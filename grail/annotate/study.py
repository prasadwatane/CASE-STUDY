"""Designing and exporting the annotation study.

Three decisions are made here because they are expensive to retrofit and easy to
get wrong in a way nobody notices until the defence.

**Stratified selection, not uniform random.** A uniform sample spends most of the
budget on easy items. The strata that earn their place are the ones where
automation fails in ways the gate cannot catch by construction: items the judge
was *confident* about (the confidently-wrong detector — a high-confidence wrong
verdict is exactly what a confidence-based gate lets through), and marginal-band
fairness items, where differential treatment lives. A random remainder is kept so
the sample is not purely adversarial.

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
    strata: dict = field(default_factory=lambda: {
        "judge_high_confidence": 0.30,   # confidently-wrong detector
        "fairness_marginal": 0.30,       # where differential treatment lives
        "judge_borderline": 0.20,        # near the gate threshold
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
    works before the judge exists: today only `fairness_marginal` and `random`
    can be populated, and the judge strata fill in later without a code change.
    Shortfalls are reported rather than silently topped up from elsewhere — a
    stratum quietly filled with random items is a study that thinks it measured
    something it did not.
    """
    quota = allocate(design)
    chosen: dict[str, dict] = {}
    shortfall: dict[str, int] = {}

    for stratum in sorted(quota):
        want = quota[stratum]
        pool = [c for c in candidates
                if stratum in (c.get("strata") or []) and c["probe_id"] not in chosen]
        pool.sort(key=lambda c: c["probe_id"])
        derive_rng(design.seed, "select", stratum).shuffle(pool)
        taken = pool[:want]
        for c in taken:
            chosen[c["probe_id"]] = dict(c, stratum=stratum)
        if len(taken) < want:
            shortfall[stratum] = want - len(taken)

    items = sorted(chosen.values(), key=lambda c: c["probe_id"])
    for it in items:
        it["_shortfall"] = shortfall
    return items


def assign(items: list[dict], design: StudyDesign) -> dict:
    """Who rates what. Primary rates everything; second rates the overlap."""
    ordered = sorted(items, key=lambda c: c["probe_id"])
    r = derive_rng(design.seed, "overlap")
    pool = list(ordered)
    r.shuffle(pool)
    overlap = {c["probe_id"] for c in pool[:design.n_overlap]}
    return {
        PRIMARY: ordered,
        SECOND: [c for c in ordered if c["probe_id"] in overlap],
        "overlap_ids": sorted(overlap),
    }


def token_for(probe_id: str, seed: int) -> str:
    import hashlib
    h = hashlib.blake2b(f"{seed}|{probe_id}".encode(), digest_size=5).hexdigest()
    return f"IT-{h.upper()}"


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
                    "item": token_for(it["probe_id"], design.seed),
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
            "items": {token_for(it["probe_id"], design.seed): {
                "probe_id": it["probe_id"], "stratum": it.get("stratum"),
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
