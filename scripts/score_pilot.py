#!/usr/bin/env python
"""Score an annotation pilot round with any number of raters.

    python scripts/score_pilot.py finance pilot_round1
    python scripts/score_pilot.py finance pilot_round1 --labels adequate inadequate "cannot judge"

Reads every rater_*.csv in data/annotation/<domain>/<round>/, writes
agreement.json + agreement.md beside them, prints the markdown. Exits 2 if an
undeclared label is found — declare it or fix the sheet; never score around it.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from grail.annotation.agreement import load_sheet, load_meta, score_study, render_markdown  # noqa: E402

DEFAULT_LABELS = ("adequate", "inadequate", "cannot judge")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("domain")
    ap.add_argument("round_name")
    ap.add_argument("--labels", nargs="+", default=list(DEFAULT_LABELS))
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()

    d = Path("data/annotation") / a.domain / a.round_name
    files = sorted(d.glob("rater_*.csv"))
    if len(files) < 2:
        print(f"need >=2 rater_*.csv in {d}", file=sys.stderr)
        return 2
    try:
        sheets = {f.stem.replace("rater_", ""): load_sheet(f, allowed=a.labels) for f in files}
    except ValueError as e:
        print(e, file=sys.stderr)
        return 2
    meta = load_meta(files[0])
    rep = score_study(sheets, meta, seed=a.seed)
    (d / "agreement.json").write_text(json.dumps(rep.to_dict(), indent=2))
    md = render_markdown(rep, f"Annotation agreement — {a.domain} / {a.round_name}")
    (d / "agreement.md").write_text(md)
    print(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
