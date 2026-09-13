"""Designing and exporting the annotation study.

Three decisions are made here because they are expensive to retrofit and easy to
get wrong in a way nobody notices until the defence.

**Stratified selection, not uniform random.** A uniform sample spends most of the
budget on easy items. The strata that earn their place are the ones where
automation fails in ways the gate cannot catch by construction: items the judge
was *confident* about (the confidently-wrong detector — a high-confidence wrong
verdict is exactly what a confidence-based gate lets through), items where it
wavered across its k runs, and items it could not call at all. A random
remainder is kept so the sample is not purely adversarial.

**Blinding.** Sheets carry an opaque token, not the probe id. Model identity and
any judge verdict are stripped. Each rater gets their own seeded permutation, so
neither can infer structure from ordering. The mapping back to probe ids lives in
a separate key file that raters do not open.

**Overlap.** The primary rater takes every item; the second rater takes a random
subset, and κ is computed on that overlap. Sizing the overlap so the *lower*
bound of the κ interval clears the threshold is what makes the criterion
defensible rather than nominally met — see `agreement.n_for_kappa_lower_bound`.
"""
from __future__ import annotations

import csv
import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

from grail.probe.schema import derive_rng

PRIMARY = "A"
SECOND = "B"


@dataclass
class StudyDesign:
    domain: str
    n_items: int = 300
    n_overlap: int = 120
    seed: int = 20260803
    # The strata exist to spend the annotation budget where disagreement is
    # informative, and they are all defined over the JUDGE's own behaviour —
    # because what this study measures is judge-human agreement, not model
    # quality. An earlier version carried a `fairness_marginal` stratum, which
    # made sense for a study of fairness items and none at all here: a fairness
    # response is the single word APPROVE, and there is no explanation in it for
    # a rater to assess.
    strata: dict = field(default_factory=lambda: {
        "judge_high_confidence": 0.40,   # confidently-wrong detector
        "judge_borderline": 0.30,        # where the judge wavered across its k runs
        "judge_undecided": 0.10,         # items the judge could not call at all
        "random": 0.20,                  # keeps the sample from being purely adversarial
    })
    guidelines_sha256: str = ""          # frozen before any judge output is seen
    created_utc: str = ""

    def __post_init__(self) -> None:
        if not self.created_utc:
            self.created_utc = datetime.now(timezone.utc).isoformat(timespec="seconds")
        if self.n_overlap > self.n_items:
            raise ValueError("overlap cannot exceed the item count")

    def as_dict(self) -> dict:
        return asdict(self)


def allocate(design: StudyDesign) -> dict:
    """Items per stratum, largest remainder, exact sum."""
    raw = {k: design.n_items * v for k, v in design.strata.items()}
    base = {k: int(v) for k, v in raw.items()}
    for k in sorted(raw, key=lambda k: (-(raw[k] - base[k]), k))[
            :design.n_items - sum(base.values())]:
        base[k] += 1
    return base


def select(candidates: list[dict], design: StudyDesign) -> list[dict]:
    """Pick items per stratum. A candidate is a dict with at least `probe_id`.

    Candidates declare which strata they belong to via a `strata` list, so this
    works before the judge exists: without judge verdicts only `random` can be
    populated, and the judge strata fill in once verdicts exist without a code
    change. Shortfalls are reported rather than silently topped up from elsewhere — a
    stratum quietly filled with random items is a study that thinks it measured
    something it did not.
    """
    quota = allocate(design)
    chosen: dict[tuple, dict] = {}
    shortfall: dict[str, int] = {}

    # Identity is (probe, model), NOT the probe alone. One probe answered by
    # four models is four explanations to rate, and each one has its own judge
    # verdict to be compared against. Keying on the probe silently capped the
    # study at one model per item, so three quarters of the judge's docket could
    # never be validated however many items were requested.
    ident = _ident

    for stratum in sorted(quota):
        want = quota[stratum]
        pool = [c for c in candidates
                if stratum in (c.get("strata") or []) and ident(c) not in chosen]
        pool.sort(key=ident)
        derive_rng(design.seed, "select", stratum).shuffle(pool)
        taken = pool[:want]
        for c in taken:
            chosen[ident(c)] = dict(c, stratum=stratum)
        if len(taken) < want:
            shortfall[stratum] = want - len(taken)

    items = sorted(chosen.values(), key=lambda c: c["probe_id"])
    for it in items:
        it["_shortfall"] = shortfall
    return items


