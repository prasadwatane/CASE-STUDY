"""Select items and export blinded annotation sheets.

Produces one CSV per rater plus a key file. The primary rater gets every item;
the second gets the overlap subset that κ is computed on. Neither sheet contains
the probe id, the model identity or any judge verdict.

Freeze the guidelines BEFORE running this. Their hash goes into the key file, so
a guideline edited after annotation began is detectable.

Run:
    python scripts/export_annotation.py finance --guidelines docs/annotation_guidelines.md
    python scripts/export_annotation.py finance --n 300 --overlap 120
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import PROBE_DIR, PROCESSED_DIR, RUN_DIR
from grail.annotate.agreement import n_for_kappa_lower_bound
from grail.annotate.study import StudyDesign, export, select
from grail.probe.schema import load_probes
from grail.run.store import load as load_responses

LABELS = ["adequate", "inadequate"]


def build_candidates(probes: list, responses: list, judge: dict | None) -> list[dict]:
    """Pair each probe with its response and tag which strata it belongs to."""
    by_probe = {r.probe_id: r for r in responses if not r.error}
    out = []
    for p in probes:
        rec = by_probe.get(p.id)
        if rec is None:
            continue
        strata = ["random"]
        if p.dimension == "fairness" and p.stratum == "marginal":
            strata.append("fairness_marginal")
        v = (judge or {}).get(p.id)
        if v:
            conf = v.get("confidence", 0.0)
            strata.append("judge_high_confidence" if conf >= 0.8 else "judge_borderline")
        out.append({
            "probe_id": p.id, "dimension": p.dimension,
            "criterion": p.expected_behavior, "prompt": p.prompt,
            "response": rec.response, "strata": strata,
        })
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("domain", nargs="?", default="finance")
    ap.add_argument("--n", type=int, default=300)
    ap.add_argument("--overlap", type=int, default=120)
    ap.add_argument("--seed", type=int, default=20260803)
    ap.add_argument("--guidelines", default=None)
    ap.add_argument("--judge", default=None, help="judge verdicts json, when it exists")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    out_dir = args.out or os.path.join(PROCESSED_DIR, "annotation", args.domain)
    probes = load_probes(os.path.join(PROBE_DIR, args.domain, "probes.jsonl"))
    responses = load_responses(os.path.join(RUN_DIR, args.domain, "responses.jsonl"))
    if not responses:
        raise SystemExit(
            "No responses logged yet. The annotation study rates model OUTPUTS, "
            "so run scripts/run_probes.py first.")

    judge = None
    if args.judge and os.path.exists(args.judge):
        with open(args.judge, encoding="utf-8") as fh:
            judge = json.load(fh)

    gsha = ""
    if args.guidelines:
        if not os.path.exists(args.guidelines):
            raise SystemExit(f"No guidelines at {args.guidelines}. Freeze them first.")
        gsha = hashlib.sha256(open(args.guidelines, "rb").read()).hexdigest()
    else:
        print("WARNING: no --guidelines given. Freeze and hash them before annotating, "
              "or you cannot show they were fixed in advance.")

    design = StudyDesign(domain=args.domain, n_items=args.n, n_overlap=args.overlap,
                         seed=args.seed, guidelines_sha256=gsha)
    candidates = build_candidates(probes, responses, judge)
    items = select(candidates, design)
    result = export(items, design, out_dir, LABELS)

    print(f"Annotation sheets -> {out_dir}")
    print(f"  rater A (primary): {result['n_primary']} items")
    print(f"  rater B (overlap): {result['n_second']} items")
    print(f"  key              : {os.path.basename(result['key'])}  (do not open until scored)")
    if gsha:
        print(f"  guidelines sha256: {gsha[:16]}…")
    if result["shortfall"]:
        print("  STRATUM SHORTFALL — these strata could not be filled:")
        for k, v in sorted(result["shortfall"].items()):
            print(f"    • {k}: {v} short")
        print("    Not topped up from elsewhere: a stratum quietly filled with random "
              "items is a study that thinks it measured something it did not.")
    need = n_for_kappa_lower_bound(0.61, 0.75)
    if args.overlap < need:
        print(f"\n  NOTE: {args.overlap} overlap items may be too few to put the LOWER "
              f"bound of κ above 0.61 (roughly {need} needed if the true κ is ~0.75).")


if __name__ == "__main__":
    main()
