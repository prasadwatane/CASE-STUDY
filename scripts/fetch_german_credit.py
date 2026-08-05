"""Fetch the Statlog (German Credit) dataset once, and record where it came from.

The data is not vendored into this repository. It is CC BY 4.0 and could be, but
fetching it explicitly means the provenance file is written at the same moment
the data arrives, rather than being reconstructed later from memory.

Run:  python scripts/fetch_german_credit.py
      python scripts/fetch_german_credit.py --verify
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from grail.probe.records import COLUMNS, SOURCE, load_records, strength

URL = "https://archive.ics.uci.edu/ml/machine-learning-databases/statlog/german/german.data"
DEST = os.path.join("data", "records", "german_credit", "german.data")


def describe(path: str) -> dict:
    records = load_records(path)
    labels = {"repaid": sum(1 for r in records if r["repaid"]),
              "defaulted": sum(1 for r in records if not r["repaid"])}
    genders = {}
    for r in records:
        genders[r["recorded_gender"]] = genders.get(r["recorded_gender"], 0) + 1
    scores = sorted(strength(r) for r in records)
    n = len(scores)
    return {
        "n_records": n,
        "label_split": labels,
        "recorded_gender_split": genders,
        "strength_score": {"min": scores[0], "max": scores[-1],
                           "tercile_cuts": [scores[n // 3], scores[2 * n // 3]]},
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dest", default=DEST)
    ap.add_argument("--url", default=URL)
    ap.add_argument("--verify", action="store_true")
    args = ap.parse_args()

    if args.verify:
        if not os.path.exists(args.dest):
            raise SystemExit(f"Nothing at {args.dest}. Run without --verify first.")
        info = describe(args.dest)
        ok = info["n_records"] == SOURCE["n_expected"]
        print(("VALID: " if ok else "UNEXPECTED: ")
              + f"{info['n_records']} records (expected {SOURCE['n_expected']})")
        print(json.dumps(info, indent=2))
        raise SystemExit(0 if ok else 1)

    os.makedirs(os.path.dirname(args.dest), exist_ok=True)
    print(f"Fetching {args.url}")
    with urllib.request.urlopen(args.url, timeout=60) as resp:
        raw = resp.read()
    with open(args.dest, "wb") as fh:
        fh.write(raw)

    info = describe(args.dest)
    if info["n_records"] != SOURCE["n_expected"]:
        print(f"WARNING: expected {SOURCE['n_expected']} records, got {info['n_records']}")

    provenance = {
        "dataset": SOURCE["name"],
        "url": args.url,
        "licence": SOURCE["licence"],
        "attribution": "Hofmann, H. (1994). Statlog (German Credit Data). "
                       "UCI Machine Learning Repository.",
        "vintage_note": SOURCE["vintage"],
        "fetched_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "bytes": len(raw),
        "columns": COLUMNS,
        **info,
    }
    with open(os.path.join(os.path.dirname(args.dest), "PROVENANCE.json"), "w",
              encoding="utf-8") as fh:
        json.dump(provenance, fh, indent=2)

    print(f"  -> {args.dest}  ({len(raw)} bytes, sha256 {provenance['sha256'][:16]}…)")
    print(f"  {info['n_records']} records; repaid {info['label_split']['repaid']}, "
          f"defaulted {info['label_split']['defaulted']}")
    print(f"  strength terciles cut at {info['strength_score']['tercile_cuts']}")
    print("\nThe label records OBSERVED REPAYMENT. It is ground truth for robustness "
          "accuracy; it is NOT a fairness reference.")


if __name__ == "__main__":
    main()
