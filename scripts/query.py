"""Eval-time retrieval demo.

Given a target-document snippet, retrieve the relevant obligations plus their
definitions and exceptions.

Run:  python scripts/query.py "the model refused a loan to an applicant based on a credit score"
"""
from __future__ import annotations
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from grail.index.hybrid_index import HybridIndex
from grail.retrieve.retriever import Retriever


def main() -> None:
    query = " ".join(sys.argv[1:]) or (
        "the system evaluated the creditworthiness of an applicant and may be "
        "biased against a protected group")
    index = HybridIndex.load()
    retriever = Retriever(index)
    results = retriever.retrieve(query)

    print(f"\nTARGET DOCUMENT:\n  {query}\n")
    print(f"RETRIEVED {len(results)} obligation(s):\n")
    for r in results:
        d = r.as_dict()
        print(f"• {d['citation']}  [{d['scope_partition']}]  (score {d['score']})")
        print(f"    {d['text']}")
        if d["chapeau"]:
            print(f"    chapeau: {d['chapeau']}")
        for de in d["definitions"]:
            print(f"    ├ def {de['citation']}: {de['term']}")
        for ex in d["exceptions"]:
            print(f"    └ exception {ex['citation']}: {ex['text'][:90]}...")
        print()

    # machine-readable form (what the evaluator/judge consumes)
    print("JSON:")
    print(json.dumps([r.as_dict() for r in results], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
