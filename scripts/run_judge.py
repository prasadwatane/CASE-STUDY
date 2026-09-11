"""Judge the qualitative docket for one audited model, against the signed criterion.

The judge is the only place a language model touches a reported number, so the
run is hedged: it refuses a judge from a family it is grading, it grounds every
quotation in code, it judges each item k times and records the spread instead of
averaging it, and it never sees which model produced the response.

    python scripts/run_judge.py finance --model Qwen/Qwen2.5-7B-Instruct \\
        --judge mistralai/Mistral-Small-24B-Instruct-2501 --local
    python scripts/run_judge.py finance --model Qwen/Qwen2.5-7B-Instruct --stub

Output is a verdict per item plus a coverage summary. It does NOT decide whether
the judge can be trusted — the annotation study does that, against the
human-human ceiling. This only produces what that study will be compared with.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import (CHECKLIST_DIR, JUDGE_ESCALATE_BELOW, JUDGE_K,
                    JUDGE_MODEL, JUDGE_TEMPERATURE, PROBE_DIR, RUN_DIR)
from grail.judge.adjudicate import assert_disjoint, judge_items
from grail.judge.rubric import build
from grail.probe.schema import load_probes
from grail.run.client import HTTPModel, StubModel, VLLMModel
from grail.run.pilot import models_in
from grail.run.store import load

CLAUSE = "AIA:Art13(1)"


class StubJudge:
    """Offline stand-in. Never evidence; keeps the pipeline runnable."""
    id = "stub/judge-1.0"
    is_stub = True

    def generate(self, prompt: str, **params) -> str:
        # Answers from the case and response already embedded in the prompt, so
        # the loop can be exercised without a model. Deterministic on purpose.
        body = prompt.split("THE RESPONSE TO ASSESS")[-1]
        first = next((l.strip() for l in body.splitlines()
                      if l.strip() and not l.startswith('"""')), "")
        return json.dumps({"conditions": {
            "names_field": {"answer": "yes", "quote": first},
            "states_direction": {"answer": "yes" if first else "cannot_tell",
                                 "quote": first},
            "no_contradiction": {"answer": "yes", "quote": first}},
            "overall": "adequate"})


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("domain", nargs="?", default="finance")
    ap.add_argument("--model", required=True, help="the AUDITED model whose responses to judge")
    ap.add_argument("--judge", default=JUDGE_MODEL,
                    help="judge model id; pinned in config, must be a disjoint family")
    ap.add_argument("--local", action="store_true", help="load the judge via vLLM in-process")
    ap.add_argument("--base-url", default=None)
    ap.add_argument("--api-key", default=os.environ.get("GRAIL_API_KEY", ""))
    ap.add_argument("--stub", action="store_true", help="dry run, not evidence")
    ap.add_argument("-k", type=int, default=JUDGE_K, help="runs per item")
    ap.add_argument("--temperature", type=float, default=JUDGE_TEMPERATURE)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--gpu-mem", type=float, default=0.85)
    ap.add_argument("--eager", action="store_true")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    run_dir = os.path.join(RUN_DIR, args.domain)
    records = load(os.path.join(run_dir, "responses.jsonl"))
    probes = load_probes(os.path.join(PROBE_DIR, args.domain, "probes.jsonl"))
    signed = json.load(open(os.path.join(CHECKLIST_DIR, f"{args.domain}_signed.json"),
                            encoding="utf-8"))

    rubric = build(signed, CLAUSE)      # raises if the criterion is empty
    print(f"rubric: {rubric.citation} — {len(rubric.conditions)} conditions, "
          f"from a checklist signed by {signed['signature'].get('signer')}")

    if args.stub:
        judge = StubJudge()
    elif args.local:
        assert_disjoint(args.judge, models_in(records))
        print(f"loading judge {args.judge}…")
        judge = VLLMModel(args.judge, gpu_memory_utilization=args.gpu_mem,
                          enforce_eager=args.eager)
    elif args.base_url:
        assert_disjoint(args.judge or "unnamed", models_in(records))
        judge = HTTPModel(args.judge or "unnamed-judge", args.base_url, args.api_key)
    else:
        raise SystemExit("Give --local, --base-url, or --stub.")

    by_hash = {p.content_sha256: p for p in probes}
    docket = [(by_hash[r.probe_sha256], r) for r in records
              if r.model_id == args.model and not r.error
              and r.probe_sha256 in by_hash
              and by_hash[r.probe_sha256].dimension == "transparency"]
    if not docket:
        raise SystemExit(f"no transparency responses for '{args.model}' in this log")
    if args.limit:
        docket = docket[:args.limit]

    print(f"judging {len(docket)} items x k={args.k} = {len(docket)*args.k} calls, "
          f"temperature={args.temperature}\n")
    started = time.time()
    verdicts = judge_items(
        judge, rubric, [(p, r.response) for p, r in docket],
        k=args.k, temperature=args.temperature,
        on_progress=lambda i, n: print(f"  ... {i}/{n}", flush=True))
    print(f"  elapsed: {time.time() - started:.1f}s")

    decided = [v for v in verdicts if v.adequate is not None]
    adequate = [v for v in decided if v.adequate]
    low = [v for v in verdicts if v.self_agreement < JUDGE_ESCALATE_BELOW]
    ungrounded = sum(v.ungrounded_quotes for v in verdicts)

    out_path = args.out or os.path.join(
        run_dir, f"judge_{args.model.replace('/', '_')}.json")
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump({"audited_model": args.model, "judge": judge.id, "k": args.k,
                   "clause": CLAUSE, "rubric": rubric.as_dict(),
                   "checklist_sha256": signed["signature"]["content_sha256"],
                   "items": [v.as_dict() for v in verdicts]},
                  fh, ensure_ascii=False, indent=2)

    print(f"\n=== JUDGE — {args.model} judged by {judge.id} ===")
    print(f"  items            : {len(verdicts)}")
    print(f"  decided          : {len(decided)}  ({len(decided)/len(verdicts):.0%})")
    print(f"  adequate         : {len(adequate)} of {len(decided)}"
          + (f"  ({len(adequate)/len(decided):.1%})" if decided else ""))
    print(f"  low self-agreement: {len(low)}  -> escalate to a human annotator")
    print(f"  ungrounded quotes : {ungrounded}  (discarded before any vote)")
    if getattr(judge, "is_stub", False):
        print("\n  *** STUB JUDGE — NOT EVIDENCE ***")
    print(f"\n  A share of adequate responses is NOT yet an audit finding. It becomes")
    print(f"  one when judge-human agreement has been measured against the")
    print(f"  human-human ceiling. Until then this is an input to that study.")
    print(f"\n  verdicts -> {out_path}")


if __name__ == "__main__":
    main()
