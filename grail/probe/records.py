"""Record-backed cases: real applicants instead of sampled ones.

A stimulus pack normally *samples* a case from ranges. A record-backed pack draws
one from a real dataset instead, which buys three things at once: profiles with a
realistic joint distribution rather than independently sampled fields, an outcome
label that turns robustness from agreement into genuine paired accuracy, and a
protected attribute that is already present in the data rather than invented.

Committed source: the Statlog (German Credit) dataset — 1,000 applicants, 20
attributes, a good/bad repayment label, CC BY 4.0. Two design decisions in here
are worth reading before trusting anything built on it.

**The label is not a fairness gold.** It records observed repayment, not whether
the application *should* have been approved. Used as a fairness reference it
would enshrine historical lending decisions as the standard, which is the thing
under audit. It is legitimate ground truth for robustness and accuracy, and that
is all it is used for.

**Stratification never touches the label or the protected fields.** Credit
strength is scored from face-valid financial attributes only, and the tercile
cuts are computed from that score. Stratifying on the outcome would leak it into
the design; stratifying on anything gender-correlated would rebuild the confound
the counterbalancing exists to remove.

Attribute 9 (personal status and sex) and attribute 20 (foreign worker) are
**redacted from every rendered prompt**. They are the protected axes: an arm
supplies the signal deliberately, so leaving the recorded value in the text would
mean the system sees two protected attributes when one is under test. The
original values stay in `slots` under `_redacted_*` for analysis.
"""
from __future__ import annotations

import os
from functools import lru_cache

from grail.probe.schema import derive_rng

SOURCE = {
    "name": "Statlog (German Credit Data)",
    "url": "https://archive.ics.uci.edu/dataset/144/statlog+german+credit+data",
    "licence": "CC BY 4.0",
    "n_expected": 1000,
    "vintage": "1994 (amounts in Deutsche Mark; a period dataset, not current lending)",
}

# Column order as published, 1-indexed in the UCI documentation.
COLUMNS = [
    "checking_status", "duration_months", "credit_history", "purpose",
    "credit_amount", "savings", "employment_since", "instalment_rate",
    "personal_status_sex", "other_debtors", "residence_since", "property",
    "age", "other_instalment_plans", "housing", "existing_credits", "job",
    "liable_people", "telephone", "foreign_worker", "label",
]

NUMERIC = {"duration_months", "credit_amount", "instalment_rate",
           "residence_since", "age", "existing_credits", "liable_people", "label"}

# Fields carrying a protected signal: never rendered, available as axes.
REDACTED = ("personal_status_sex", "foreign_worker")

CODES = {
    "checking_status": {"A11": "overdrawn", "A12": "under 200 DM",
                        "A13": "200 DM or more", "A14": "no checking account"},
    "credit_history": {"A30": "no credits taken, or all paid back duly",
                       "A31": "all credits at this bank paid back duly",
                       "A32": "existing credits paid back duly so far",
                       "A33": "delay in paying off in the past",
                       "A34": "critical account, or credits elsewhere"},
    "purpose": {"A40": "new car", "A41": "used car", "A42": "furniture or equipment",
                "A43": "radio or television", "A44": "domestic appliances",
                "A45": "repairs", "A46": "education", "A47": "holiday",
                "A48": "retraining", "A49": "business", "A410": "other"},
    "savings": {"A61": "under 100 DM", "A62": "100 to 500 DM",
                "A63": "500 to 1000 DM", "A64": "1000 DM or more",
                "A65": "unknown or none"},
    "employment_since": {"A71": "unemployed", "A72": "under 1 year",
                         "A73": "1 to 4 years", "A74": "4 to 7 years",
                         "A75": "7 years or more"},
    "other_debtors": {"A101": "none", "A102": "co-applicant", "A103": "guarantor"},
    "property": {"A121": "real estate", "A122": "savings agreement or life policy",
                 "A123": "car or other", "A124": "unknown or none"},
    "other_instalment_plans": {"A141": "at another bank", "A142": "at stores",
                               "A143": "none"},
    "housing": {"A151": "rented", "A152": "owned", "A153": "provided free"},
    "job": {"A171": "unemployed or unskilled, non-resident",
            "A172": "unskilled resident", "A173": "skilled employee",
            "A174": "management or self-employed"},
    "telephone": {"A191": "none", "A192": "registered"},
    "personal_status_sex": {"A91": "male, divorced or separated",
                            "A92": "female, divorced, separated or married",
                            "A93": "male, single", "A94": "male, married or widowed",
                            "A95": "female, single"},
    "foreign_worker": {"A201": "yes", "A202": "no"},
}

# Recorded gender, for analysis only — never rendered, and never used to stratify.
GENDER = {"A91": "male", "A92": "female", "A93": "male", "A94": "male", "A95": "female"}


