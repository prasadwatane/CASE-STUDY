"""E1 retrieval evaluation — the ruler for the "which embedding model" question.

Builds the index with the CURRENT embedding model (config.EMBED_MODEL, override
with GRAIL_EMBED_MODEL), runs the gold query->clause set, and reports
recall@k and MRR. Search runs over ALL units (not just the probeable set) so it
measures raw retrieval quality — this is Gate A / success-criterion S1.

Compare models with one command each:

    GRAIL_EMBED_MODEL=BAAI/bge-small-en-v1.5 python scripts/eval_retrieval.py
    GRAIL_EMBED_MODEL=BAAI/bge-base-en-v1.5  python scripts/eval_retrieval.py
    GRAIL_EMBED_MODEL=BAAI/bge-large-en-v1.5 python scripts/eval_retrieval.py
    GRAIL_EMBED_MODEL=intfloat/e5-large-v2   python scripts/eval_retrieval.py

The number picks the model, not the vibe.
"""
from __future__ import annotations
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import RAW_DIR, INSTRUMENT, EMBED_MODEL, ROOT
from grail.ingest.clause_parser import parse_text
from grail.ingest.loaders import load_source_text, clean_oj_text
from grail.ingest.linker import link_units
from grail.index.hybrid_index import HybridIndex

GOLD_PATH = os.path.join(ROOT, "data", "eval", "e1_gold.jsonl")
KS = (1, 3, 5, 10)


def build_index():
    pdfs = sorted(glob.glob(os.path.join(RAW_DIR, "*.pdf")))
    sources = pdfs or sorted(glob.glob(os.path.join(RAW_DIR, "*.txt")))
    units = []
    for p in sources:
        units.extend(parse_text(clean_oj_text(load_source_text(p)), INSTRUMENT))
    units = link_units(units)
    return HybridIndex.build(units)


def load_gold():
    with open(GOLD_PATH, encoding="utf-8") as fh:
        return [json.loads(l) for l in fh if l.strip()]


def main() -> None:
    gold = load_gold()
    index = build_index()
    ids = [u.id for u in index.units]
    id_set = set(ids)

    recall = {k: 0 for k in KS}
    rr_sum = 0.0
    misses = []

    for item in gold:
        golds = [g for g in item["gold_ids"]]
        for g in golds:
            if g not in id_set:
                print(f"  ! gold id not in corpus: {g}  (check parser id)")
        ranking = index.search(item["query"], allowed_idx=None)
        ranked_ids = [index.units[i].id for i, _ in ranking]
        best = None
        for pos, cid in enumerate(ranked_ids):
            if cid in golds:
                best = pos + 1
                break
        if best is None:
            misses.append((item.get("note", ""), golds))
            continue
        rr_sum += 1.0 / best
        for k in KS:
            if best <= k:
                recall[k] += 1

    n = len(gold)
    print(f"\nModel: {EMBED_MODEL}  |  backend: {index.backend}  |  queries: {n}")
    print("-" * 56)
    for k in KS:
        print(f"  recall@{k:<2}: {recall[k]/n:.2f}  ({recall[k]}/{n})")
    print(f"  MRR   : {rr_sum/n:.3f}")
    if misses:
        print("\n  misses:")
        for note, g in misses:
            print(f"    - {note}: {g}")


if __name__ == "__main__":
    main()
