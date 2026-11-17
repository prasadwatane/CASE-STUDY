"""Sequentially valid audit-budget allocation (C3, RQ3).

The uncorrected adaptive policy in `replay.py` looks at every requirement after
every round and stops buying evidence once a fixed-sample interval clears the
threshold. Each look is a test at level alpha; nine looks are up to nine
chances to cross a boundary by luck. That is optional stopping, and the replay
already shows its cost: verdict fidelity falls to about 0.78.

Two corrections are implemented here, both keeping the case study's verdict
rule (three verdicts, same margins, same withheld-PASS guard) and changing only
how much evidence a determinate verdict needs.

**Confidence sequences (primary).** A mixture-likelihood confidence sequence
(Robbins 1970; Howard et al. 2021): for the true parameter p*, the ratio

    M_n(p*) = ∫ L_n(p) dπ(p) / L_n(p*)

is a non-negative martingale with mean one, so by Ville's inequality
P(∃n : M_n(p*) ≥ 1/alpha) ≤ alpha. The set {p : M_n(p) < 1/alpha} therefore
covers p* at every n simultaneously, and stays valid at whatever moment an
adaptive policy decides to stop. Written as a likelihood region it is

    { p : log L_n(p) > log m_n − log(1/alpha) },   m_n = ∫ L_n dπ,

which is the profile-likelihood interval the jury already uses, with the fixed
cut-off chi2/2 replaced by one that grows like (d/2) log n. The prior is
Jeffreys: Beta(1/2, 1/2) for a single rate, Dirichlet(1/2, 1/2, 1/2) for the
three-cell paired table (discordant for ref, discordant for other, concordant).

**Alpha spending (comparator).** The fixed-sample rule is applied at look j at
level alpha_j = a(j/K) − a((j−1)/K), with a(·) a Lan–DeMets spending function
and K = rounds + 1 the maximum number of looks, fixed in advance. By the union
bound the chance of any false determinate verdict across all looks is at most
sum alpha_j = alpha. This ignores the correlation between looks and is
therefore conservative; it is reported to show what the classical, discrete-look
answer costs, not as the method of choice.

Error matching. In the fixed rule a false PASS (TOST at alpha) and a false FAIL
(two-sided interval at alpha excluding zero) each have probability at most
alpha. Both corrected rules are run at the same alpha and give the same
per-requirement guarantee, but uniformly over looks.

Decisions are computed from the likelihood at three points (−margin, 0,
+margin) rather than by bisecting for interval endpoints. Because the profile
log-likelihood is concave in the difference, "the interval lies inside
(−m, m)" is exactly "the profile at ±m is below the cut-off and the estimate is
inside", and likewise for excluding zero. `fixed_fairness_verdict` is checked
in the tests against the jury's own bisection-based rule.
"""
from __future__ import annotations

import math
import random
from functools import lru_cache
from statistics import mean

from grail.allocate.replay import (ALPHA, FAIRNESS_MARGIN, ROBUSTNESS_TOLERANCE,
                                   Requirement, determinate, reference_verdicts,
                                   static_allocation)
from grail.jury.intervals import _paired_loglik, _z, min_discordant_to_reject, wilson

UNDET, PASS, FAIL = "UNDETERMINED", "PASS", "FAIL"


# =============================================================== counts
def fairness_counts(units: list) -> tuple[int, int, int]:
    """(b, c, concordant) from (fav_ref, fav_other) pairs."""
    b = c = conc = 0
    for ref, other in units:
        if ref and not other:
            b += 1
        elif other and not ref:
            c += 1
        else:
            conc += 1
    return b, c, conc


def robustness_counts(units: list) -> tuple[int, int]:
    flipped = sum(1 for base, variants in units if any(v != base for v in variants))
    return flipped, len(units)


# =============================================================== fixed-sample rule
def _prof(b: int, c: int, conc: int, delta: float) -> float:
    # three-cell profile; the a/d split of the concordant mass is a constant
    # that cancels in every comparison below
    return _paired_loglik(conc, b, c, 0, delta)


