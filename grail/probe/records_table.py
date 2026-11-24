"""Record-backed cases from a generic table: one JSON object per applicant.

Statlog has its own loader because its columns are codes. Tables imported by
GRAIL's own scripts (the NHANES life-insurance applicants) arrive already
decoded into readable values, so all a pack has to declare is which fields to
show, which to hide, which outcomes to keep aside, and how to stratify.

Declared in the pack under ``source`` (``loader: "table"``):

``path``            JSONL file, one record per line, each with ``record_id``
``render_fields``   fields copied verbatim into the prompt slots
``redacted``        protected fields: kept as ``_redacted_<name>``, never rendered
``outcome_fields``  recorded outcomes: kept as ``_outcome_<name>``, never rendered
``synthetic``       per-record fields the data do not hold (a sum insured, a
                    term), drawn deterministically from the record id, so they
                    are identical in both arms of a pair and in every probe
                    that draws the same record
``strength``        a face-valid score over named fields whose terciles define
                    the strata. It may not read a redacted or an outcome field;
                    that is refused at load, because stratifying on the outcome
                    leaks it into the design and stratifying on the protected
                    attribute rebuilds the confound the pairing removes.
"""
from __future__ import annotations

import hashlib
import json
import os
from functools import lru_cache

from grail.probe.schema import derive_rng


@lru_cache(maxsize=8)
def load_table(path: str, hint: str = "") -> tuple:
    if not os.path.exists(path):
        raise SystemExit(
            f"No record file at {path}.\n"
            + (f"Fetch and import it once: {hint}" if hint else "Import it first."))
    out = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    if not out:
        raise SystemExit(f"{path} is empty")
    if any("record_id" not in r for r in out):
        raise SystemExit(f"{path}: every record needs a record_id")
    return tuple(out)


def check_spec(source: dict) -> None:
    """Refuse a strength score that reads a protected or an outcome field."""
    forbidden = set(source.get("redacted") or []) | set(source.get("outcome_fields") or [])
    bad = sorted(forbidden & set((source.get("strength") or {}).keys()))
    if bad:
        raise SystemExit(
            f"record pack stratifies on {bad}, which are redacted or outcome "
            "fields; the strata may use face-valid risk factors only")
    shown = set(source.get("render_fields") or [])
    leak = sorted(shown & forbidden)
    if leak:
        raise SystemExit(f"record pack would render protected or outcome fields: {leak}")


def score(rec: dict, spec: dict) -> float:
    """Face-valid points. Bands are half-open [lo, hi); missing values score 0."""
    total = 0.0
    for field, rule in spec.items():
        v = rec.get(field)
        if v is None:
            continue
        if "bands" in rule:
            for lo, hi, pts in rule["bands"]:
                if isinstance(v, (int, float)) and lo <= v < hi:
                    total += pts
                    break
        elif "map" in rule:
            total += rule["map"].get(str(v), 0)
        elif "per_unit" in rule and isinstance(v, (int, float)):
            total += rule["per_unit"] * v
    return total


def _tiebreak(record_id: str) -> str:
    # A face-valid score has many ties (every young never-smoker with no history
    # scores 0). Breaking them by the id string would put the tercile cut through
    # id order, which in survey data tracks the collection cycle. A hash of the
    # id is just as deterministic and carries no information.
    return hashlib.blake2b(record_id.encode("utf-8"), digest_size=8).hexdigest()


def stratify(records: tuple, spec: dict, names: tuple) -> dict:
    """Terciles of the score, lowest first; ties broken by a hash of the record id."""
    scored = sorted(records, key=lambda r: (score(r, spec), _tiebreak(r["record_id"])))
    n = len(scored)
    lo, hi = n // 3, 2 * n // 3
    return {names[0]: scored[:lo], names[1]: scored[lo:hi], names[2]: scored[hi:]}


