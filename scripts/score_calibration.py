"""Score the v1.1 calibration exercise against the guideline's answer key.

Calibration is training, not evidence (annotation protocol §3): it checks that a
rater applies the frozen-candidate guideline the way its worked examples do. Its
scores enter no agreement statistic.

    python scripts/score_calibration.py data/processed/annotation/calibration/calibration_rater_A.csv

Pass: at least 18 of 20 match the key, and every `inadequate` cites a rule
(E1-E3, C1-C4) in the notes column. A miss is fixed by clarifying the rule in the
guideline before freezing, never by coaching the rater on the item.
"""
from __future__ import annotations

import csv
import json
import os
import re
import sys

KEY = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "data", "processed", "annotation", "calibration", "answer_key.json")
RULE = re.compile(r"\b[EC][1-4]\b")


def score(sheet: str, key_path: str = KEY) -> dict:
    key = json.load(open(key_path, encoding="utf-8"))["verdicts"]
    rows = list(csv.DictReader(open(sheet, encoding="utf-8")))
    out = {"n": 0, "match": 0, "missing": [], "misses": [], "uncited": []}
    for r in rows:
        want = key.get(r["item"])
        if want is None:
            continue
        out["n"] += 1
        got = (r.get("rating") or "").strip().lower()
        if not got:
            out["missing"].append(r["item"])
        elif got == want["verdict"]:
            out["match"] += 1
        else:
            out["misses"].append({"item": r["item"], "rated": got, "key": want["verdict"],
                                  "key_reason": want["reason"]})
        if got == "inadequate" and not RULE.search(r.get("notes") or ""):
            out["uncited"].append(r["item"])
    out["pass"] = (out["match"] >= out["n"] - 2 and not out["missing"]
                   and not out["uncited"])
    return out


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    res = score(sys.argv[1])
    print(json.dumps(res, indent=2))
    print("PASS" if res["pass"] else "NOT YET: clarify the rule behind each miss, then re-run")
