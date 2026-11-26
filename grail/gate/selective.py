"""The selective-automation gate on the judge path (calibration CAL2).

The judge emits a label and a nonconformity score s(x) (higher = less sure).
The gate accepts the judge's label when s(x) <= tau and sends the item to a
human otherwise. What is certified is the selective error

    R(tau) = P( judge label != reference | s(x) <= tau )

with an exact one-sided Clopper–Pearson bound at confidence 1 - delta.

Three choices are fixed here because they decide whether the bound means
anything:

1. **The threshold grid comes from the UNLABELLED docket.** Candidates are
   quantiles of s over all judged items, computed before any calibration label
   exists, then de-duplicated. A score with many ties (self-agreement over five
   runs takes six values) collapses the grid; that is reported, not hidden.

2. **Fixed-sequence testing, strictest first.** Candidates are tested in order of
   increasing tau (increasing coverage), each at level delta, stopping at the
   first failure. Because the order is fixed in advance the family-wise error is
   delta with no Bonferroni penalty (Angelopoulos et al., Learn then Test).
   `grail.gold.conformal.calibrate` keeps the older Bonferroni search for the gold
   pipeline; this module does not change it.

3. **A stratified sample is not the docket.** The annotation study oversamples
   hard items. A single bound over the pooled sample certifies the risk on THAT
   mixture, not on the docket the gate will run on. `stratified_bound` bounds each
   stratum at delta / S and recombines them with docket weights and docket
   coverage — both computable without labels, because s(x) needs none.

The guarantee is marginal and holds only for items exchangeable with the
calibration set: same docket, models, probe families, judge version and prompt.
It says nothing about legal conformity.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

from grail.gold.conformal import clopper_pearson_upper

DEFAULT_QUANTILES = tuple(round(0.50 + 0.05 * i, 2) for i in range(11))   # 0.50 … 1.00


def _quantile(sorted_xs: list[float], q: float) -> float:
    if not sorted_xs:
        raise ValueError("empty")
    i = min(len(sorted_xs) - 1, max(0, int(round(q * (len(sorted_xs) - 1)))))
    return sorted_xs[i]


def threshold_grid(unlabelled_scores: list[float],
                   quantiles: tuple = DEFAULT_QUANTILES) -> list[float]:
    """Pre-registered candidates, strictest first, ties collapsed."""
    xs = sorted(unlabelled_scores)
    grid = sorted({_quantile(xs, q) for q in quantiles})
    return grid


def coverage_on(scores: list[float], tau: float) -> float:
    return sum(1 for s in scores if s <= tau) / len(scores) if scores else 0.0


@dataclass
class GateResult:
    certified: bool
    tau: float | None
    alpha: float
    delta: float
    n_calibration: int
    n_accepted: int
    n_errors: int
    error_bound: float | None
    coverage_calibration: float | None
    coverage_docket: float | None
    tested: list
    reason: str = ""

    def as_dict(self) -> dict:
        return asdict(self)


def fixed_sequence(cal: list[tuple[float, bool]], grid: list[float],
                   alpha: float = 0.05, delta: float = 0.05,
                   docket_scores: list[float] | None = None) -> GateResult:
    """cal = [(score, judge_was_correct)]. Returns the loosest tau that passed."""
    tested, best = [], None
    for tau in grid:
        acc = [ok for s, ok in cal if s <= tau]
        k = sum(1 for ok in acc if not ok)
        ub = clopper_pearson_upper(k, len(acc), delta) if acc else 1.0
        tested.append({"tau": tau, "n_accepted": len(acc), "errors": k,
                       "bound": round(ub, 5), "passed": ub <= alpha})
        if ub > alpha:
            break
        best = (tau, len(acc), k, ub)
    n = len(cal)
    if best is None:
        return GateResult(False, None, alpha, delta, n, 0, 0, None, None, None, tested,
                          "the strictest candidate already fails; nothing is certified")
    tau, na, k, ub = best
    return GateResult(True, tau, alpha, delta, n, na, k, round(ub, 5),
                      round(na / n, 4) if n else None,
                      round(coverage_on(docket_scores, tau), 4) if docket_scores else None,
                      tested, f"selective error <= {ub:.4f} at confidence {1 - delta:.2f}")


def stratified_bound(cal_by_stratum: dict[str, list[tuple[float, bool]]],
                     docket_by_stratum: dict[str, list[float]], tau: float,
                     delta: float = 0.05) -> dict:
    """Docket-level selective-error bound from a stratified calibration sample.

    Each stratum's error among accepted items is bounded at delta / S. The docket's
    selective error is the coverage-weighted mixture of stratum errors, with the
    weights (stratum share x stratum coverage) taken from the unlabelled docket.
    Replacing each stratum error by its bound gives a bound that holds with
    probability at least 1 - delta (union bound).
    """
    strata = [s for s in docket_by_stratum if docket_by_stratum[s]]
    S = len(strata)
    total = sum(len(docket_by_stratum[s]) for s in strata)
    num = den = 0.0
    per = {}
    for s in strata:
        w = len(docket_by_stratum[s]) / total
        phi = coverage_on(docket_by_stratum[s], tau)
        acc = [ok for sc, ok in cal_by_stratum.get(s, []) if sc <= tau]
        k = sum(1 for ok in acc if not ok)
        ub = clopper_pearson_upper(k, len(acc), delta / S) if acc else 1.0
        per[s] = {"weight": round(w, 4), "coverage": round(phi, 4),
                  "n_accepted": len(acc), "errors": k, "bound": round(ub, 5)}
        num += w * phi * ub
        den += w * phi
    return {"tau": tau, "delta": delta, "strata": per,
            "docket_coverage": round(den, 4),
            "bound": round(num / den, 5) if den else None}


def risk_coverage(cal: list[tuple[float, bool]], delta: float = 0.05) -> list[dict]:
    """Empirical selective error and its bound at every distinct score."""
    out = []
    for tau in sorted({s for s, _ in cal}):
        acc = [ok for s, ok in cal if s <= tau]
        k = sum(1 for ok in acc if not ok)
        out.append({"tau": tau, "coverage": round(len(acc) / len(cal), 4),
                    "error": round(k / len(acc), 4), "bound":
                    round(clopper_pearson_upper(k, len(acc), delta), 5)})
    return out


def max_errors_certifiable(n_accepted: int, alpha: float = 0.05, delta: float = 0.05) -> int:
    """Largest error count among n accepted items that still certifies alpha (-1: none)."""
    k = -1
    while k + 1 <= n_accepted and clopper_pearson_upper(k + 1, n_accepted, delta) <= alpha:
        k += 1
    return k