def tercile_cuts(records: tuple, spec: dict) -> tuple:
    """The scores at the two tercile boundaries (for provenance and the amendment)."""
    s = sorted(score(r, spec) for r in records)
    return s[len(s) // 3], s[2 * len(s) // 3]


@lru_cache(maxsize=8)
def _pools(path: str, spec_key: str, names: tuple, hint: str) -> dict:
    return stratify(load_table(path, hint), json.loads(spec_key), names)


def _synthetic(rec_id: str, spec: dict, vocab: dict):
    r = derive_rng(0, "record_policy", rec_id, spec["name"])
    kind = spec["type"]
    if kind == "int_step":
        lo, hi = spec["fixed"]
        return r.randrange(lo, hi + 1, spec.get("step", 1))
    if kind == "int_range":
        lo, hi = spec["fixed"]
        return r.randint(lo, hi)
    if kind == "choice":
        return r.choice(vocab[spec["vocab"]])
    raise SystemExit(f"unknown synthetic field type '{kind}'")


def reference(record_id: str) -> str:
    """A five-digit application number derived from the record id.

    The dataset's own identifier (an NHANES SEQN, say) never reaches a prompt:
    it would add nothing for the system under audit and is the one field that
    points straight back to a public-use record.
    """
    h = int(hashlib.blake2b(record_id.encode("utf-8"), digest_size=8).hexdigest(), 16)
    return f"{10000 + h % 90000}"


def to_slots(rec: dict, pack: dict) -> dict:
    source = pack["source"]
    rid = rec["record_id"]
    slots: dict = {"ref": f"{pack.get('case_prefix', 'TR')}-{reference(rid)}"}
    slots.update(pack.get("axis_slot_defaults", {}))
    vocab = pack.get("vocab") or {}
    if vocab.get("initials") and vocab.get("surnames"):
        nr = derive_rng(0, "record_name", rid)
        slots["initial"] = nr.choice(vocab["initials"])
        slots["surname"] = nr.choice(vocab["surnames"])
    for f in source.get("render_fields") or []:
        v = rec.get(f)
        slots[f] = "not stated" if v is None else v
    for spec in source.get("synthetic") or []:
        slots[spec["name"]] = _synthetic(rid, spec, vocab)
    for f in source.get("redacted") or []:
        slots[f"_redacted_{f}"] = rec.get(f)
    for f in source.get("outcome_fields") or []:
        slots[f"_outcome_{f}"] = rec.get(f)
    slots["_score"] = score(rec, source.get("strength") or {})
    slots["source_record"] = rid
    return slots


@lru_cache(maxsize=64)
def _permutation(n: int, seed: int, domain: str, ns: str, stratum: str) -> tuple:
    order = list(range(n))
    derive_rng(seed, domain, ns, stratum, "without_replacement").shuffle(order)
    return tuple(order)


def sample_table_case(pack: dict, seed: int, domain: str, index: int, stratum: str,
                      ns: str, path: str, ordinal: int | None = None) -> dict:
    """One record drawn from a stratum.

    With `ordinal` (the case's position among the cases of its stratum, which
    the generators pass) the draw is WITHOUT replacement: a fixed shuffle of the
    stratum's pool, keyed by (seed, domain, ns, stratum), read in order. A person
    then appears in at most one pair of a stratum until the pool is used up,
    which matters: at temperature 0 the same prompt gets the same answer, so a
    person drawn twice is one observation counted twice. Statlog's 1,000 records
    could not avoid that (its marginal tercile holds ~333 people for 2,844
    pairs); NHANES's ~3,000 per tercile can. Past the end of the pool the shuffle
    wraps, and the continuous jury counts a repeated pair once.

    Without `ordinal` (older callers) the draw is with replacement, keyed by
    (seed, domain, ns, index, stratum), exactly as before. Either way nothing
    depends on the arm, and the shuffle is prefix-stable: more cases extend the
    sequence without changing the earlier ones.
    """
    source = pack["source"]
    check_spec(source)
    order = tuple(pack.get("stratum_order") or sorted(pack["strata"]))
    spec_key = json.dumps(source.get("strength") or {}, sort_keys=True)
    pool = _pools(path, spec_key, order, source.get("fetch_hint", ""))[stratum]
    if not pool:
        raise SystemExit(f"stratum '{stratum}' has no records")
    if ordinal is not None:
        perm = _permutation(len(pool), seed, domain, ns, stratum)
        rec = pool[perm[ordinal % len(pool)]]
    else:
        r = derive_rng(seed, domain, ns, index, stratum)
        rec = pool[r.randrange(len(pool))]
    slots = to_slots(rec, pack)
    slots["stratum"] = stratum
    return slots
