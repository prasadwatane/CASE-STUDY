"""Record-backed hiring cases: a real job description paired with a CV.

Source: Rozado (2025), 700 LLM-generated CVs and 700 job descriptions across 70
professions, released with "Gender and Positional Biases in LLM-Based Hiring
Decisions" (PeerJ Computer Science 12:e3628, 2026), Zenodo
10.5281/zenodo.17173798, CC BY 4.0. The CVs carry no name, which is what makes
them usable: the protected arm supplies the only identity signal.

Why this and not Statlog's loader. Statlog is twenty coded columns; these are
free text. Three things do not carry over and are decided here instead.

**Strata come from the job, not the candidate.** There is no hiring outcome and
no quality score in the data, and scoring CV quality ourselves would be building
the classifier we are auditing. The stratum is the relation between the CV and
the job: *strong* = a CV written for the same profession; *marginal* = a CV for
a different profession in the same occupational family (a paralegal applying as
a family lawyer); *weak* = a CV from another family. The family map lives in the
pack, is declared before any response exists, and never reads a protected field.

**Fairness cues are removed at import, not at render.** Most job descriptions
end with an equal-opportunity statement ("we do not discriminate on the basis
of ... sex"), and a few CVs list a gendered professional association. The first
tells the model that fairness is being looked at; the second contradicts the
arm. `clean_jd` drops the paragraph carrying a cue (and an orphaned heading
before it); `cv_usable` excludes a CV carrying one. Nothing else is edited.

**The leakage guard is scoped.** Ordinary uses of "compliance" or "audit" in a
CV are not GRAIL telling the model anything, so the rendered documents are
declared as quoted (`_quoted`) and checked against the construct-cue list only
(`grail.probe.schema.assert_no_leakage`). Everything GRAIL writes is still
checked against the full list.
"""
from __future__ import annotations

import csv
import json
import os
from functools import lru_cache

from grail.probe.schema import construct_cues, derive_rng

SOURCE = {
    "name": "Rozado (2025) LLM hiring experiment: CVs and job descriptions",
    "doi": "10.5281/zenodo.17173798",
    "paper": "Rozado, D. (2026). Gender and positional biases in LLM-based hiring "
             "decisions: evidence from comparative CV/resume evaluations. "
             "PeerJ Computer Science 12:e3628.",
    "licence": "CC BY 4.0",
}

# Gendered signals a CV can carry without any pronoun. A CV listing membership of
# a women's professional association is a female-coded CV, and pairing it with
# "Mr." would make the arm incoherent. Case-sensitive on purpose: "Women's
# Health" (a clinical area) and "Brigham and Women's Hospital" are not these.
_GENDER_CODED = ["Professional Women", "Women in "]

MIN_JD_WORDS = 250


def _gender_coded(text: str) -> list[str]:
    return [g for g in _GENDER_CODED if g in text]


def _heading(par: str) -> bool:
    s = par.strip()
    return (s.startswith("**") or s.startswith("#")) and len(s.split()) <= 8


def clean_jd(text: str) -> tuple[str, int]:
    """Drop every paragraph carrying a construct cue; return (text, n_dropped)."""
    kept: list[str] = []
    dropped = 0
    for par in text.split("\n\n"):
        if construct_cues(par):
            dropped += 1
            if kept and _heading(kept[-1]):
                kept.pop()
            continue
        kept.append(par)
    return "\n\n".join(kept).strip(), dropped


def cv_usable(text: str) -> bool:
    return not construct_cues(text) and not _gender_coded(text)


# --- import (raw CSV -> cleaned JSONL) --------------------------------------
def import_raw(raw_dir: str, excluded_professions: list[str]) -> dict:
    """Read Rozado's two CSVs and return cleaned records plus an exclusion log."""
    csv.field_size_limit(10 ** 9)
    log = {"cv_excluded_cue": [], "jd_paragraphs_dropped": 0, "jd_cleaned": 0,
           "jd_excluded_short_or_cue": [], "excluded_professions": excluded_professions}
    cvs, jds = [], []
    with open(os.path.join(raw_dir, "CVs.csv"), encoding="utf-8") as fh:
        for i, row in enumerate(csv.DictReader(fh)):
            rid = f"rozado_cv:{i:03d}"
            if row["profession"] in excluded_professions:
                continue
            if not cv_usable(row["cv"]):
                log["cv_excluded_cue"].append(rid)
                continue
            cvs.append({"id": rid, "profession": row["profession"],
                        "generated_by": row["model_name"], "text": row["cv"].strip()})
    with open(os.path.join(raw_dir, "job_descriptions.csv"), encoding="utf-8") as fh:
        for i, row in enumerate(csv.DictReader(fh)):
            rid = f"rozado_jd:{i:03d}"
            if row["profession"] in excluded_professions:
                continue
            text, dropped = clean_jd(row["job_description"])
            log["jd_paragraphs_dropped"] += dropped
            log["jd_cleaned"] += dropped > 0
            if construct_cues(text) or _gender_coded(text) or len(text.split()) < MIN_JD_WORDS:
                log["jd_excluded_short_or_cue"].append(rid)
                continue
            jds.append({"id": rid, "profession": row["profession"],
                        "generated_by": row["model_name"], "text": text,
                        "paragraphs_dropped": dropped})
    return {"cvs": cvs, "jds": jds, "log": log}


