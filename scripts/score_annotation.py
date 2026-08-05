"""Score completed annotation sheets: human ceiling first, then the judge.

Run:
    python scripts/score_annotation.py finance
    python scripts/score_annotation.py finance --judge data/processed/judge/finance.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import PROCESSED_DIR
from grail.annotate.report import format_report, score
from grail.annotate.study import load_sheet


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("domain", nargs="?", default="finance")
    ap.add_argument("--dir", default=None)
    ap.add_argument("--judge", default=None)
    ap.add_argument("--threshold", type=float, default=0.61)
    args = ap.parse_args()

    d = args.dir or os.path.join(PROCESSED_DIR, "annotation", args.domain)
    key_path = os.path.join(d, "KEY_do_not_open_until_scored.json")
    if not os.path.exists(key_path):
        raise SystemExit(f"No key file at {key_path}. Run export_annotation.py first.")
    with open(key_path, encoding="utf-8") as fh:
        key = json.load(fh)
    labels = key["allowed_labels"]

    sheets = {}
    for rater in ("A", "B"):
        path = os.path.join(d, f"annotation_rater_{rater}.csv")
        if not os.path.exists(path):
            raise SystemExit(f"Missing completed sheet: {path}")
        sheets[rater] = load_sheet(path, labels)
        s = sheets[rater]
        print(f"rater {rater}: {len(s['ratings'])} rated, {s['blank']} blank, "
              f"{len(s['invalid'])} invalid")
        for item, value in s["invalid"][:5]:
            print(f"    invalid label on {item}: {value!r} (allowed: {labels})")

    judge = None
    if args.judge and os.path.exists(args.judge):
        with open(args.judge, encoding="utf-8") as fh:
            raw = json.load(fh)
        tok = {meta["probe_id"]: t for t, meta in key["items"].items()}
        judge = {tok[pid]: v["verdict"] for pid, v in raw.items() if pid in tok}

    rep = score(sheets["A"]["ratings"], sheets["B"]["ratings"], key,
                judge=judge, threshold=args.threshold)
    print()
    print(format_report(rep))

    out = os.path.join(d, "agreement_report.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(rep, fh, ensure_ascii=False, indent=2)
    print(f"\n-> {out}")


if __name__ == "__main__":
    main()