# --- loading ----------------------------------------------------------------
def parse_line(line: str, index: int) -> dict:
    parts = line.split()
    if len(parts) != len(COLUMNS):
        raise ValueError(f"row {index}: expected {len(COLUMNS)} fields, got {len(parts)}")
    rec: dict = {"record_id": f"german_credit:{index:04d}"}
    for name, raw in zip(COLUMNS, parts):
        rec[name] = int(raw) if name in NUMERIC else raw
    rec["recorded_gender"] = GENDER.get(rec["personal_status_sex"], "unknown")
    rec["repaid"] = rec["label"] == 1        # 1 = good, 2 = bad
    return rec


@lru_cache(maxsize=8)
def load_records(path: str) -> tuple:
    if not os.path.exists(path):
        raise SystemExit(
            f"No record file at {path}.\n"
            "Fetch it once:  python scripts/fetch_german_credit.py\n"
            f"Source: {SOURCE['url']}  ({SOURCE['licence']})")
    records = []
    with open(path, encoding="utf-8") as fh:
        for i, line in enumerate(fh):
            line = line.strip()
            if line:
                records.append(parse_line(line, i))
    if not records:
        raise SystemExit(f"{path} is empty")
    return tuple(records)


# --- credit strength, scored without the label or the protected fields ------
# Face-valid orderings, NOT fitted to the outcome. Fitting the score to the label
# would be building a classifier and then auditing the probes it generated.
_STRENGTH = {
    "checking_status": {"A11": 0, "A12": 1, "A13": 2, "A14": 1},
    "credit_history": {"A30": 2, "A31": 3, "A32": 2, "A33": 1, "A34": 0},
    "savings": {"A61": 0, "A62": 1, "A63": 2, "A64": 3, "A65": 1},
    "employment_since": {"A71": 0, "A72": 1, "A73": 2, "A74": 3, "A75": 4},
}


def strength(rec: dict) -> int:
    score = sum(table.get(rec[field], 0) for field, table in _STRENGTH.items())
    score += 2 if rec["duration_months"] <= 12 else 1 if rec["duration_months"] <= 24 else 0
    score += max(0, 4 - rec["instalment_rate"])       # rate 1 is best, 4 worst
    return score


def stratify(records: tuple, names: tuple[str, str, str]) -> dict:
    """Split records into (weak, marginal, strong) by strength terciles.

    `names` is given lowest-first so a pack can call its bands whatever it likes;
    the cut points come from the data rather than from a guessed threshold.
    """
    scored = sorted(records, key=lambda r: (strength(r), r["record_id"]))
    n = len(scored)
    lo, hi = n // 3, 2 * n // 3
    return {names[0]: scored[:lo], names[1]: scored[lo:hi], names[2]: scored[hi:]}


# --- turning a record into slots -------------------------------------------
def to_slots(rec: dict, pack: dict) -> dict:
    """Human-readable slots. Protected fields are redacted, never rendered."""
    slots: dict = {"ref": f"{pack.get('case_prefix', 'GC')}-{rec['record_id'].split(':')[1]}"}
    slots.update(pack.get("axis_slot_defaults", {}))

    # The dataset holds no names, and "Ms. applicant GC-0042" does not read like a
    # real file. A name is generated from the record id — deterministic, identical
    # across both arms of a pair, and carrying no information. Standard practice in
    # correspondence audit studies; the financial attributes remain the real record.
    vocab = pack.get("vocab") or {}
    if vocab.get("initials") and vocab.get("surnames"):
        r = derive_rng(0, "record_name", rec["record_id"])
        slots["initial"] = r.choice(vocab["initials"])
        slots["surname"] = r.choice(vocab["surnames"])

    for field in COLUMNS:
        if field in ("label",) or field in REDACTED:
            continue
        value = rec[field]
        slots[field] = CODES[field][value] if field in CODES else value

    # kept for analysis and provenance; the renderer never sees these
    slots["_redacted_personal_status_sex"] = rec["personal_status_sex"]
    slots["_redacted_foreign_worker"] = rec["foreign_worker"]
    slots["_recorded_gender"] = rec["recorded_gender"]
    slots["_repaid"] = rec["repaid"]
    slots["_strength"] = strength(rec)
    slots["source_record"] = rec["record_id"]
    return slots


def sample_record_case(pack: dict, seed: int, domain: str, index: int,
                       stratum: str, ns: str, records_path: str) -> dict:
    """Draw one real record deterministically from a stratum.

    Sampling is with replacement by design: 1,000 records cannot cover 655
    fairness pairs plus 290 robustness cases without reuse, and reuse is harmless
    because every case is rendered identically for both arms. Which record a case
    draws depends only on (seed, domain, ns, index, stratum) — never on the arm.
    """
    records = load_records(records_path)
    bands = tuple(sorted(pack["strata"]))
    order = pack.get("stratum_order") or list(bands)
    pool = stratify(records, tuple(order))[stratum]
    if not pool:
        raise SystemExit(f"stratum '{stratum}' has no records")
    r = derive_rng(seed, domain, ns, index, stratum)
    rec = pool[r.randrange(len(pool))]
    slots = to_slots(rec, pack)
    slots["stratum"] = stratum
    return slots
