"""Put probes to a model and log the raw responses, then print the pilot report.

Start small. `--limit 50` draws a seeded, dimension-stratified sample and answers
the four questions the full run's sizing depends on. Running everything before
knowing the parse rate is how you pay for 3492 unparseable responses.

The log is append-only and cached, so re-running skips anything already paid for
and a bigger `--limit` later only buys the difference.

Run:
    python scripts/run_probes.py finance --limit 50 --stub
    python scripts/run_probes.py finance --limit 50 --base-url http://localhost:8000/v1 \
                                 --model llama-3.1-70b-instruct
    python scripts/run_probes.py finance --report-only
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import (FAIRNESS_PRIMARY_STRATUM, PROBE_DIR, PROBE_SEED,
                    ROBUSTNESS_ASSUMED_FLIP_RATE, ROBUSTNESS_PSI, RUN_DIR,
                    RUN_PARAMS)
from grail.probe.schema import load_probes
from grail.run.client import HTTPModel, StubModel, VLLMModel
from grail.run.pilot import report
from grail.run.runner import run
from grail.run.store import load, verify_chain


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("domain", nargs="?", default="finance")
    ap.add_argument("--probes", default=None)
    ap.add_argument("--limit", type=int, default=None, help="pilot size")
    ap.add_argument("--model", default=None, help="model id (pinned into every record)")
    ap.add_argument("--base-url", default=None, help="OpenAI-compatible endpoint")
    ap.add_argument("--local", default=None, metavar="HF_REPO_ID",
                    help="run vLLM in this process (no server); batches every prompt")
    ap.add_argument("--max-model-len", type=int, default=4096)
    ap.add_argument("--gpu-mem", type=float, default=0.85)
    ap.add_argument("--eager", action="store_true",
                    help="skip torch.compile (slower, avoids native-extension crashes)")
    ap.add_argument("--api-key", default=os.environ.get("GRAIL_API_KEY", ""))
    ap.add_argument("--temperature", type=float, default=RUN_PARAMS["temperature"])
    ap.add_argument("--stub", action="store_true", help="dry run, not evidence")
    ap.add_argument("--seed", type=int, default=PROBE_SEED)
    ap.add_argument("--out", default=None)
    ap.add_argument("--report-only", action="store_true")
    ap.add_argument("--verify", action="store_true")
    args = ap.parse_args()

    out_dir = args.out or os.path.join(RUN_DIR, args.domain)
    log_path = os.path.join(out_dir, "responses.jsonl")
    probes_path = args.probes or os.path.join(PROBE_DIR, args.domain, "probes.jsonl")

    if args.verify:
        ok, reason = verify_chain(load(log_path))
        print(("VALID: " if ok else "INVALID: ") + reason)
        raise SystemExit(0 if ok else 1)

    if not os.path.exists(probes_path):
        raise SystemExit(f"No probe set at {probes_path}. Run generate_probes.py first.")
    probes = load_probes(probes_path)

    if not args.report_only:
        if args.local:
            print(f"Loading {args.local} into this process (first run downloads weights)…")
            model = VLLMModel(args.local, max_model_len=args.max_model_len,
                              gpu_memory_utilization=args.gpu_mem,
                              enforce_eager=args.eager)
        elif args.base_url:
            model = HTTPModel(args.model or "unnamed-model", args.base_url, args.api_key)
        elif args.stub:
            model = StubModel()
        else:
            raise SystemExit(
                "Give --local <hf-repo-id> to run vLLM in-process, --base-url for a "
                "served endpoint, or --stub for a dry run.")

        _, summary = run(probes, model, log_path,
                         params={"temperature": args.temperature},
                         limit=args.limit, seed=args.seed, allow_stub=args.stub,
                         on_progress=lambda i, n: print(f"  ... {i}/{n}", flush=True))
        print(f"Responses -> {log_path}")
        print(f"  model    : {summary.model_id}  params {summary.params}")
        print(f"  requested: {summary.requested}   called {summary.called}   "
              f"cached {summary.cached}   errors {summary.errors}")
        print(f"  elapsed  : {summary.seconds}s")
        if getattr(model, "is_stub", False):
            print("  *** STUB RUN — NOT EVIDENCE ***")

    records = load(log_path)
    if not records:
        raise SystemExit("No responses logged yet.")

    rep = report(probes, records, assumed_flip_rate=ROBUSTNESS_ASSUMED_FLIP_RATE,
                 psi=ROBUSTNESS_PSI,
                 primary_stratum=FAIRNESS_PRIMARY_STRATUM.get(args.domain, "marginal"))
    with open(os.path.join(out_dir, "pilot_report.json"), "w", encoding="utf-8") as fh:
        json.dump(rep, fh, ensure_ascii=False, indent=2)

    print("\n=== PILOT REPORT ===")
    print(f"  responses    : {rep['n_responses']}  (errors {rep['n_errors']})")
    print(f"  parse rate   : {rep['parse_rate']:.0%}   refusals {rep['refusal_rate']:.0%}")
    for dim, st in sorted(rep["by_dimension"].items()):
        print(f"      {dim:<13} parsed {st['parsed']:>4}  refused {st['refused']:>3}  "
              f"unparseable {st['unparseable']:>3}")
    if rep["base_rate"]:
        b = rep["base_rate"]
        print(f"  base rate    : {b['rate']:.1%} favourable (n={b['n']}); "
              f"variance is {b['variance_ratio']}x the p=0.5 assumption")
    if rep["flip_rate"]:
        f = rep["flip_rate"]
        print(f"  flip rate    : {f['rate']:.1%} of {f['comparisons']} comparisons "
              f"(assumed {f['assumed']:.0%})")
        if f["base_cases_needed_at_measured_rate"]:
            print(f"                 -> {f['base_cases_needed_at_measured_rate']} "
                  "base cases needed at the measured rate")
    if rep.get("fairness_discordance"):
        d = rep["fairness_discordance"]
        print(f"  fairness pairs: {d['pairs']} in '{d['stratum']}'  "
              f"discordant {d['discordant']} ({d['rate']:.2%})  "
              f"p={d['sign_test_p']}")
        if not d["can_reject_at_all"]:
            print(f"                 -> below the floor of "
                  f"{d['min_discordant_to_ever_reject']} discordant pairs; needs "
                  f"~{d['pairs_needed_at_measured_rate']} pairs in this stratum")
    if rep["controls"]:
        for name, c in sorted(rep["controls"].items()):
            print(f"  control      : {name} {c}")
    if rep.get("effective_power"):
        e = rep["effective_power"]
        print(f"  power        : at the measured base rate, n=393/arm detects "
              f"{e['gap_detectable_at_n393']} pp")
    if rep["verdicts"]:
        print("\n  THINGS TO FIX BEFORE THE FULL RUN:")
        for v in rep["verdicts"]:
            print(f"    • {v}")
    else:
        print("\n  No blocking issues found in the pilot.")


if __name__ == "__main__":
    main()
