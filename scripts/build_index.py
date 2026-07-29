"""Build the standards index end-to-end.

    raw text  --(deterministic parser)-->  legal units
              --(linker)-->               units + definition/exception links
              --(hybrid index)-->         dense + BM25, persisted

Run:  python scripts/build_index.py
"""
from __future__ import annotations
import glob
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import RAW_DIR, CLAUSES_PATH, PROCESSED_DIR, INSTRUMENT
from grail.ingest.clause_parser import parse_text
from grail.ingest.loaders import load_source_text, clean_oj_text
from grail.ingest.linker import link_units
from grail.ingest.schema import save_units
from grail.index.hybrid_index import HybridIndex


def main() -> None:
    os.makedirs(PROCESSED_DIR, exist_ok=True)
    # Prefer the official PDF if present; otherwise fall back to seed .txt.
    pdfs = sorted(glob.glob(os.path.join(RAW_DIR, "*.pdf")))
    sources = pdfs or sorted(glob.glob(os.path.join(RAW_DIR, "*.txt")))
    if not sources:
        raise SystemExit(f"No raw sources (*.pdf / *.txt) found in {RAW_DIR}")

    units = []
    for path in sources:
        raw = load_source_text(path)
        text = clean_oj_text(raw)
        units.extend(parse_text(text, INSTRUMENT))
        print(f"  ingested {os.path.basename(path)}")

    units = link_units(units)
    save_units(units, CLAUSES_PATH)

    counts: dict[str, int] = {}
    for u in units:
        counts[u.unit_type] = counts.get(u.unit_type, 0) + 1

    index = HybridIndex.build(units)
    index.save()

    print(f"Parsed {len(units)} legal units -> {CLAUSES_PATH}")
    print("  by type:", counts)
    print(f"  embed backend: {index.backend}")
    print("  index saved.")


if __name__ == "__main__":
    main()
