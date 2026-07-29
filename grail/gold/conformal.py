"""The conformal gate — when may a model-proposed gold be accepted unchecked?

An Amber gold is proposed by a model, so accepting one without a human is only
defensible if the error rate *among the accepted ones* is bounded. That is a
selective-risk guarantee, and it is built here in three steps:

1. **Score.** Ask the proposer k times and score the item by disagreement,
   `1 - modal share`. Low score means the proposer said the same thing k times.
2. **Calibrate.** On items whose true answer is already known for free (the
   computed ones), record (score, was the modal proposal correct). For a
   candidate threshold t, look at the calibration items with score <= t and put
   an exact Clopper-Pearson upper bound on their error rate.
3. **Certify.** Take the largest t whose bound is still <= alpha. Because that
   maximisation searches every candidate threshold, each test uses
   `delta / m` (Bonferroni over the m candidates), so the guarantee holds
   simultaneously and is not an artefact of picking the luckiest cut.

The important behaviour is the refusal. With few calibration points, no
threshold can be certified — even with zero observed errors, the exact bound
from n points cannot fall below alpha until n >= log(delta)/log(1-alpha)
(59 points for alpha = delta = 0.05). In that case this module certifies nothing
and every Amber candidate escalates to a human. An uncertifiable bound is
reported as an uncertifiable bound; it is never rounded up into a number.

Everything is exact integer arithmetic plus a bisection, so there is no scipy
dependency and no approximation to argue about.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, asdict


def binom_cdf(k: int, n: int, p: float) -> float:
    """P(X <= k) for X ~ Binomial(n, p), computed exactly term by term."""
    if k < 0:
        return 0.0
    if k >= n:
        return 1.0
    if p <= 0.0:
        return 1.0
    if p >= 1.0:
        return 0.0
    total = 0.0
    for i in range(k + 1):
        total += math.comb(n, i) * (p ** i) * ((1.0 - p) ** (n - i))
    return min(1.0, total)


def clopper_pearson_upper(k: int, n: int, delta: float) -> float:
    """Exact upper confidence bound on a binomial rate: k errors out of n.

    The bound is the p at which observing k or fewer errors would itself have
    probability delta. Found by bisection on the exact CDF, which is monotone
    decreasing in p.
    """
    if n <= 0:
        return 1.0
    if k >= n:
        return 1.0
    lo, hi = 0.0, 1.0
    for _ in range(200):
        mid = (lo + hi) / 2.0
        if binom_cdf(k, n, mid) > delta:
            lo = mid
        else:
            hi = mid
    return hi


def min_calibration_n(alpha: float, delta: float) -> int:
    """Fewest calibration points that could ever certify a rate of `alpha`.

    Best case is zero observed errors, where the bound is 1 - delta^(1/n); it
    first drops to alpha at n = log(delta) / log(1 - alpha). This is a floor and
    assumes a single candidate threshold — with m candidates and the Bonferroni
    correction the real requirement is larger.
    """
    if not 0 < alpha < 1 or not 0 < delta < 1:
        raise ValueError("alpha and delta must be in (0, 1)")
    return math.ceil(math.log(delta) / math.log(1.0 - alpha))


@dataclass
class Calibration:
    certified: bool
    threshold: float | None      # accept a proposal iff its score <= threshold
    alpha: float
    delta: float
    delta_adjusted: float | None  # delta / m after the Bonferroni correction
    n_calibration: int
    n_selected: int              # calibration items the threshold would accept
    n_errors: int                # of those, how many the proposer got wrong
    error_bound: float | None    # certified upper bound on selective error
    min_n_required: int
    reason: str = ""

    def as_dict(self) -> dict:
        return asdict(self)


def calibrate(observations: list[tuple[float, bool]], alpha: float,
              delta: float) -> Calibration:
    """Choose the largest score threshold whose selective error is provably <= alpha.

    `observations` is [(nonconformity score, was the proposal correct), ...].
    """
    n = len(observations)
    floor_n = min_calibration_n(alpha, delta)

    if n == 0:
        return Calibration(False, None, alpha, delta, None, 0, 0, 0, None, floor_n,
                           "no calibration data: nothing can be certified")

    candidates = sorted({score for score, _ in observations})
    m = len(candidates)
    delta_adj = delta / m

    best = None
    for t in candidates:
        selected = [ok for score, ok in observations if score <= t]
        if not selected:
            continue
        errors = sum(1 for ok in selected if not ok)
        bound = clopper_pearson_upper(errors, len(selected), delta_adj)
        if bound <= alpha:
            best = (t, len(selected), errors, bound)

    if best is None:
        return Calibration(
            False, None, alpha, delta, delta_adj, n, 0, 0, None, floor_n,
            f"no threshold certifies selective error <= {alpha} at confidence "
            f"{1 - delta:.2f} from {n} calibration points "
            f"(at least {floor_n} are needed even with zero observed errors, "
            f"and more once the {m} candidate thresholds are corrected for)")

    t, n_sel, errors, bound = best
    return Calibration(
        True, t, alpha, delta, delta_adj, n, n_sel, errors, bound, floor_n,
        f"selective error <= {bound:.4f} at confidence {1 - delta:.2f} "
        f"for proposals scoring <= {t:.4f}")


def nonconformity(proposals: list[str]) -> tuple[float, str, float]:
    """(score, modal proposal, modal share) for k proposals. Score = 1 - modal share."""
    if not proposals:
        return 1.0, "", 0.0
    counts: dict[str, int] = {}
    for p in proposals:
        counts[p] = counts.get(p, 0) + 1
    # ties broken by the proposal text so the result never depends on ordering
    modal = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
    share = counts[modal] / len(proposals)
    return 1.0 - share, modal, share
