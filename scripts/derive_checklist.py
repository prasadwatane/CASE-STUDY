"""Derive a DRAFT checklist for a domain from the parsed corpus.

The draft is auto-derived (the "auto" in auto/self-evolving); it is NOT yet
trusted. A human reviews/edits data/processed/checklists/<domain>_draft.json,
then signs it with sign_checklist.py. Only the signed copy may drive an audit.

Run:  python scripts/derive_checklist.py finance
"""
from __future__ import annotations
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import (CLAUSES_PATH, CHECKLIST_DIR, COMMITTED_CLAUSES,
                    CLAUSE_DIMENSION, CRITERIA_DIR, INSTRUMENT)
from grail.ingest.schema import load_units
from grail.ground.checklist import build_checklist


def main() -> None:
    domain = sys.argv[1] if len(sys.argv) > 1 else "finance"
    if domain not in COMMITTED_CLAUSES:
        raise SystemExit(f"No committed clauses configured for domain '{domain}'.")
    if not os.path.exists(CLAUSES_PATH):
        raise SystemExit("No parsed corpus. Run scripts/build_index.py first.")

    units = load_units(CLAUSES_PATH)
    checklist = build_checklist(
        units, COMMITTED_CLAUSES[domain], domain, INSTRUMENT, CLAUSE_DIMENSION)

    # Criteria are authored by a human and version-controlled, so they survive
    # regeneration. The clause text comes from the law; what counts as
    # conformance to it is a judgement, and a judgement has to be reviewable and
    # attributable rather than regenerated from a corpus each time.
    criteria_path = os.path.join(CRITERIA_DIR, f"{domain}.json")
    criteria, filled = {}, 0
    if os.path.exists(criteria_path):
        criteria = json.load(open(criteria_path, encoding="utf-8"))
    for it in checklist.items:
        entry = criteria.get(it.clause_id)
        if isinstance(entry, dict) and entry.get("criterion"):
            it.criterion = entry["criterion"]
            filled += 1

    os.makedirs(CHECKLIST_DIR, exist_ok=True)
    out = os.path.join(CHECKLIST_DIR, f"{domain}_draft.json")
    checklist.save(out)

    print(f"Derived DRAFT checklist ({len(checklist.items)} requirements) -> {out}")
    for it in checklist.items:
        mark = "criterion set" if it.criterion else "NO CRITERION — unscoreable"
        print(f"  • {it.citation}  [{it.dimension}/{it.scope_partition}]  {mark}")
    if filled < len(checklist.items):
        print(f"\n  {len(checklist.items) - filled} clause(s) have no criterion. "
              f"Edit {criteria_path} — a clause without one cannot be judged, "
              "and its probes cannot be scored however many were answered.")
    print("\nNext: review/edit the draft, then sign it:")
    print(f"  python scripts/sign_checklist.py {domain} \"Your Name\"")


if __name__ == "__main__":
    main()