@lru_cache(maxsize=None)
def fixed_fairness_verdict(b: int, c: int, conc: int, alpha: float = ALPHA,
                           margin: float = FAIRNESS_MARGIN) -> str:
    """The jury's fairness rule, decided at three points instead of by bisection."""
    n = b + c + conc
    if n == 0:
        return UNDET
    point = (b - c) / n
    mle = _prof(b, c, conc, point)
    # TOST at alpha == containment of the (1 - 2 alpha) interval
    crit_eq = _z(2 * alpha) ** 2
    inside = (-margin < point < margin
              and 2 * (mle - _prof(b, c, conc, margin)) > crit_eq
              and 2 * (mle - _prof(b, c, conc, -margin)) > crit_eq)
    if inside:
        return PASS if (b + c) >= min_discordant_to_reject(alpha) else UNDET
    crit = _z(alpha) ** 2
    if abs(point) >= margin and 2 * (mle - _prof(b, c, conc, 0.0)) > crit:
        return FAIL
    return UNDET


@lru_cache(maxsize=None)
def fixed_robustness_verdict(flipped: int, n: int, alpha: float = ALPHA,
                             tolerance: float = ROBUSTNESS_TOLERANCE) -> str:
    """Wilson at 1 − 2·alpha two-sided (alpha = 0.05 reproduces the jury's 90%)."""
    if n == 0:
        return UNDET
    iv = wilson(flipped, n, 2 * alpha)
    if iv.high < tolerance:
        return PASS
    if iv.low > tolerance:
        return FAIL
    return UNDET


# =============================================================== confidence sequences
_LG_HALF = math.lgamma(0.5)


def _log_marginal_dirichlet(counts: tuple[int, ...], a0: float = 0.5) -> float:
    """log ∫ Π p_i^{x_i} dDirichlet(a0,…) — the mixture likelihood of the sequence."""
    k = len(counts)
    n = sum(counts)
    return (math.lgamma(k * a0) - k * math.lgamma(a0)
            + sum(math.lgamma(x + a0) for x in counts) - math.lgamma(n + k * a0))


@lru_cache(maxsize=None)
def cs_fairness_verdict(b: int, c: int, conc: int, alpha: float = ALPHA,
                        margin: float = FAIRNESS_MARGIN) -> str:
    """Fairness rule with a time-uniform region in place of the fixed interval."""
    n = b + c + conc
    if n == 0:
        return UNDET
    point = (b - c) / n
    thr = _log_marginal_dirichlet((b, c, conc)) - math.log(1 / alpha)
    inside = (-margin < point < margin
              and _prof(b, c, conc, margin) < thr
              and _prof(b, c, conc, -margin) < thr)
    if inside:
        return PASS if (b + c) >= min_discordant_to_reject(alpha) else UNDET
    if abs(point) >= margin and _prof(b, c, conc, 0.0) < thr:
        return FAIL
    return UNDET


def _binom_ll(k: int, n: int, p: float) -> float:
    if p <= 0:
        return 0.0 if k == 0 else -math.inf
    if p >= 1:
        return 0.0 if k == n else -math.inf
    return k * math.log(p) + (n - k) * math.log1p(-p)


@lru_cache(maxsize=None)
def cs_robustness_verdict(flipped: int, n: int, alpha: float = ALPHA,
                          tolerance: float = ROBUSTNESS_TOLERANCE) -> str:
    if n == 0:
        return UNDET
    logm = (math.lgamma(flipped + 0.5) + math.lgamma(n - flipped + 0.5)
            - math.lgamma(n + 1.0) - 2 * _LG_HALF)
    thr = logm - math.log(1 / alpha)
    phat = flipped / n
    excluded = _binom_ll(flipped, n, tolerance) < thr
    if excluded and phat < tolerance:
        return PASS
    if excluded and phat > tolerance:
        return FAIL
    return UNDET


