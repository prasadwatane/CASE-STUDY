"""S2 and S2b: is the judge as good as a second human, and better than a word list?

Pre-registered readings (PREREGISTRATION.md, OPEN 1 and OPEN 3, closed
18 November 2026):

  S2   D = ½[AC1(J, A) + AC1(J, B)] − AC1(A, B),  δ = 0.10
       met          one-sided 95% lower bound of D  > −δ
       not met      one-sided 95% upper bound of D  < −δ
       undetermined otherwise
  S2b  Δ = AC1(J, R*) − AC1(Q, R*)
       met          lower bound > 0;  not met  upper bound < 0;  else undetermined

AC1 is primary because S1 uses it; the κ-based versions are computed and
reported alongside, never as the criterion. Intervals are **BCa** bootstrap over
items: in simulation at the margin (n = 120–300, prevalence 0.65–0.70, ceiling
κ 0.70–0.75) the percentile bound rejected 0.055–0.061 of the time against a
nominal 0.05, BCa 0.047–0.055.

The arbitrated label R* is not used in S2, because a label built from both
raters is an easier target than either rater alone.
"""
from __future__ import annotations

from statistics import NormalDist

from grail.annotate.agreement import cohen_kappa, gwet_ac1
from grail.probe.schema import derive_rng

DELTA = 0.10
_N = NormalDist()
STATS = {"ac1": gwet_ac1, "kappa": cohen_kappa}


def _norm(labels) -> list[str]:
    out = []
    for x in labels:
        if isinstance(x, bool):
            out.append("adequate" if x else "inadequate")
        else:
            out.append(str(x).strip().lower())
    return out


def _stat(name, x, y):
    v = STATS[name](x, y)[0]
    return v


def _d(stat, a, b, j):
    ja, jb, ab = _stat(stat, j, a), _stat(stat, j, b), _stat(stat, a, b)
    if None in (ja, jb, ab):
        return None
    return (ja + jb) / 2 - ab


def _delta(stat, j, q, r):
    jr, qr = _stat(stat, j, r), _stat(stat, q, r)
    if None in (jr, qr):
        return None
    return jr - qr


def bca_bounds(fn, cols: list[list[str]], iterations: int = 10000, seed: int = 20261118,
               alpha: float = 0.05) -> tuple[float | None, float | None, float | None]:
    """(estimate, one-sided lower bound, one-sided upper bound) at level 1 − alpha.

    `fn(*cols)` is the statistic over item-aligned label vectors. Resampling is
    over items; acceleration from the item jackknife.
    """
    n = len(cols[0])
    theta = fn(*cols)
    if theta is None or n < 3:
        return theta, None, None
    r = derive_rng(seed, "bca", n)
    draws = []
    for _ in range(iterations):
        idx = [r.randrange(n) for _ in range(n)]
        v = fn(*[[c[i] for i in idx] for c in cols])
        if v is not None:
            draws.append(v)
    if len(draws) < iterations * 0.5:
        return theta, None, None
    draws.sort()
    m = len(draws)
    below = sum(1 for d in draws if d < theta) / m
    z0 = _N.inv_cdf(min(max(below, 1e-6), 1 - 1e-6))
    jack = []
    for i in range(n):
        v = fn(*[c[:i] + c[i + 1:] for c in cols])
        if v is not None:
            jack.append(v)
    jm = sum(jack) / len(jack)
    num = sum((jm - v) ** 3 for v in jack)
    den = 6 * (sum((jm - v) ** 2 for v in jack) ** 1.5)
    a = num / den if den > 0 else 0.0

    def q(p):
        z = _N.inv_cdf(p)
        adj = _N.cdf(z0 + (z0 + z) / (1 - a * (z0 + z)))
        k = min(m - 1, max(0, int(adj * m)))
        return draws[k]

    return theta, q(alpha), q(1 - alpha)


def _three_way(lo, hi, bar_met_above: float) -> str:
    if lo is None:
        return "undetermined"
    if lo > bar_met_above:
        return "met"
    if hi is not None and hi < bar_met_above:
        return "not met"
    return "undetermined"


def s2(rater_a, rater_b, judge, delta: float = DELTA, iterations: int = 10000,
       seed: int = 20261118) -> dict:
    """Judge non-inferior to a second human (H1b). Items must be aligned."""
    a, b, j = _norm(rater_a), _norm(rater_b), _norm(judge)
    if not (len(a) == len(b) == len(j)):
        raise ValueError("rater and judge vectors must be item-aligned")
    out = {"n": len(a), "delta": delta, "interval": "BCa, one-sided 95%"}
    for stat in ("ac1", "kappa"):
        est, lo, hi = bca_bounds(lambda x, y, z: _d(stat, x, y, z), [a, b, j],
                                 iterations=iterations, seed=seed)
        out[stat] = {"D": est, "lower": lo, "upper": hi,
                     "verdict": _three_way(lo, hi, -delta)}
    out["verdict"] = out["ac1"]["verdict"]          # AC1 is the criterion
    return out


def s2b(judge, rule, reference, iterations: int = 10000, seed: int = 20261118) -> dict:
    """Judge better than the rule-based scorer Q against R* (H1c)."""
    j, q, r = _norm(judge), _norm(rule), _norm(reference)
    if not (len(j) == len(q) == len(r)):
        raise ValueError("judge, rule and reference vectors must be item-aligned")
    out = {"n": len(j), "interval": "BCa, one-sided 95%"}
    for stat in ("ac1", "kappa"):
        est, lo, hi = bca_bounds(lambda x, y, z: _delta(stat, x, y, z), [j, q, r],
                                 iterations=iterations, seed=seed)
        out[stat] = {"Delta": est, "lower": lo, "upper": hi,
                     "verdict": _three_way(lo, hi, 0.0)}
    out["verdict"] = out["ac1"]["verdict"]
    return out