def token_for(probe_id: str, seed: int, model_id: str = "") -> str:
    """The blinded item id a rater sees.

    Derived from the probe AND the model, because one probe answered by four
    models is four things to rate. Keying on the probe alone gave all four the
    same token: the key file would collapse them to one entry, and a rater's
    labels would be attributed to whichever explanation happened to be written
    last. The failure is silent — the sheets look right and every number
    downstream is wrong.
    """
    import hashlib
    h = hashlib.blake2b(f"{seed}|{probe_id}|{model_id}".encode(),
                        digest_size=5).hexdigest()
    return f"IT-{h.upper()}"


def token_of(item: dict, seed: int) -> str:
    """`token_for` for a selected item, which carries its own model."""
    return token_for(item["probe_id"], seed, item.get("model_id", ""))


def _ident(c: dict) -> tuple:
    """(probe, model) — the identity of a thing to be rated. See `select`."""
    return (c["probe_id"], c.get("model_id", ""))


def assign(items: list[dict], design: StudyDesign) -> dict:
    """Who rates what. Primary rates everything; second rates the overlap.

    The overlap is chosen over (probe, model) pairs for the same reason
    selection is: picking by probe alone would pull every model's answer to a
    probe into the overlap together, which is not a random subset of the items
    and would make the two raters' shared sample lumpier than the design says.
    """
    ordered = sorted(items, key=_ident)
    pool = list(ordered)
    derive_rng(design.seed, "overlap").shuffle(pool)
    overlap = {_ident(c) for c in pool[:design.n_overlap]}
    return {
        PRIMARY: ordered,
        SECOND: [c for c in ordered if _ident(c) in overlap],
        "overlap_ids": sorted(token_for(pid, design.seed, mid)
                              for pid, mid in overlap),
    }


COLUMNS = ["item", "dimension", "criterion", "prompt", "response", "rating", "notes"]


def export(items: list[dict], design: StudyDesign, out_dir: str,
           labels: list[str]) -> dict:
    """Write one blinded CSV per rater, plus a key file the raters never open."""
    os.makedirs(out_dir, exist_ok=True)
    sheets = assign(items, design)
    written = {}

    for rater in (PRIMARY, SECOND):
        rows = list(sheets[rater])
        # a per-rater permutation: neither can read structure out of the order
        derive_rng(design.seed, "order", rater).shuffle(rows)
        path = os.path.join(out_dir, f"annotation_rater_{rater}.csv")
        with open(path, "w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=COLUMNS)
            w.writeheader()
            for it in rows:
                w.writerow({
                    "item": token_of(it, design.seed),
                    "dimension": it.get("dimension", ""),
                    "criterion": it.get("criterion", ""),
                    "prompt": it.get("prompt", ""),
                    "response": it.get("response", ""),
                    "rating": "",       # allowed values are in the guidelines
                    "notes": "",
                })
        written[rater] = path

    key_path = os.path.join(out_dir, "KEY_do_not_open_until_scored.json")
    with open(key_path, "w", encoding="utf-8") as fh:
        json.dump({
            "design": design.as_dict(),
            "allowed_labels": labels,
            "overlap_ids": sheets["overlap_ids"],
            "shortfall": (items[0].get("_shortfall") if items else {}) or {},
            "items": {token_of(it, design.seed): {
                "probe_id": it["probe_id"],
                # The audited model. Scoring needs it to line a human label up
                # against the judge verdict for the SAME explanation; without
                # it the study cannot be joined back to what it validates.
                "model_id": it.get("model_id", ""),
                "stratum": it.get("stratum"),
                "dimension": it.get("dimension"),
            } for it in items},
        }, fh, ensure_ascii=False, indent=2)

    return {"sheets": written, "key": key_path,
            "n_primary": len(sheets[PRIMARY]), "n_second": len(sheets[SECOND]),
            "shortfall": (items[0].get("_shortfall") if items else {}) or {}}


def load_sheet(path: str, labels: list[str]) -> dict:
    """Read a completed sheet. Unrated rows are dropped and counted, not guessed."""
    ratings, blank, invalid = {}, 0, []
    with open(path, encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            value = (row.get("rating") or "").strip()
            if not value:
                blank += 1
                continue
            if value not in labels:
                invalid.append((row.get("item"), value))
                continue
            ratings[row["item"]] = value
    return {"ratings": ratings, "blank": blank, "invalid": invalid}
