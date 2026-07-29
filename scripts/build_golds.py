"""Build the gold ledger for a domain: Green / Amber / escalated, with a split report.

Reads the frozen probe set, routes every probe that needs a reference answer, and
writes an append-only hash-chained ledger plus a report of the split and the
measured human leakage.

No real proposer is wired yet, so a real run needs one passed in code. The stub
path exists to keep the pipeline runnable offline and must be asked for
explicitly — its name is written into every record either way.

Run:
    python scripts/build_golds.py finance --probes path/to/probes.jsonl --stub
    python scripts/build_golds.py finance --verify
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import (GOLD_ALPHA, GOLD_DELTA, GOLD_DIR, GOLD_PROPOSER_K, PROBE_DIR,
                    PROBE_SEED_DIR)
from grail.gold.proposer import StubProposer
from grail.gold.router import build_golds
from grail.gold.schema import load_ledger, save_ledger, verify_chain
from grail.probe.generators.truthfulness import load_seed_bank
from grail.probe.schema import load_probes


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("domain", nargs="?", default="finance")
    ap.add_argument("--probes", default=None, help="probes.jsonl (default: the domain's frozen set)")
    ap.add_argument("--out", default=None)
    ap.add_argument("--alpha", type=float, default=GOLD_ALPHA)
    ap.add_argument("--delta", type=float, default=GOLD_DELTA)
    ap.add_argument("--k", type=int, default=GOLD_PROPOSER_K)
    ap.add_argument("--stub", action="store_true",
                    help="dry run with the offline stub proposer (not evidence)")
    ap.add_argument("--verify", action="store_true", help="check the ledger hash chain")
    args = ap.parse_args()

    out_dir = args.out or os.path.join(GOLD_DIR, args.domain)
    ledger_path = os.path.join(out_dir, "golds.jsonl")

    if args.verify:
        if not os.path.exists(ledger_path):
            raise SystemExit(f"No ledger at {ledger_path}.")
        ok, reason = verify_chain(load_ledger(ledger_path))
        print(("VALID: " if ok else "INVALID: ") + reason)
        raise SystemExit(0 if ok else 1)

    probes_path = args.probes or os.path.join(PROBE_DIR, args.domain, "probes.jsonl")
    if not os.path.exists(probes_path):
        raise SystemExit(f"No probe set at {probes_path}. Run generate_probes.py first.")
    probes = load_probes(probes_path)

    needing = [p for p in probes if p.gold_route in {"computed", "sourced", "structural"}]
    if not needing:
        print(f"No probe in {probes_path} carries a gold route — nothing to key.")
        print("Fairness, robustness and transparency are scored by comparison or by "
              "rubric, not against a reference answer, so this is expected for the "
              "committed finance checklist.")
        return

    items = load_seed_bank(PROBE_SEED_DIR)
    proposer = StubProposer()
    records, report = build_golds(
        items, probes, proposer, domain=args.domain, alpha=args.alpha,
        delta=args.delta, k=args.k, allow_stub=args.stub)

    save_ledger(records, ledger_path, report=report)

    print(f"Gold ledger -> {ledger_path}")
    print(f"  items       : {report['n_items']}")
    c, s = report["counts"], report["split"]
    print(f"  green       : {c['green']:>4}  ({s['green']:.0%})  computed or sourced, no model trusted")
    print(f"  amber       : {c['amber']:>4}  ({s['amber']:.0%})  proposed, conformally accepted")
    print(f"  escalated   : {c['escalated']:>4}  ({s['escalated']:.0%})  queued for a human")
    print(f"  leakage     : {report['human_leakage']:.0%} of items need a human")
    print(f"  proposer    : {report['proposer']}"
          + ("   [STUB — NOT EVIDENCE]" if report["proposer_is_stub"] else ""))
    cal = report["calibration"]
    if cal["certified"]:
        print(f"  gate        : accept when disagreement <= {cal['threshold']:.2f}; "
              f"selective error <= {cal['error_bound']:.4f} at "
              f"{1 - cal['delta']:.0%} confidence")
    else:
        print(f"  gate        : NOT CERTIFIED — {cal['reason']}")
    print(f"  ledger head : {str(report['ledger_head'])[:16]}…")
    for n in report["notes"]:
        print(f"    - {n}")


if __name__ == "__main__":
    main()
