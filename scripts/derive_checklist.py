"""Derive a DRAFT checklist for a domain from the parsed corpus.

The draft is auto-derived (the "auto" in auto/self-evolving); it is NOT yet
trusted. A human reviews/edits data/processed/checklists/<domain>_draft.json,
then signs it with sign_checklist.py. Only the signed copy may drive an audit.

Run:  python scripts/derive_checklist.py finance
"""
from __future__ import annotations
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import (CLAUSES_PATH, CHECKLIST_DIR, COMMITTED_CLAUSES,
                    CLAUSE_DIMENSION, INSTRUMENT)
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

    os.makedirs(CHECKLIST_DIR, exist_ok=True)
    out = os.path.join(CHECKLIST_DIR, f"{domain}_draft.json")
    checklist.save(out)

    print(f"Derived DRAFT checklist ({len(checklist.items)} requirements) -> {out}")
    for it in checklist.items:
        print(f"  • {it.citation}  [{it.dimension}/{it.scope_partition}]")
    print("\nNext: review/edit the draft, then sign it:")
    print(f"  python scripts/sign_checklist.py {domain} \"Your Name\"")


if __name__ == "__main__":
    main()
