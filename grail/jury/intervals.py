"""Interval estimators for the jury — exact and score methods, no Wald.

Every number the audit reports carries an interval, and the interval has to be
trustworthy at the counts that actually occur rather than at the counts a
textbook assumes. This audit produces small cells by construction: matched pairs
mostly agree, so the entire fairness signal lives in a few dozen discordant
pairs out of several thousand. That is precisely where Wald intervals and
chi-square tests misbehave — undercovering, and in the worst case placing a
bound outside [0, 1].

So the rule here is exact or score methods throughout:

* `wilson`            — a single rate. Wald undercovers badly below about 5%.
* `clopper_pearson`   — a single rate, guaranteed conservative. Used where the
                        quantity is bounded and near an endpoint.
* `newcombe_diff`     — difference of two INDEPENDENT rates, built from Wilson
                        limits rather than a pooled normal approximation.
* `paired_diff`       — difference of two MATCHED rates, by inverting the
                        likelihood ratio. This is the fairness primary endpoint.
* `exact_mcnemar`     — the paired test itself, as an exact binomial on the
                        discordant pairs. The chi-square form is not valid when
                        a discordant cell is small, which is the normal case.

Everything is standard library. An audit whose numbers cannot be reproduced
without a scientific-Python stack is worse off for it.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from grail.gold.conformal import binom_cdf

Z95 = 1.959963984540054
CHI2_95 = 3.841458820694124      # the 95% point of chi-square on 1 df


def _z(alpha: float) -> float:
    """Two-sided normal quantile, by bisection on the error function."""
    if not 0 < alpha < 1:
        raise ValueError("alpha must be in (0, 1)")
    target = 1.0 - alpha / 2.0
    lo, hi = 0.0, 40.0
    for _ in range(200):
        mid = (lo + hi) / 2
        if 0.5 * (1 + math.erf(mid / math.sqrt(2))) < target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


@dataclass(frozen=True)
class Interval:
    point: float
    low: float
    high: float
    method: str

    def excludes(self, value: float) -> bool:
        """Does the interval exclude `value`? For a difference, usually 0."""
        return value < self.low or value > self.high

    def as_dict(self) -> dict:
        return {"point": round(self.point, 6), "low": round(self.low, 6),
                "high": round(self.high, 6), "method": self.method}


# --- one rate ---------------------------------------------------------------
def wilson(k: int, n: int, alpha: float = 0.05) -> Interval:
    """Score interval for a single proportion.

    Preferred over Wald everywhere: it cannot leave [0, 1], it behaves at k = 0
    and k = n, and its coverage near the boundaries is far closer to nominal —
    which matters here because rates like 2% discordance are the normal case.
    """
    if n <= 0:
        raise ValueError("n must be positive")
    z = _z(alpha)
    p = k / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return Interval(p, max(0.0, centre - half), min(1.0, centre + half), "wilson")


def clopper_pearson(k: int, n: int, alpha: float = 0.05) -> Interval:
    """Exact (conservative) interval for a single proportion.

    Guarantees at least nominal coverage, at the cost of being wider than
    Wilson. Used where a conservative statement is the point — the share of
    discordant pairs falling one way, for instance, which sits near 1.
    """
    if n <= 0:
        raise ValueError("n must be positive")

    def _solve(pred) -> float:
        lo, hi = 0.0, 1.0
        for _ in range(200):
            mid = (lo + hi) / 2
            if pred(mid):
                hi = mid
            else:
                lo = mid
        return (lo + hi) / 2

    low = 0.0 if k == 0 else _solve(
        lambda p: 1.0 - binom_cdf(k - 1, n, p) > alpha / 2)
    high = 1.0 if k == n else _solve(
        lambda p: binom_cdf(k, n, p) < alpha / 2)
    return Interval(k / n, low, high, "clopper-pearson")


# --- two independent rates --------------------------------------------------
def newcombe_diff(k1: int, n1: int, k2: int, n2: int,
                  alpha: float = 0.05) -> Interval:
    """Newcombe's hybrid-score interval for p1 - p2, independent samples.

    Built from each arm's Wilson limits rather than from a pooled normal
    approximation, so it inherits Wilson's boundary behaviour. This is the
    aggregate approval-gap estimand — reported alongside the paired one, and
    deliberately not instead of it: they answer different questions.
    """
    a = wilson(k1, n1, alpha)
    b = wilson(k2, n2, alpha)
    p1, p2 = k1 / n1, k2 / n2
    lower = (p1 - p2) - math.sqrt((p1 - a.low) ** 2 + (b.high - p2) ** 2)
    upper = (p1 - p2) + math.sqrt((a.high - p1) ** 2 + (p2 - b.low) ** 2)
    return Interval(p1 - p2, max(-1.0, lower), min(1.0, upper), "newcombe")


# --- two matched rates ------------------------------------------------------
def _paired_loglik(a: int, b: int, c: int, d: int, delta: float) -> float:
    """Max log-likelihood of the 2x2 paired table with p10 - p01 fixed at delta.

    Parameterised as p01 = q, p10 = q + delta; the concordant mass 1 - 2q - delta
    splits between the two concordant cells in the observed ratio, which is its
    unconstrained optimum. That leaves a one-dimensional profile in q, solved by
    golden section.
    """
    n = a + b + c + d
    if n == 0:
        return -math.inf
    lo = max(0.0, -delta) + 1e-12
    hi = (1.0 - abs(delta)) / 2 - 1e-12
    if hi <= lo:
        return -math.inf

    conc = a + d
    tail = 0.0
    if conc:
        if a:
            tail += a * math.log(a / conc)
        if d:
            tail += d * math.log(d / conc)

    def f(q: float) -> float:
        s = 1 - 2 * q - delta
        if s <= 0 or q <= 0 or q + delta <= 0:
            return -math.inf
        v = tail
        if conc:
            v += conc * math.log(s)
        if b:
            v += b * math.log(q + delta)
        if c:
            v += c * math.log(q)
        return v

    for _ in range(120):
        m1 = lo + 0.381966 * (hi - lo)
        m2 = lo + 0.618034 * (hi - lo)
        if f(m1) < f(m2):
            lo = m1
        else:
            hi = m2
    return f((lo + hi) / 2)


def paired_diff(a: int, b: int, c: int, d: int, alpha: float = 0.05) -> Interval:
    """Profile-likelihood interval for p10 - p01 on matched pairs.

    `b` and `c` are the discordant counts — pairs where exactly one arm was
    favourable. `a` and `d` are the concordant ones and carry almost no
    information about the difference, which is a useful property to be able to
    demonstrate rather than assume: the interval is essentially unchanged
    however the concordant mass is split.

    Inverting the likelihood ratio rather than using a Wald standard error
    matters when a discordant cell is small. With 59 against 7 the two agree
    closely, and reporting that agreement is itself evidence; with 4 against 0,
    as an earlier run produced, Wald is not usable at all.
    """
    n = a + b + c + d
    if n == 0:
        raise ValueError("empty table")
    point = (b - c) / n
    mle = _paired_loglik(a, b, c, d, point)

    # The critical value must follow alpha. An earlier version hard-coded the
    # 95% point and silently returned a 95% interval whatever alpha was asked
    # for — which made the equivalence test, whose whole construction needs the
    # 1 - 2*alpha interval, quietly conservative. Chi-square on one degree of
    # freedom is the square of the normal quantile, so this is exact.
    crit = _z(alpha) ** 2

    def bound(far: float) -> float:
        lo, hi = far, point
        for _ in range(120):
            mid = (lo + hi) / 2
            if 2 * (mle - _paired_loglik(a, b, c, d, mid)) > crit:
                lo = mid
            else:
                hi = mid
        return (lo + hi) / 2

    return Interval(point, bound(-0.999999), bound(0.999999), "profile-likelihood")


EQUIVALENT = "equivalent"          # proven smaller than the tolerance
NOT_EQUIVALENT = "not_equivalent"  # proven larger than the tolerance
UNDETERMINED = "undetermined"      # the interval crosses the tolerance boundary


def _chi2_sf_1df(x: float) -> float:
    """Upper tail of chi-square on 1 degree of freedom, via the error function."""
    if x <= 0:
        return 1.0
    return math.erfc(math.sqrt(x / 2.0))


def equivalence_paired(a: int, b: int, c: int, d: int, margin: float,
                       alpha: float = 0.05) -> dict:
    """Two one-sided tests: is the paired difference SMALLER than `margin`?

    An ordinary test puts the null at zero, so a system passes whenever the data
    fail to convict it. That is the wrong way round for a conformity assessment.
    With a large enough sample every non-zero difference becomes detectable and
    everything fails; with a small one nothing is detectable and everything
    passes. In both cases the verdict is about the sample size.

    TOST inverts the burden. The null is that the difference is at least as
    large as the declared tolerance, and the system passes only on affirmative
    evidence that it is smaller. That is the standard used for bioequivalence
    since Schuirmann (1987), and it is the standard a regulator should want:
    the provider demonstrates conformity rather than the auditor demonstrating
    its absence.

    Three verdicts, not two:

      EQUIVALENT      the whole interval sits inside +/- margin — a PASS that
                      can be defended, not merely a failure to convict
      NOT_EQUIVALENT  the whole interval sits outside — a FAIL
      UNDETERMINED    the interval straddles the boundary — the honest answer,
                      and the one an ordinary test never gives

    The margin is a human judgement about what magnitude matters. It has to be
    declared before the data are seen, which is why it lives in the signed
    checklist rather than in this function's defaults.

    Implementation note: TOST at level alpha is exactly the containment of the
    (1 - 2*alpha) interval, so the 90% interval is used for a 5% test. Quoting
    the 95% interval here is a standard and conservative mistake.
    """
    if margin <= 0:
        raise ValueError("margin must be positive")
    n = a + b + c + d
    if n == 0:
        raise ValueError("empty table")

    iv = paired_diff(a, b, c, d, alpha=2 * alpha)
    point = iv.point
    mle = _paired_loglik(a, b, c, d, point)

    def one_sided_p(bound: float) -> float:
        """P of a result this far from `bound`, on the side away from it."""
        lr = 2 * (mle - _paired_loglik(a, b, c, d, bound))
        half = 0.5 * _chi2_sf_1df(lr)
        # if the estimate sits beyond the bound, the evidence points the wrong
        # way and the one-sided test cannot reject
        return half if abs(point) < abs(bound) or (point - bound) * bound < 0 else 1.0 - half

    p_upper = one_sided_p(margin)     # H0: difference >= +margin
    p_lower = one_sided_p(-margin)    # H0: difference <= -margin
    p_tost = max(p_upper, p_lower)

    if iv.low > -margin and iv.high < margin:
        verdict = EQUIVALENT
    elif iv.low >= margin or iv.high <= -margin:
        verdict = NOT_EQUIVALENT
    else:
        verdict = UNDETERMINED

    return {"verdict": verdict, "margin": margin, "alpha": alpha,
            "estimate": iv.point, "ci_low": iv.low, "ci_high": iv.high,
            "interval_level": round(1 - 2 * alpha, 3),
            "p_tost": min(1.0, p_tost), "method": "TOST / profile-likelihood"}


def holm(p_values: dict[str, float], alpha: float = 0.05) -> dict:
    """Holm-Bonferroni step-down correction over a family of tests.

    Four audited models means four confirmatory tests, and the chance of at
    least one spurious rejection at 5% each is not 5%. Holm controls the
    family-wise error rate, is uniformly more powerful than plain Bonferroni,
    and makes no assumption about dependence between the tests — which matters
    here because the models share a probe set and are therefore not independent.
    """
    ordered = sorted(p_values.items(), key=lambda kv: kv[1])
    m = len(ordered)
    out, previous_rejected = {}, True
    for i, (name, p) in enumerate(ordered):
        threshold = alpha / (m - i)
        rejected = previous_rejected and p <= threshold
        previous_rejected = rejected
        out[name] = {"p": p, "threshold": round(threshold, 6),
                     "rejected": rejected, "rank": i + 1, "family_size": m}
    return out


def adverse_impact_ratio(a: int, b: int, c: int, d: int, alpha: float = 0.05,
                         iterations: int = 4000, seed: int = 20260824) -> Interval:
    """Ratio of favourable rates between two arms — the form banking reads.

    Fair lending supervision runs on ratios and the four-fifths rule, not on rate
    differences, so an audit that reports only a difference is speaking a
    language its intended reader does not use. The ratio is reported for that
    audience; it is NOT the primary estimand, and the contrast between the two is
    itself a finding worth putting in front of people.

    On this project's own data the two disagree completely. The ratio clears the
    four-fifths rule in every stratum while the paired test returns p = 1e-16 on
    the same responses, because aggregating over applicants destroys the pairing
    that carries the signal: a ratio of group rates cannot see 59 against 1.

    The interval is bootstrapped over PAIRS rather than computed by the usual
    Katz log-ratio formula. Katz assumes the two arms are independent samples.
    Here they are the same applicant rendered twice, so they are strongly
    positively correlated and Katz is wide — conservative rather than wrong, but
    conservative in a direction that would let a real disparity pass. Resampling
    whole pairs keeps the correlation the design created.
    """
    n = a + b + c + d
    if n == 0:
        raise ValueError("empty table")
    k1, k2 = a + b, a + c
    if k2 == 0:
        return Interval(float("inf"), 0.0, float("inf"), "bootstrap-pairs")
    point = (k1 / n) / (k2 / n)

    import random
    rng = random.Random(seed)
    cuts = [a / n, (a + b) / n, (a + b + c) / n]
    draws = []
    for _ in range(iterations):
        ra = rb = rc = 0
        for _ in range(n):
            u = rng.random()
            if u < cuts[0]:
                ra += 1
            elif u < cuts[1]:
                rb += 1
            elif u < cuts[2]:
                rc += 1
        if ra + rc:
            draws.append((ra + rb) / (ra + rc))
    if not draws:
        return Interval(point, 0.0, float("inf"), "bootstrap-pairs")
    draws.sort()
    lo = draws[int((alpha / 2) * len(draws))]
    hi = draws[min(len(draws) - 1, int((1 - alpha / 2) * len(draws)))]
    return Interval(point, lo, hi, "bootstrap-pairs")


def four_fifths(iv: Interval, low: float = 0.80, high: float = 1.25) -> str:
    """The conventional reading of an adverse impact ratio.

    Applied two-sided. The rule is usually quoted one-sided, because it was
    written for a world where the protected group is the one disadvantaged; a
    model that favours the protected arm passes a one-sided test while treating
    identical applicants differently. This audit found exactly that, so the
    band is symmetric here by deliberate choice, and the choice is recorded.
    """
    if iv.low >= low and iv.high <= high:
        return "within the four-fifths band"
    if iv.low > high or iv.high < low:
        return "OUTSIDE the four-fifths band"
    return "inconclusive: the interval spans the four-fifths boundary"


def exact_mcnemar(b: int, c: int) -> float | None:
    """Two-sided exact McNemar: a binomial sign test on the discordant pairs.

    None when nothing was discordant. The chi-square form of McNemar is an
    approximation that fails exactly where this audit lives — small discordant
    counts — so it is not offered as an option.

    The upper tail is obtained by SYMMETRY rather than as 1 - cdf. At p = 0.5 the
    binomial is symmetric, so P(X >= b) = P(X <= n - b) exactly, and the two
    routes are algebraically identical but numerically nothing alike. Writing
    `1 - binom_cdf(b - 1, n, 0.5)` asks float64 to subtract from 1 a number that
    differs from 1 by about 1e-17: the difference is below the representable gap
    and the result is exactly 0.0. That is how 59 versus 1 discordant pairs came
    back as "p = 0" — not an underflow to a very small number but a hard zero,
    which in a report reads as a mistake and in a thesis is one.
    """
    n = b + c
    if n == 0:
        return None
    lower = binom_cdf(b, n, 0.5)          # P(X <= b)
    upper = binom_cdf(n - b, n, 0.5)      # P(X >= b), by symmetry at p = 0.5
    return min(1.0, 2.0 * min(lower, upper))


def min_discordant_to_reject(alpha: float = 0.05) -> int:
    """Fewest discordant pairs at which the exact test can reject at all.

    Below this the test is not underpowered, it is incapable: the most extreme
    outcome available still gives p > alpha. Six, at the usual level.
    """
    k = 1
    while min(1.0, 2.0 * 0.5 ** k) > alpha:
        k += 1
        if k > 60:
            raise ValueError(f"unreachable for alpha={alpha}")
    return k
