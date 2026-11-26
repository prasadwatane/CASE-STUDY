"""Human-agreement study on insurance premium explanations (guideline v2.0).

Five steps, in this order. Each one prints what to do next.

    # 1. draw 240 main + 20 calibration items, write blinded sheets and HTML packets
    python scripts/human_agreement.py export insurance

    # 2. the arbiter fills calibration_arbiter_key.html; each rater does calibration_rater_X.html
    python scripts/human_agreement.py calibration insurance      # pass = 18 of 20

    # 3. both raters do rater_A.html / rater_B.html (all 240 items each)
    python scripts/human_agreement.py score insurance            # agreement.md + arbiter sheet

    # 4. the arbiter does arbiter.html (disputed items only, labels hidden)
    python scripts/human_agreement.py reference insurance        # reference_labels.json (R*)

Rater files come back as CSV (the packet's "Download CSV" button) and go into
data/processed/annotation/<domain>/ under the same file name.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import PROBE_DIR, PROCESSED_DIR, RUN_DIR  # noqa: E402
from grail.annotate import insurance_study as S  # noqa: E402
from grail.probe.schema import load_probes  # noqa: E402
from grail.run.store import load as load_responses  # noqa: E402
from grail.annotate.packet import packet  # noqa: E402

GUIDELINE = os.path.join("docs", "annotation", "guideline_insurance_v2.0.md")

def _dir(args) -> str:
    return args.out or os.path.join(PROCESSED_DIR, "annotation", args.domain)


def cmd_export(args) -> None:
    if not os.path.exists(args.guideline):
        raise SystemExit(f"No guideline at {args.guideline}.")
    probes = load_probes(os.path.join(PROBE_DIR, args.domain, "probes.jsonl"))
    responses = load_responses(os.path.join(RUN_DIR, args.domain, "responses.jsonl"))
    cands = S.candidates(probes, responses, models=args.model)
    if not cands:
        raise SystemExit("No transparency responses yet. Run the explanation prompts first:\n"
                         f"  bash scripts/run_models.sh {args.domain} --dimension transparency")
    models = sorted({c["model_id"] for c in cands})
    print(f"candidates: {len(cands)} explanations from {len(models)} models")
    for m in models:
        print(f"   {m}: {sum(1 for c in cands if c['model_id'] == m)}")
    design = S.Design(per_cell=args.per_cell, calibration=args.calibration, seed=args.seed,
                      guideline_sha256=S.sha256_file(args.guideline))
    main, calib, short = S.draw(cands, design)
    paths = S.write_study(main, calib, design, _dir(args))
    titles = {"rater_A": "Rater A - main sample", "rater_B": "Rater B - main sample",
              "calibration_A": "Rater A - calibration (20 items)",
              "calibration_B": "Rater B - calibration (20 items)",
              "calibration_key": "Arbiter - calibration answer key (20 items)"}
    for k, t in titles.items():
        packet(paths[k], args.guideline, t)
    print(f"\nmain sample: {len(main)} items   calibration: {len(calib)} items")
    if short:
        print("SHORTFALL (cells with fewer items than planned):", short)
    print(f"guideline sha256: {design.guideline_sha256[:16]}...")
    print(f"\nWritten to {_dir(args)}:")
    for k in titles:
        print(f"   {os.path.basename(paths[k]).replace('.csv', '.html')}")
    print("\nNext: the arbiter fills calibration_arbiter_key.html first; then send each rater "
          "their calibration_rater_X.html. Return files are CSVs with the same names.")


def cmd_calibration(args) -> None:
    d = _dir(args)
    key = S.load_sheet(os.path.join(d, "calibration_arbiter_key.csv"))
    passed = True
    for r in args.raters:
        p = os.path.join(d, f"calibration_rater_{r}.csv")
        if not os.path.exists(p):
            print(f"rater {r}: no sheet yet ({os.path.basename(p)})")
            passed = False
            continue
        res = S.check_calibration(S.load_sheet(p), key)
        passed &= res["passed"]
        print(f"rater {r}: {res['correct']}/{res['n']} match the key "
              f"(need {res['needed']}) -> {'PASS' if res['passed'] else 'NOT YET'}")
        for m in res["misses"]:
            print(f"     {m['item']} ({m['request']}): rater {m['rater']}, key {m['key']}")
    print("\nNext: " + ("send rater_A.html and rater_B.html (240 items each)." if passed else
          "discuss the RULE behind each miss (never the item), clarify the guideline if needed "
          "(new version, new hash), and repeat calibration on fresh items."))


def cmd_score(args) -> None:
    d = _dir(args)
    key = json.load(open(os.path.join(d, S.KEY_FILE), encoding="utf-8"))
    a = S.load_sheet(os.path.join(d, "rater_A.csv"), require_complete=not args.partial)
    b = S.load_sheet(os.path.join(d, "rater_B.csv"), require_complete=not args.partial)
    rep = S.score(a, b, key, iterations=args.iterations)
    rep["sheet_sha256"] = {"rater_A": S.sha256_file(os.path.join(d, "rater_A.csv")),
                           "rater_B": S.sha256_file(os.path.join(d, "rater_B.csv"))}
    with open(os.path.join(d, "agreement.json"), "w", encoding="utf-8") as fh:
        json.dump(rep, fh, indent=2)
    md = S.render(rep)
    with open(os.path.join(d, "agreement.md"), "w", encoding="utf-8") as fh:
        fh.write(md)
    n = S.write_arbiter_sheet(rep, os.path.join(d, "rater_A.csv"), os.path.join(d, "arbiter.csv"))
    if n:
        packet(os.path.join(d, "arbiter.csv"), args.guideline, f"Arbiter - {n} disputed items")
    print(md)
    print(f"-> {os.path.join(d, 'agreement.md')}   arbiter sheet: {n} items (arbiter.html)")


def cmd_reference(args) -> None:
    d = _dir(args)
    key = json.load(open(os.path.join(d, S.KEY_FILE), encoding="utf-8"))
    a = S.load_sheet(os.path.join(d, "rater_A.csv"))
    b = S.load_sheet(os.path.join(d, "rater_B.csv"))
    arb_path = os.path.join(d, "arbiter.csv")
    arb = S.load_sheet(arb_path) if os.path.exists(arb_path) else {}
    ref = S.reference(a, b, arb, key)
    with open(os.path.join(d, "reference_labels.json"), "w", encoding="utf-8") as fh:
        json.dump(ref, fh, indent=2)
    waiting = sum(1 for v in ref.values() if v["label"] is None)
    print(f"R*: {len(ref)} items ({waiting} still waiting for the arbiter) -> reference_labels.json")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("export", "calibration", "score", "reference"):
        p = sub.add_parser(name)
        p.add_argument("domain", nargs="?", default="insurance")
        p.add_argument("--out", default=None, help="study folder (default data/processed/annotation/<domain>)")
        p.add_argument("--guideline", default=GUIDELINE)
        if name == "export":
            p.add_argument("--per-cell", type=int, default=30, help="items per model and request type")
            p.add_argument("--calibration", type=int, default=20)
            p.add_argument("--seed", type=int, default=20261125)
            p.add_argument("--model", nargs="*", default=None)
        if name == "calibration":
            p.add_argument("--raters", nargs="*", default=["A", "B"])
        if name == "score":
            p.add_argument("--partial", action="store_true", help="score the items rated so far")
            p.add_argument("--iterations", type=int, default=4000)
    args = ap.parse_args()
    {"export": cmd_export, "calibration": cmd_calibration,
     "score": cmd_score, "reference": cmd_reference}[args.cmd](args)


if __name__ == "__main__":
    main()
