"""Score one audited model's responses into clause-traced findings.

Deterministic end to end: no model is consulted, so the headline effects do not
depend on anything that could have been trained on the applications it is
grading. Run it as often as you like; the answer is a function of the response
log and the probe set alone.

    python scripts/run_jury.py finance --model Qwen/Qwen2.5-7B-Instruct
    python scripts/run_jury.py finance --list
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import FAIRNESS_ALPHA, FAIRNESS_PRIMARY_STRATUM, PROBE_DIR, RUN_DIR
from grail.jury.verdict import CONFIRMATORY, INSTRUMENT, deliberate
from grail.probe.schema import load_probes
from grail.run.pilot import models_in
from grail.run.store import load, verify_chain

ROLE_MARK = {CONFIRMATORY: "**", INSTRUMENT: "  ", "exploratory": "  "}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("domain", nargs="?", default="finance")
    ap.add_argument("--model", default=None, help="model id; omit with one model in the log")
    ap.add_argument("--list", action="store_true", help="show models present and exit")
    ap.add_argument("--alpha", type=float, default=FAIRNESS_ALPHA)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    run_dir = os.path.join(RUN_DIR, args.domain)
    records = load(os.path.join(run_dir, "responses.jsonl"))
    if not records:
        raise SystemExit("No responses logged yet.")
    probes = load_probes(os.path.join(PROBE_DIR, args.domain, "probes.jsonl"))

    present = models_in(records)
    if args.list:
        for m in present:
            print(f"  {m}   {sum(1 for r in records if r.model_id == m)} responses")
        return

    ok, reason = verify_chain(records)
    print(("chain VALID: " if ok else "chain INVALID: ") + reason)
    if not ok:
        raise SystemExit("Refusing to score a response log that does not verify.")

    model = args.model or (present[0] if len(present) == 1 else None)
    if model is None:
        raise SystemExit(f"{len(present)} models in this log — pass --model. "
                         f"Present: {', '.join(present)}")

    rep = deliberate(probes, records, model,
                     primary_stratum=FAIRNESS_PRIMARY_STRATUM.get(args.domain, "marginal"),
                     alpha=args.alpha)

    out_path = args.out or os.path.join(
        run_dir, f"jury_{model.replace('/', '_')}.json")
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(rep, fh, ensure_ascii=False, indent=2)

    print(f"\n=== JURY — {model} ===")
    print(f"  {rep['n_parsed']} parsed responses   alpha {rep['alpha']}   "
          f"primary stratum '{rep['primary_stratum']}'\n")
    print(f"  {'':2} {'dim':<11}{'stratum':<9}{'estimand':<50}"
          f"{'estimate':>10}{'95% interval':>20}{'p':>11}")
    print("  " + "-" * 111)
    for f in rep["findings"]:
        p = f"{f['p_value']:.2e}" if f["p_value"] is not None else "—"
        ci = "[{:+.2f}, {:+.2f}]".format(f["ci_low"] * 100, f["ci_high"] * 100)
        print(f"  {ROLE_MARK.get(f['role'], '  ')} {f['dimension'][:10]:<11}"
              f"{f['stratum'][:8]:<9}{f['estimand'][:48]:<50}"
              f"{f['estimate'] * 100:>9.2f}%{ci:>20}{p:>11}")
    print("\n  ** = pre-registered confirmatory endpoint; all else is descriptive")

    print(f"\n  controls: {rep['instrument_summary']['controls_fired']} of "
          f"{rep['instrument_summary']['controls_evaluated']} fired")
    if rep["caveats"]:
        print("\n  READ BEFORE QUOTING ANY NUMBER ABOVE:")
        for c in rep["caveats"]:
            print(f"    • {c}")
    print(f"\n  findings -> {out_path}")


if __name__ == "__main__":
    main()
