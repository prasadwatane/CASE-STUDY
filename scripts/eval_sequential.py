#!/usr/bin/env python
"""RQ3: static vs uncorrected adaptive vs sequentially valid adaptive allocation.

    python scripts/eval_sequential.py finance --part null          # error rates under a known truth
    python scripts/eval_sequential.py finance --part replay --budgets 0.05 0.10
    python scripts/eval_sequential.py finance --part report        # merge parts -> sequential.json / .md

Two experiments, because the replay alone cannot show error control: it has no
ground truth, only the full-budget verdict.

  null    Simulated requirements whose true parameter sits exactly where a
          determinate verdict is wrong. Measures the false-verdict rate of each
          policy directly.
  replay  The 16 real requirements (4 models x 3 fairness strata + robustness),
          resampled from the logged responses, at matched budgets. Measures
          coverage, fidelity against the full-budget verdict, contradictions
          and spend.

Parts are written separately so the replay can be run one budget at a time.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import PROBE_DIR, RUN_DIR
from grail.allocate.replay import Requirement, build_requirements, reference_verdicts
from grail.allocate.sequential import (PRIMARY_POLICY, compare_policies, null_error_rates,
                                      s4_primary)

FRACTIONS = (0.05, 0.10, 0.20, 0.30, 0.50, 0.75, 1.00)


def load_requirements(domain: str) -> list[Requirement]:
    run_dir = os.path.join(RUN_DIR, domain)
    cache = os.path.join(run_dir, "allocation_units.json")
    if os.path.exists(cache):
        reqs = [Requirement(r["key"], r["kind"], r["model"], r["stratum"],
                            [tuple(u) if r["kind"] == "fairness" else (u[0], list(u[1]))
                             for u in r["units"]], r["cost_per_unit"])
                for r in json.load(open(cache))["requirements"]]
        return reqs
    from grail.jury.verdict import _parsed
    from grail.probe.schema import load_probes
    from grail.run.store import load
    probes = load_probes(os.path.join(PROBE_DIR, domain, "probes.jsonl"))
    records = load(os.path.join(run_dir, "responses.jsonl"))
    models = sorted({r.model_id for r in records if r.model_id and not r.error})
    parsed_by_model = {}
    for m in models:
        parsed, _ = _parsed(probes, records, m)
        if parsed:
            parsed_by_model[m] = parsed
    reqs = build_requirements(parsed_by_model)
    with open(cache, "w") as fh:
        json.dump({"requirements": [
            {"key": r.key, "kind": r.kind, "model": r.model, "stratum": r.stratum,
             "cost_per_unit": r.cost_per_unit, "units": r.units} for r in reqs]}, fh)
    return reqs


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("domain", nargs="?", default="finance")
    ap.add_argument("--part", choices=["null", "replay", "report"], required=True)
    ap.add_argument("--budgets", type=float, nargs="*", default=list(FRACTIONS))
    ap.add_argument("--seeds", type=int, default=40)
    ap.add_argument("--sims", type=int, default=1000)
    a = ap.parse_args()
    out_dir = os.path.join(RUN_DIR, a.domain, "sequential")
    os.makedirs(out_dir, exist_ok=True)

    if a.part == "null":
        # Simulated audits are sized like the real requirements: the median
        # number of DISTINCT units per requirement (repeated applicants count
        # once, as in the jury). Until 23 Nov 2026 these were fixed at 948 and
        # 725, the sizes of the credit set before repeats were removed.
        reqs = load_requirements(a.domain)
        med = lambda xs: sorted(xs)[len(xs) // 2] if xs else None
        n_fair = med([r.n_available for r in reqs if r.kind == "fairness"]) or 948
        n_rob = med([r.n_available for r in reqs if r.kind == "robustness"]) or 725
        res = {}
        for kind, n in (("fairness_null0", n_fair), ("fairness_margin", n_fair),
                        ("robustness_tol", n_rob)):
            res[kind] = {"n_units": n, "sims": a.sims,
                         "rates": null_error_rates(kind, n, a.sims)}
            print(kind, res[kind]["rates"])
        json.dump(res, open(os.path.join(out_dir, "null.json"), "w"), indent=1)
        return

    reqs = load_requirements(a.domain)
    full = sum(r.n_available * r.cost_per_unit for r in reqs)
    if a.part == "replay":
        for f in a.budgets:
            rows = compare_policies(reqs, [int(full * f)], seeds=a.seeds)
            json.dump(rows, open(os.path.join(out_dir, f"replay_{f:.2f}.json"), "w"), indent=1)
            for r in rows:
                print(f"{f:.2f} {r['policy']:16s} cov {r['coverage']['mean']:.3f} "
                      f"fid {r['fidelity']['mean']:.3f} contra {r['contradictions']['mean']:.2f} "
                      f"spent {r['spent']['mean']:.0f} {r.get('S4', '')}", flush=True)
        return

    # report
    rows = []
    for p in sorted(glob.glob(os.path.join(out_dir, "replay_*.json"))):
        rows += json.load(open(p))
    null = json.load(open(os.path.join(out_dir, "null.json")))
    ref = reference_verdicts(reqs)
    json.dump({"domain": a.domain, "full_budget": full, "seeds": a.seeds,
               "reference_verdicts": ref, "null": null, "replay": rows},
              open(os.path.join(RUN_DIR, a.domain, "sequential.json"), "w"), indent=1)
    write_markdown(a.domain, full, ref, null, rows, a.seeds)


def write_markdown(domain, full, ref, null, rows, seeds):
    L = ["# RQ3 — sequential allocation results", "",
         f"Domain `{domain}` · {len(ref)} requirements · full budget {full:,} prompts · "
         f"{seeds} replay seeds. Produced by `scripts/eval_sequential.py`.", "",
         "## 1. Error rates under a known truth (simulation)", "",
         "Share of simulated audits ending in a **false** determinate verdict. "
         "`fairness_null0`: true difference 0, any FAIL is false (nominal 0.05). "
         "`fairness_margin`: true difference = margin, any PASS is false (nominal 0.05). "
         "`robustness_tol`: true flip rate = tolerance, PASS and FAIL both false "
         "(nominal 0.05 per side, 0.10 total).", "",
         "| truth | n | static | adaptive (uncorrected) | adaptive + CS | adaptive + OBF spending | adaptive + Pocock spending |",
         "|---|---|---|---|---|---|---|"]
    for kind, v in null.items():
        r = v["rates"]
        L.append(f"| {kind} | {v['n_units']} | " + " | ".join(
            f"{r[p]['false_rate']:.3f}" for p in
            ("static", "adaptive", "adaptive_cs", "adaptive_obf", "adaptive_pocock")) + " |")
    L += ["", "Share of the same audits reaching **any** determinate verdict "
          "(how often each rule commits at all):", "",
          "| truth | static | adaptive | CS | OBF | Pocock |", "|---|---|---|---|---|---|"]
    for kind, v in null.items():
        r = v["rates"]
        L.append(f"| {kind} | " + " | ".join(
            f"{r[p]['determinate_rate']:.3f}" for p in
            ("static", "adaptive", "adaptive_cs", "adaptive_obf", "adaptive_pocock")) + " |")
    L += ["", "## 2. Replay over the logged responses", "",
          "Mean over seeds, with the 2.5–97.5% range over seeds in brackets. Fidelity is "
          "against the static full-budget verdict. S4: corrected fidelity ≥ 0.90 × static "
          "AND spend ≤ 0.80 × static, judged on the seed-range bounds.", "",
          "| budget | policy | coverage | fidelity | contradictions (mean / max) | spend | fidelity ÷ static | spend ÷ static | S4 |",
          "|---|---|---|---|---|---|---|---|---|"]
    fmt = lambda s: f"{s['mean']:.2f} [{s['lo']:.2f}, {s['hi']:.2f}]"
    for r in sorted(rows, key=lambda x: (x["budget"], x["policy"])):
        L.append(f"| {r['budget'] / full:.0%} | {r['policy']} | {fmt(r['coverage'])} | "
                 f"{fmt(r['fidelity'])} | {r['contradictions']['mean']:.2f} / {r['contradictions_max']} | "
                 f"{r['spent']['mean']:,.0f} | "
                 + (fmt(r['fidelity_ratio_vs_static']) + " | " + fmt(r['spend_ratio_vs_static'])
                    + f" | {r['S4']}" if r["policy"] != "static" else "— | — | —") + " |")
    L += ["", "### S4 under both readings, with coverage relative to static", "",
          "`range` = per-seed 2.5–97.5% range (how one audit run could come out; the reading "
          "the code applies). `mean CI` = bootstrap CI of the mean over seeds (expected "
          "behaviour). Coverage ÷ static is the mean ratio with its CI — S4 does not "
          "constrain it, which is why it is shown.", "",
          "**Primary (pre-registered, OPEN 5):** mean CI with a coverage condition "
          "(coverage ÷ static ≥ 0.90), primary policy `adaptive_obf`.", "",
          "| budget | policy | **S4 primary** | S4 (range) | S4 (mean CI, no coverage) | fidelity ÷ static, mean CI | spend ÷ static, mean CI | coverage ÷ static |",
          "|---|---|---|---|---|---|---|---|"]
    ci = lambda s: f"{s['mean']:.2f} [{s['lo']:.2f}, {s['hi']:.2f}]"
    for r in sorted(rows, key=lambda x: (x["budget"], x["policy"])):
        if r["policy"] == "static":
            continue
        prim = r.get("S4_primary") or s4_primary(
            r["fidelity_ratio_mean_ci"], r["spend_ratio_mean_ci"], r["coverage_ratio_vs_static"])
        mark = " ◀ primary policy" if r["policy"] == PRIMARY_POLICY else ""
        L.append(f"| {r['budget'] / full:.0%} | {r['policy']}{mark} | **{prim}** | {r['S4']} | {r['S4_mean_ci']} | "
                 f"{ci(r['fidelity_ratio_mean_ci'])} | {ci(r['spend_ratio_mean_ci'])} | "
                 f"{ci(r['coverage_ratio_vs_static'])} |")
    L += ["", "## 3. Full-budget reference verdicts", "",
          "| requirement | verdict |", "|---|---|"]
    L += [f"| {k} | {v} |" for k, v in ref.items()]
    open(os.path.join(RUN_DIR, domain, "sequential.md"), "w").write("\n".join(L) + "\n")
    print("written sequential.json / sequential.md")


if __name__ == "__main__":
    main()
