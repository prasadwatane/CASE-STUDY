#!/usr/bin/env python
"""Adaptive vs static audit-budget allocation, by replay over the response log.

    python scripts/eval_allocation.py finance
    python scripts/eval_allocation.py finance --seeds 60 --out data/processed/runs/finance/allocation.json

Every response is already paid for, so a policy that would have sampled N units
is evaluated by scoring exactly N logged units. This compares ALLOCATIONS, not
probe sets: no policy here invents a probe the committed set does not contain.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import PROBE_DIR, RUN_DIR
from grail.allocate.replay import build_requirements, run_replay
from grail.jury.verdict import _parsed
from grail.probe.schema import load_probes
from grail.run.store import load


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("domain", nargs="?", default="finance")
    ap.add_argument("--seeds", type=int, default=40)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    run_dir = os.path.join(RUN_DIR, a.domain)
    probes = load_probes(os.path.join(PROBE_DIR, a.domain, "probes.jsonl"))
    records = load(os.path.join(run_dir, "responses.jsonl"))
    models = sorted({r.model_id for r in records if r.model_id and not r.error})
    print(f"{len(probes)} probes · {len(records)} responses · {len(models)} models")

    parsed_by_model = {}
    for m in models:
        parsed, match = _parsed(probes, records, m)
        if not parsed:
            print(f"  skip {m}: no hash-matched responses")
            continue
        parsed_by_model[m] = parsed
        print(f"  {m.split('/')[-1]:38s} matched {match['matched']:6d} "
              f"coverage {match['coverage']:.2f}")

    reqs = build_requirements(parsed_by_model)
    full = sum(r.n_available * r.cost_per_unit for r in reqs)
    print(f"\n{len(reqs)} requirement instances; full budget {full:,} prompts")
    for r in reqs:
        print(f"  {r.key:44s} units={r.n_available:5d} cost/unit={r.cost_per_unit}")

    budgets = [int(full * f) for f in (0.05, 0.10, 0.20, 0.30, 0.50, 0.75, 1.00)]
    rows = run_replay(reqs, budgets, seeds=a.seeds)

    from grail.allocate.replay import reference_verdicts
    ref = reference_verdicts(reqs)
    print("\nfull-budget reference verdicts:")
    for k, v in ref.items():
        print(f"  {k:44s} {v}")

    print(f"\n{'budget':>8} {'share':>6} | {'cov(st)':>8} {'cov(ad)':>8} {'delta':>7} "
          f"| {'fid(st)':>8} {'fid(ad)':>8} {'contra':>7} | {'ad spent':>9} {'saved':>7}")
    for i in range(0, len(rows), 2):
        st, ad = rows[i], rows[i + 1]
        print(f"{st['budget']:>8,} {st['budget']/full:>6.0%} | "
              f"{st['coverage']:>8.2%} {ad['coverage']:>8.2%} "
              f"{ad['coverage']-st['coverage']:>+7.2%} | "
              f"{st['fidelity']:>8.2%} {ad['fidelity']:>8.2%} "
              f"{ad['contradictions_max']:>7d} | {ad['spent']:>9,} "
              f"{1-ad['spent']/max(1,st['spent']):>7.0%}")

    out = a.out or os.path.join(run_dir, "allocation.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump({"domain": a.domain, "seeds": a.seeds, "full_budget": full,
                   "requirements": [{"key": r.key, "kind": r.kind,
                                     "units": r.n_available,
                                     "cost_per_unit": r.cost_per_unit} for r in reqs],
                   "rows": rows}, fh, indent=2)
    print(f"\n-> {out}")


if __name__ == "__main__":
    main()