def cs_bounds_rate(flipped: int, n: int, alpha: float = ALPHA) -> tuple[float, float]:
    """Endpoints of the robustness confidence sequence (for reporting)."""
    logm = (math.lgamma(flipped + 0.5) + math.lgamma(n - flipped + 0.5)
            - math.lgamma(n + 1.0) - 2 * _LG_HALF)
    thr = logm - math.log(1 / alpha)
    phat = flipped / n

    def edge(far: float) -> float:
        lo, hi = far, phat
        for _ in range(80):
            mid = (lo + hi) / 2
            if _binom_ll(flipped, n, mid) < thr:
                lo = mid
            else:
                hi = mid
        return (lo + hi) / 2
    return edge(0.0), edge(1.0)


# =============================================================== spending
def _phi(x: float) -> float:
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def spend_obf(t: float, alpha: float = ALPHA) -> float:
    """Lan–DeMets O'Brien–Fleming-type: almost nothing early, nearly all at the end."""
    if t <= 0:
        return 0.0
    return min(alpha, 2 * (1 - _phi(_z(alpha) / math.sqrt(t))))


def spend_pocock(t: float, alpha: float = ALPHA) -> float:
    """Lan–DeMets Pocock-type: spends more evenly across looks."""
    if t <= 0:
        return 0.0
    return min(alpha, alpha * math.log(1 + (math.e - 1) * t))


def look_alphas(k_looks: int, fn, alpha: float = ALPHA) -> list[float]:
    cum = [fn(j / k_looks, alpha) for j in range(k_looks + 1)]
    return [max(cum[j] - cum[j - 1], 1e-12) for j in range(1, k_looks + 1)]


# =============================================================== verdict rules
class Rule:
    """A stopping rule: verdict for a requirement at look j (1-based) of K."""
    name = "fixed"

    def __call__(self, req: Requirement, units: list, look: int) -> str:
        if req.kind == "fairness":
            return fixed_fairness_verdict(*fairness_counts(units))
        return fixed_robustness_verdict(*robustness_counts(units))


class CSRule(Rule):
    name = "cs"

    def __call__(self, req, units, look):
        if req.kind == "fairness":
            return cs_fairness_verdict(*fairness_counts(units))
        return cs_robustness_verdict(*robustness_counts(units))


class SpendingRule(Rule):
    def __init__(self, k_looks: int, fn, name: str):
        self.alphas = look_alphas(k_looks, fn)
        self.name = name

    def __call__(self, req, units, look):
        a = self.alphas[min(look, len(self.alphas)) - 1]
        if req.kind == "fairness":
            return fixed_fairness_verdict(*fairness_counts(units), alpha=a)
        return fixed_robustness_verdict(*robustness_counts(units), alpha=a)


# =============================================================== policies
def static_policy(reqs: list[Requirement], budget: int, rng: random.Random):
    """One look, at the end, at alpha. Same proportional split as replay.py."""
    order = {r.key: rng.sample(range(r.n_available), r.n_available) for r in reqs}
    taken = static_allocation(reqs, budget)
    spent = sum(taken[r.key] * r.cost_per_unit for r in reqs)
    rule = Rule()
    verdicts = {r.key: rule(r, [r.units[i] for i in order[r.key][:taken[r.key]]], 1)
                for r in reqs}
    return taken, spent, verdicts


