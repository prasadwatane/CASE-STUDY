"""Scoring the annotation study — ceiling first, always.

The order of this report is deliberate. The human–human agreement comes first,
before any judge number appears, because it is the ceiling: if two trained people
following the same frozen guidelines only reach κ = 0.65, then a judge reaching
0.65 has matched the best achievable on that task, and reporting the judge number
first invites the reader to measure it against 1.0 instead.

That reframing also decides what counts as a result. A dimension where humans
cannot agree is not a dimension where the judge failed — it is a dimension shown
not to be reliably automatable, which is a finding with a number attached.

The judge is therefore reported twice: raw agreement with the human labels, and
the same figure as a share of the ceiling. Only the second is interpretable.
"""
from __future__ import annotations

from grail.annotate.agreement import agreement, interpret


def _pairs(a: dict, b: dict) -> tuple[list[str], list[str], list[str]]:
    shared = sorted(set(a) & set(b))
    return [a[k] for k in shared], [b[k] for k in shared], shared


def score(rater_a: dict, rater_b: dict, key: dict,
          judge: dict | None = None, threshold: float = 0.61,
          seed: int = 20260803) -> dict:
    """Human ceiling, then per-dimension κ, then the judge against that ceiling."""
    items = key.get("items", {})
    dims = {tok: meta.get("dimension", "unassigned") for tok, meta in items.items()}

    va, vb, shared = _pairs(rater_a, rater_b)
    overall = agreement(va, vb, seed=seed)

    out: dict = {
        "n_double_annotated": len(shared),
        "n_primary_only": len(set(rater_a) - set(rater_b)),
        "ceiling": {
            "kappa": overall.kappa,
            "ci": [overall.ci_low, overall.ci_high],
            "percent_agreement": overall.percent_agreement,
            "expected_agreement": overall.expected_agreement,
            "interpretation": interpret(overall.kappa),
            "undefined_reason": overall.undefined_reason,
            "meets_threshold": overall.meets(threshold),
            "threshold": threshold,
        },
        "by_dimension": {},
        "judge": None,
        "notes": [],
    }

    if overall.undefined_reason:
        out["notes"].append(f"ceiling: {overall.undefined_reason}")
    elif not overall.meets(threshold):
        out["notes"].append(
            f"The human ceiling does not clear κ ≥ {threshold} at the lower bound "
            f"(κ = {overall.kappa:.3f}, CI [{overall.ci_low:.3f}, {overall.ci_high:.3f}]). "
            "No judge can be shown to exceed a ceiling that has not itself been "
            "established — either the guidelines need sharpening or the dimension "
            "is not reliably automatable, and the second of those is a finding.")

    # per dimension
    by_dim: dict[str, tuple[list, list]] = {}
    for tok in shared:
        d = dims.get(tok, "unassigned")
        pa, pb = by_dim.setdefault(d, ([], []))
        pa.append(rater_a[tok])
        pb.append(rater_b[tok])
    for d, (pa, pb) in sorted(by_dim.items()):
        ag = agreement(pa, pb, seed=seed)
        out["by_dimension"][d] = {
            "n": ag.n, "kappa": ag.kappa, "ci": [ag.ci_low, ag.ci_high],
            "percent_agreement": ag.percent_agreement,
            "interpretation": interpret(ag.kappa),
            "meets_threshold": ag.meets(threshold),
            "undefined_reason": ag.undefined_reason,
        }
        if ag.n < 30:
            out["by_dimension"][d]["warning"] = (
                f"only {ag.n} double-annotated items — the interval is too wide "
                "to support a claim about this dimension")

    # judge against the ceiling, never against 1.0
    if judge:
        jv, hv, js = _pairs(judge, rater_a)
        if js:
            ja = agreement(jv, hv, seed=seed)
            ceiling = overall.kappa
            share = (round(ja.kappa / ceiling, 4)
                     if (ja.kappa is not None and ceiling not in (None, 0)) else None)
            out["judge"] = {
                "n": ja.n, "kappa": ja.kappa, "ci": [ja.ci_low, ja.ci_high],
                "percent_agreement": ja.percent_agreement,
                "share_of_ceiling": share,
                "interpretation": interpret(ja.kappa),
            }
            if share is not None and share >= 0.95:
                out["notes"].append(
                    f"The judge reaches {share:.0%} of the human ceiling. At that "
                    "point the limit is the task, not the judge — further judge "
                    "tuning cannot be shown to help.")
    return out


def format_report(rep: dict) -> str:
    L = []
    L.append("=== HUMAN CEILING (reported first, by design) ===")
    c = rep["ceiling"]
    if c["kappa"] is None:
        L.append(f"  kappa      : undefined — {c['undefined_reason']}")
    else:
        L.append(f"  kappa      : {c['kappa']:.3f}  CI [{c['ci'][0]:.3f}, {c['ci'][1]:.3f}]"
                 f"   ({c['interpretation']})")
    L.append(f"  raw agreement {c['percent_agreement']:.1%}   "
             f"expected by chance {c['expected_agreement']:.1%}")
    L.append(f"  double-annotated: {rep['n_double_annotated']}   "
             f"primary only: {rep['n_primary_only']}")
    L.append(f"  meets κ ≥ {c['threshold']} at the lower bound: "
             f"{'YES' if c['meets_threshold'] else 'NO'}")

    L.append("\n=== BY DIMENSION ===")
    for d, s in sorted(rep["by_dimension"].items()):
        k = "undefined" if s["kappa"] is None else f"{s['kappa']:.3f}"
        ci = ("" if s["kappa"] is None
              else f"  CI [{s['ci'][0]:.3f}, {s['ci'][1]:.3f}]")
        L.append(f"  {d:<14} n={s['n']:<4} kappa={k}{ci}  ({s['interpretation']})")
        if s.get("warning"):
            L.append(f"      ! {s['warning']}")

    if rep["judge"]:
        j = rep["judge"]
        L.append("\n=== JUDGE vs HUMAN (against the ceiling, not against 1.0) ===")
        L.append(f"  kappa      : {j['kappa']:.3f}  CI [{j['ci'][0]:.3f}, {j['ci'][1]:.3f}]")
        if j["share_of_ceiling"] is not None:
            L.append(f"  that is {j['share_of_ceiling']:.0%} of the human ceiling")

    if rep["notes"]:
        L.append("\n=== NOTES ===")
        for n in rep["notes"]:
            L.append(f"  • {n}")
    return "\n".join(L)
