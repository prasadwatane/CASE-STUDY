#!/usr/bin/env python
"""What can be said about the judge BEFORE any human reference exists.

    python scripts/preview_judge.py finance

NOT VALIDATION. Nothing here compares the judge with a human. It answers three
design questions that need no labels and that the judge calibration (CAL2) depends on:

1. How often does the judge agree with the rule-based baseline (S2b's
   comparator)? If almost always, S2b will be hard to win; if rarely, the two
   disagree on something the human reference will have to settle.
2. Is self-agreement (k = 5 runs at the pinned temperature) a usable score?
   How many distinct values does it take, what coverage can a gate on it reach,
   and where do non-unanimous items concentrate?
3. Given the coverage each candidate threshold reaches on the unlabelled docket,
   how many judge errors could a 300-item calibration set tolerate and still
   certify alpha = 0.05?
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import PROBE_DIR, RUN_DIR
from grail.annotate.agreement import agreement
from grail.gate.selective import coverage_on, max_errors_certifiable, threshold_grid
from grail.judge.baselines import rule_based
from grail.probe.schema import load_probes
from grail.run.store import load


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("domain", nargs="?", default="finance")
    ap.add_argument("--n-cal", type=int, default=300)
    a = ap.parse_args()
    run_dir = os.path.join(RUN_DIR, a.domain)
    probes = {p.id: p for p in load_probes(os.path.join(PROBE_DIR, a.domain, "probes.jsonl"))}
    resp = {}
    for r in load(os.path.join(run_dir, "responses.jsonl")):
        if r.dimension == "transparency" and not r.error:
            resp[(r.model_id, r.probe_id)] = r.response

    rows = []
    for f in sorted(glob.glob(os.path.join(run_dir, "judge_*.json"))):
        d = json.load(open(f))
        model = d["audited_model"]
        for it in d["items"]:
            p = probes[it["probe_id"]]
            text = resp.get((model, it["probe_id"]))
            if text is None:
                continue
            split = [c["key"] for c in it["conditions"]
                     if not c.get("settled_in_code") and c["agreement"] < 1.0]
            rows.append({"model": model.split("/")[-1], "probe": it["probe_id"],
                         "family": p.family, "judge": it["adequate"],
                         "self_agreement": it["self_agreement"],
                         "rule": rule_based(text, p.slots, p.family),
                         "split_conditions": split})

    decided = [r for r in rows if r["judge"] is not None]
    lab = lambda b: "adequate" if b else "inadequate"
    ag = agreement([lab(r["judge"]) for r in decided], [lab(r["rule"]) for r in decided])

    by_model = {}
    for m in sorted({r["model"] for r in decided}):
        sub = [r for r in decided if r["model"] == m]
        g = agreement([lab(r["judge"]) for r in sub], [lab(r["rule"]) for r in sub])
        by_model[m] = {"n": len(sub),
                       "judge_adequate": round(sum(r["judge"] for r in sub) / len(sub), 3),
                       "rule_adequate": round(sum(r["rule"] for r in sub) / len(sub), 3),
                       "raw": g.percent_agreement, "kappa": g.kappa, "ac1": g.ac1}

    sa = [r["self_agreement"] for r in rows if r["self_agreement"] is not None]
    score = [round(1 - x, 4) for x in sa]
    grid = threshold_grid(score)
    gate = []
    for tau in grid:
        cov = coverage_on(score, tau)
        n_acc = int(round(cov * a.n_cal))
        k = max_errors_certifiable(n_acc)
        gate.append({"tau": tau, "docket_coverage": round(cov, 4),
                     "accepted_of_300_if_srs": n_acc, "max_errors_certifiable": k,
                     "max_error_rate": round(k / n_acc, 4) if n_acc and k >= 0 else None})

    unan = [r for r in decided if r["self_agreement"] == 1.0]
    split = [r for r in decided if r["self_agreement"] is not None and r["self_agreement"] < 1.0]
    jq = lambda xs: round(sum(r["judge"] == r["rule"] for r in xs) / len(xs), 3) if xs else None
    split_cond = Counter(c for r in rows for c in r["split_conditions"])

    out = {"n_items": len(rows), "n_judge_undecided": len(rows) - len(decided),
           "judge_vs_rule": {"n": ag.n, "raw": ag.percent_agreement, "kappa": ag.kappa,
                             "kappa_ci": [ag.ci_low, ag.ci_high], "ac1": ag.ac1,
                             "ac1_ci": [ag.ac1_ci_low, ag.ac1_ci_high],
                             "confusion": ag.confusion, "marginals": ag.marginals},
           "by_model": by_model,
           "self_agreement_values": dict(sorted(Counter(round(x, 2) for x in sa).items())),
           "split_conditions": dict(split_conds) if (split_conds := split_cond) else {},
           "judge_rule_agreement_when_unanimous": jq(unan), "n_unanimous": len(unan),
           "judge_rule_agreement_when_split": jq(split), "n_split": len(split),
           "gate_grid": gate}
    json.dump(out, open(os.path.join(run_dir, "judge_preview.json"), "w"), indent=1)
    print(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    main()