def adaptive_policy(reqs: list[Requirement], budget: int, rng: random.Random,
                    rule: Rule, rounds: int = 8, seed_frac: float = 0.15):
    """The case study's adaptive schedule, with the stopping rule as a parameter.

    Purchases are identical to `replay.adaptive_allocation` given the same rule;
    the difference is that a requirement's verdict is FROZEN at the look where it
    became determinate. Re-scoring later at a different alpha would be a new
    look, and the corrected rules are only valid if each look is counted.
    """
    order = {r.key: rng.sample(range(r.n_available), r.n_available) for r in reqs}
    taken = {r.key: 0 for r in reqs}
    spent = 0
    seed_budget = int(budget * seed_frac)
    per = max(1, seed_budget // max(1, len(reqs)))
    for r in reqs:
        k = min(r.n_available, per // r.cost_per_unit)
        taken[r.key] = k
        spent += k * r.cost_per_unit

    stopped: dict = {}
    look = 0

    def score(r):
        return rule(r, [r.units[i] for i in order[r.key][:taken[r.key]]], look)

    for _ in range(rounds):
        look += 1
        live = []
        for r in reqs:
            if r.key in stopped:
                continue
            v = score(r)
            if determinate(v):
                stopped[r.key] = v
            elif taken[r.key] < r.n_available:
                live.append(r)
        if not live or spent >= budget:
            break
        room = budget - spent
        per = max(1, room // (len(live) * (rounds // 2 or 1)))
        for r in live:
            k = min(r.n_available - taken[r.key], per // r.cost_per_unit)
            if k <= 0:
                continue
            if spent + k * r.cost_per_unit > budget:
                k = (budget - spent) // r.cost_per_unit
            if k <= 0:
                continue
            taken[r.key] += k
            spent += k * r.cost_per_unit

    look += 1                       # the final look, after the last purchase
    verdicts = {}
    for r in reqs:
        verdicts[r.key] = stopped[r.key] if r.key in stopped else score(r)
    return taken, spent, verdicts


# =============================================================== experiment
def _summ(xs: list[float]) -> dict:
    s = sorted(xs)
    n = len(s)
    return {"mean": round(mean(s), 4),
            "lo": round(s[int(0.025 * (n - 1))], 4),
            "hi": round(s[int(round(0.975 * (n - 1)))], 4)}


def _mean_ci(xs: list[float], reps: int = 4000, seed: int = 11) -> dict:
    rng = random.Random(seed)
    n = len(xs)
    ms = sorted(mean(rng.choice(xs) for _ in range(n)) for _ in range(reps))
    return {"mean": round(mean(xs), 4), "lo": round(ms[int(0.025 * reps)], 4),
            "hi": round(ms[int(0.975 * reps) - 1], 4)}


def compare_policies(reqs: list[Requirement], budgets: list[int], seeds: int = 40,
                     rounds: int = 8) -> list[dict]:
    """Static, uncorrected adaptive and corrected adaptive at matched budgets.

    For each seed every policy samples units in the same order (same
    Random(1000 + seed) stream), so the comparison is paired: differences are
    computed seed by seed and summarised with a 2.5–97.5% range over seeds.
    That range describes replay variability over which units are drawn; it is
    not a sampling interval for new data.
    """
    ref = reference_verdicts(reqs)
    k_looks = rounds + 1
    policies = {
        "static": None,
        "adaptive": Rule(),
        "adaptive_cs": CSRule(),
        "adaptive_obf": SpendingRule(k_looks, spend_obf, "adaptive_obf"),
        "adaptive_pocock": SpendingRule(k_looks, spend_pocock, "adaptive_pocock"),
    }
    out = []
    for budget in budgets:
        per_seed = {p: {"cov": [], "fid": [], "contra": [], "spent": []} for p in policies}
        for s in range(seeds):
            for name, rule in policies.items():
                rng = random.Random(1000 + s)
                if rule is None:
                    taken, spent, ver = static_policy(reqs, budget, rng)
                else:
                    taken, spent, ver = adaptive_policy(reqs, budget, rng, rule, rounds)
                det = [k for k, v in ver.items() if determinate(v)]
                agree = sum(1 for k in det if ver[k] == ref[k])
                d = per_seed[name]
                d["cov"].append(len(det) / len(reqs))
                d["fid"].append(agree / len(det) if det else 1.0)
                d["contra"].append(len(det) - agree)
                d["spent"].append(spent)
        st = per_seed["static"]
        for name, d in per_seed.items():
            row = {"budget": budget, "policy": name,
                   "coverage": _summ(d["cov"]), "fidelity": _summ(d["fid"]),
                   "contradictions": _summ(d["contra"]),
                   "contradictions_max": max(d["contra"]),
                   "spent": _summ(d["spent"])}
            if name != "static":
                row["fidelity_ratio_vs_static"] = _summ(
                    [f / sf if sf else 1.0 for f, sf in zip(d["fid"], st["fid"])])
                row["spend_ratio_vs_static"] = _summ(
                    [x / sx if sx else 1.0 for x, sx in zip(d["spent"], st["spent"])])
                row["coverage_diff_vs_static"] = _summ(
                    [c - sc for c, sc in zip(d["cov"], st["cov"])])
                fr, sr = row["fidelity_ratio_vs_static"], row["spend_ratio_vs_static"]
                # S4 on the bounds, never the point: the 2.5% fidelity ratio and the
                # 97.5% spend ratio must both clear. This is the per-seed RANGE
                # (how a single audit run could come out) — the stricter reading.
                row["S4"] = ("met" if fr["lo"] >= 0.90 and sr["hi"] <= 0.80 else
                             "not met" if fr["hi"] < 0.90 or sr["lo"] > 0.80 else
                             "undetermined")
                # Secondary reading: bootstrap CI of the MEAN over seeds (the
                # policy's expected behaviour). Reported, not the criterion.
                fm = _mean_ci([f / sf if sf else 1.0 for f, sf in zip(d["fid"], st["fid"])])
                sm = _mean_ci([x / sx if sx else 1.0 for x, sx in zip(d["spent"], st["spent"])])
                row["fidelity_ratio_mean_ci"], row["spend_ratio_mean_ci"] = fm, sm
                row["S4_mean_ci"] = ("met" if fm["lo"] >= 0.90 and sm["hi"] <= 0.80 else
                                     "not met" if fm["hi"] < 0.90 or sm["lo"] > 0.80 else
                                     "undetermined")
                row["coverage_ratio_vs_static"] = _mean_ci(
                    [c / sc if sc else 1.0 for c, sc in zip(d["cov"], st["cov"])])
            out.append(row)
    return out


# =============================================================== null simulation
def null_requirements(kind: str, n: int, rng: random.Random) -> Requirement:
    """A requirement whose true parameter sits exactly where a verdict is wrong.

    fairness_null0   true difference 0, 2% discordant each way: any FAIL is false
    fairness_margin  true difference = +margin: any PASS is false
    robustness_tol   true flip rate = tolerance: any determinate verdict is false
    """
    if kind == "fairness_null0":
        p_b = p_c = 0.02
    elif kind == "fairness_margin":
        p_c = 0.02
        p_b = p_c + FAIRNESS_MARGIN
    if kind.startswith("fairness"):
        units = []
        for _ in range(n):
            u = rng.random()
            units.append((True, False) if u < p_b else
                         (False, True) if u < p_b + p_c else (True, True))
        return Requirement(kind, "fairness", "sim", kind, units, 2)
    units = [("A", ["B" if rng.random() < ROBUSTNESS_TOLERANCE else "A"])
             for _ in range(n)]
    return Requirement(kind, "robustness", "sim", "-", units, 7)


def false_verdict(kind: str, v: str) -> bool:
    if kind == "fairness_null0":
        return v == FAIL
    if kind == "fairness_margin":
        return v == PASS
    return determinate(v)


def null_error_rates(kind: str, n: int, sims: int, rounds: int = 8,
                     seed: int = 20261116) -> dict:
    """Share of simulated audits that reach a false determinate verdict."""
    k_looks = rounds + 1
    rules = {"static": None, "adaptive": Rule(), "adaptive_cs": CSRule(),
             "adaptive_obf": SpendingRule(k_looks, spend_obf, "obf"),
             "adaptive_pocock": SpendingRule(k_looks, spend_pocock, "pocock")}
    errs = {k: 0 for k in rules}
    det = {k: 0 for k in rules}
    for s in range(sims):
        req = null_requirements(kind, n, random.Random(seed * 7919 + s))
        budget = req.n_available * req.cost_per_unit
        for name, rule in rules.items():
            rng = random.Random(seed + s)
            if rule is None:
                _, _, v = static_policy([req], budget, rng)
            else:
                _, _, v = adaptive_policy([req], budget, rng, rule, rounds)
            vv = v[req.key]
            errs[name] += false_verdict(kind, vv)
            det[name] += determinate(vv)
    return {name: {"false_rate": round(errs[name] / sims, 4),
                   "determinate_rate": round(det[name] / sims, 4)} for name in rules}
