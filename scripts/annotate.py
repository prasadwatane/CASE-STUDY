"""Label one item at a time, in the terminal. Writes as you go.

Editing the sheet by hand works, but a spreadsheet shows a two-thousand-character
prompt as a truncated cell and silently re-encodes the file on save. This reads
the same CSV, shows one item properly, takes a verdict, and rewrites the file
after every answer — so closing the window loses nothing.

    python scripts/annotate.py data/processed/annotation/pilot/annotation_rater_A.csv

It shows the APPLICATION first and the RESPONSE second, deliberately: reading the
response first frames how you read the case, and the guidelines ask for the other
order.

Nothing here tells you what to answer. The rules live in the frozen guidelines,
and a tool that nudged would be making the labels partly its own.
"""
from __future__ import annotations

import argparse
import csv
import os
import shutil
import sys
import textwrap

VERDICTS = {
    "1": "adequate",
    "2": "inadequate",
    "3": "cannot judge",
}
COLUMNS = ["item", "dimension", "criterion", "prompt", "response", "rating", "notes"]


def _wrap(text: str, width: int) -> str:
    out = []
    for para in (text or "").splitlines():
        out.append(textwrap.fill(para, width) if para.strip() else "")
    return "\n".join(out)


def _save(path: str, rows: list[dict]) -> None:
    """Write the whole sheet, atomically. Called after every single answer."""
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS)
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in COLUMNS})
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("sheet", help="annotation_rater_A.csv or _B.csv")
    ap.add_argument("--redo", action="store_true",
                    help="revisit items already rated")
    args = ap.parse_args()

    if not os.path.exists(args.sheet):
        raise SystemExit(f"No sheet at {args.sheet}")

    with open(args.sheet, encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))

    # One backup of the untouched sheet, once. Cheap insurance against a
    # mis-keyed session; never overwritten, so it stays the original.
    backup = args.sheet + ".original"
    if not os.path.exists(backup):
        shutil.copy2(args.sheet, backup)

    width = min(shutil.get_terminal_size((100, 40)).columns - 2, 100)
    todo = [i for i, r in enumerate(rows)
            if args.redo or not (r.get("rating") or "").strip()]
    done_already = len(rows) - len(todo)

    if not todo:
        print(f"All {len(rows)} items already rated. Use --redo to revisit.")
        return

    print(f"\n{len(todo)} items to rate ({done_already} already done).")
    print("Saved after every answer — you can stop any time and rerun.\n")

    for n, idx in enumerate(todo, start=1):
        r = rows[idx]
        print("=" * width)
        print(f"  ITEM {n} of {len(todo)}     {r['item']}")
        print("=" * width)
        print("\n--- THE APPLICATION ---\n")
        print(_wrap(r.get("prompt", ""), width))
        print("\n--- THE RESPONSE ---\n")
        print(_wrap(r.get("response", ""), width))
        print("\n" + "-" * width)
        if r.get("rating"):
            print(f"  (currently: {r['rating']})")
        print("  1 = adequate      2 = inadequate      3 = cannot judge")
        print("  s = skip for now  q = save and quit")

        while True:
            try:
                choice = input("  > ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                _save(args.sheet, rows)
                print("\n\nSaved. Rerun the same command to continue.")
                return
            if choice == "q":
                _save(args.sheet, rows)
                print(f"\nSaved to {args.sheet}. Rerun to continue.")
                return
            if choice == "s":
                break
            if choice in VERDICTS:
                r["rating"] = VERDICTS[choice]
                note = input("  note (optional, Enter to skip): ").strip()
                if note:
                    r["notes"] = note
                _save(args.sheet, rows)
                break
            print("  1, 2, 3, s or q.")
        print()

    rated = sum(1 for r in rows if (r.get("rating") or "").strip())
    print("=" * width)
    print(f"  {rated} of {len(rows)} rated.")
    if rated < len(rows):
        print("  Rerun the same command to finish the rest.")
    else:
        print(f"  Sheet complete -> {args.sheet}")
        print("  When BOTH raters are done:")
        print("    python scripts/score_annotation.py finance --dir "
              f"{os.path.dirname(args.sheet)}")
    print("=" * width)


if __name__ == "__main__":
    main()
