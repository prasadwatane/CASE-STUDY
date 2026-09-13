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


def build_candidates(probes: list, responses: list, judges: list[dict],
                     dimension: str = "transparency",
                     models: list[str] | None = None) -> list[dict]:
    """Pair each probe with each model's response and tag which strata it belongs to.

    Three things here are load-bearing, and each was got wrong first time:

    **Only the dimension the judge actually judges.** The study measures
    judge-human agreement, so a rater must be shown the items the judge ruled
    on. Article 13(1) transparency is the only qualitative docket; a fairness
    probe's response is the single word APPROVE, and asking a human whether that
    explanation names a field is asking about an explanation that does not
    exist.

    **Matched by CONTENT HASH, never by probe id.** A probe regenerated with
    different text under the same id is a different question, and pairing its
    old response with the new prompt would show the rater a response to
    something they are not reading. This is the same failure that gave the jury
    a 1.27% estimate on five discordant pairs when the truth was 1.83% on
    sixty-six.

    **One candidate per (probe, model).** A probe answered by four models is
    four things to rate, not one. Keying on the probe alone silently kept
    whichever model happened to be last in the log, and the judge would then be
    validated on a quarter of its own docket.
    """
    by_hash: dict[str, list] = {}
    for r in responses:
        if r.error:
            continue
        if models and r.model_id not in models:
            continue
        by_hash.setdefault(r.probe_sha256, []).append(r)

    # judge verdicts, keyed by (audited model, probe id)
    verdicts: dict[tuple[str, str], dict] = {}
    for doc in judges:
        for v in doc.get("items", []):
            verdicts[(doc["audited_model"], v["probe_id"])] = v

    out = []
    for p in probes:
        if dimension and p.dimension != dimension:
            continue
        for rec in by_hash.get(p.content_sha256, []):
            strata = ["random"]
            v = verdicts.get((rec.model_id, p.id))
            if v:
                # Self-agreement, not "confidence": the judge reports how often
                # its k runs agreed, and that is the quantity worth stratifying
                # on. Items it was sure about and items it wavered on fail
                # differently, and a study that samples only the easy ones
                # measures the judge at its best rather than in general.
                agree = v.get("self_agreement", 0.0)
                strata.append("judge_high_confidence" if agree >= 0.8
                              else "judge_borderline")
                if v.get("adequate") is None:
                    strata.append("judge_undecided")
            out.append({
                "probe_id": p.id, "model_id": rec.model_id,
                "dimension": p.dimension,
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
    ap.add_argument("--judge", default=None, nargs="*",
                    help="judge verdict json files; default is every one found")
    ap.add_argument("--dimension", default="transparency",
                    help="only this dimension. The judge rules on Art 13(1) "
                         "transparency, so validating it on anything else "
                         "measures agreement about a different task.")
    ap.add_argument("--model", default=None, nargs="*",
                    help="limit to these audited models; default is all")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    out_dir = args.out or os.path.join(PROCESSED_DIR, "annotation", args.domain)
    probes = load_probes(os.path.join(PROBE_DIR, args.domain, "probes.jsonl"))
    responses = load_responses(os.path.join(RUN_DIR, args.domain, "responses.jsonl"))
    if not responses:
        raise SystemExit(
            "No responses logged yet. The annotation study rates model OUTPUTS, "
            "so run scripts/run_probes.py first.")

    paths = args.judge
    if paths is None or paths == []:
        import glob as _glob
        paths = sorted(_glob.glob(os.path.join(RUN_DIR, args.domain, "judge_*.json")))
    judges = [json.load(open(p, encoding="utf-8"))
              for p in paths if os.path.exists(p)]
    if not judges:
        print("WARNING: no judge verdicts found. Items will be sampled at "
              "random rather than stratified by how sure the judge was, which "
              "measures the judge on easy items as often as hard ones.")

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
    candidates = build_candidates(probes, responses, judges,
                                  dimension=args.dimension, models=args.model)
    if not candidates:
        raise SystemExit(
            f"No '{args.dimension}' responses to rate. Check the dimension and "
            "that the response log covers the models you asked for.")
    from collections import Counter
    print(f"candidates: {len(candidates)} ({args.dimension}) across "
          f"{len(Counter(c['model_id'] for c in candidates))} models")
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