# --- loading ----------------------------------------------------------------
@lru_cache(maxsize=4)
def load(record_dir: str) -> tuple[tuple, tuple]:
    out = []
    for name in ("cvs.jsonl", "jds.jsonl"):
        path = os.path.join(record_dir, name)
        if not os.path.exists(path):
            raise SystemExit(
                f"No record file at {path}.\n"
                "Import it once from Rozado's archive (Zenodo "
                f"{SOURCE['doi']}, {SOURCE['licence']}):\n"
                "  python scripts/import_rozado.py <folder holding CVs.csv and "
                "job_descriptions.csv>")
        with open(path, encoding="utf-8") as fh:
            out.append(tuple(json.loads(line) for line in fh if line.strip()))
    if not out[0] or not out[1]:
        raise SystemExit(f"{record_dir}: empty CV or job-description file")
    return out[0], out[1]


def family_index(pack: dict) -> dict[str, str]:
    fam = {}
    for family, profs in pack["source"]["families"].items():
        for p in profs:
            if p in fam:
                raise SystemExit(f"profession '{p}' is in two families")
            fam[p] = family
    return fam


@lru_cache(maxsize=4)
def _pools(record_dir: str, families_key: str) -> dict:
    cvs, jds = load(record_dir)
    fam = dict(json.loads(families_key))
    missing = sorted({r["profession"] for r in cvs + jds} - set(fam))
    if missing:
        raise SystemExit(f"professions with no family in the pack: {missing}")
    by_prof: dict[str, list] = {}
    for cv in cvs:
        by_prof.setdefault(cv["profession"], []).append(cv)
    by_cv_id = {cv["id"]: cv for cv in cvs}
    return {"cvs": cvs, "jds": jds, "fam": fam, "by_prof": by_prof, "by_id": by_cv_id}


def pools_for(pack: dict, record_dir: str) -> dict:
    key = json.dumps(sorted(family_index(pack).items()))
    return _pools(record_dir, key)


def candidates(P: dict, jd: dict, relation: str) -> list:
    prof, fam = jd["profession"], P["fam"][jd["profession"]]
    if relation == "strong":
        pool = P["by_prof"].get(prof, [])
    elif relation == "marginal":
        pool = [c for c in P["cvs"] if P["fam"][c["profession"]] == fam
                and c["profession"] != prof]
    elif relation == "weak":
        pool = [c for c in P["cvs"] if P["fam"][c["profession"]] != fam]
    else:
        raise SystemExit(f"unknown stratum '{relation}' for a CV/job pack")
    if not pool:
        raise SystemExit(f"no '{relation}' CV for a '{prof}' job")
    return pool


def _cv_slots(P: dict, cv: dict) -> dict:
    return {"cv": cv["text"], "source_cv": cv["id"],
            "cv_profession": cv["profession"], "cv_family": P["fam"][cv["profession"]]}


def sample_cv_case(pack: dict, seed: int, domain: str, index: int, stratum: str,
                   ns: str, record_dir: str) -> dict:
    """One (job, CV) case. Depends on (seed, domain, ns, index, stratum) only."""
    P = pools_for(pack, record_dir)
    r = derive_rng(seed, domain, ns, index, stratum)
    jd = P["jds"][r.randrange(len(P["jds"]))]
    pool = candidates(P, jd, stratum)
    cv = pool[r.randrange(len(pool))]
    # alternates for the controls, drawn every time so the stream never depends
    # on whether a control asked for them
    strong = candidates(P, jd, "strong")
    weak = candidates(P, jd, "weak")
    alt_strong = strong[r.randrange(len(strong))]
    alt_weak = weak[r.randrange(len(weak))]

    slots: dict = {"ref": f"{pack.get('case_prefix', 'JR')}-{index:05d}"}
    slots.update(pack.get("axis_slot_defaults", {}))
    vocab = pack.get("vocab") or {}
    if vocab.get("initials") and vocab.get("surnames"):
        nr = derive_rng(0, "record_name", cv["id"])
        slots["initial"] = nr.choice(vocab["initials"])
        slots["surname"] = nr.choice(vocab["surnames"])
    slots.update({"job_title": jd["profession"], "job_description": jd["text"],
                  "source_jd": jd["id"], "jd_family": P["fam"][jd["profession"]]})
    slots.update(_cv_slots(P, cv))
    slots["_alt_cv_strong"] = alt_strong["id"]
    slots["_alt_cv_weak"] = alt_weak["id"]
    slots["_quoted"] = list(pack["source"].get("quoted_fields", ["job_description", "cv"]))
    slots["stratum"] = stratum
    return slots


def resolve(pack: dict, slots: dict, field: str, value, record_dir: str) -> dict:
    """A control override like {"cv": "@strong"} -> the slot updates it implies.

    The controls swap one document for another of a different relation to the
    same job; the provenance slots follow the text so the record stays honest.
    """
    if not (isinstance(value, str) and value.startswith("@")):
        return {field: value}
    if field != "cv":
        raise SystemExit(f"a CV/job pack can only swap 'cv' by reference, not '{field}'")
    rel = value[1:]
    if rel == "self":
        return {}
    alt_id = slots.get(f"_alt_cv_{rel}")
    if alt_id is None:
        raise SystemExit(f"unknown CV reference '{value}' (use @strong, @weak or @self)")
    P = pools_for(pack, record_dir)
    return _cv_slots(P, P["by_id"][alt_id])
