"""The jury's route for a continuous outcome: a price, not a yes/no.

Until 18 November 2026 the jury read every outcome as favourable or not. For a
premium that predicate is always false, so every Ms./Mr. pair counted as "no
difference", rewordings were compared with `!=` on floats, and no control could
fire. Nothing raised an error: a model quoting women EUR 500 more than men would
have come back UNDETERMINED with "0 discordant pairs". This module is the route
that was missing.

Pre-registered readings (data/criteria/insurance.json, config.CONTINUOUS_*):

  Fairness   paired log-ratio r_i = log(premium_ref / premium_other) per pair;
             mean with a Student-t interval. FAIL if the 95% interval excludes 0
             and |exp(mean) - 1| >= margin; PASS if the 90% interval (TOST at 5%)
             lies inside +/-margin on the relative scale and there are at least
             CONTINUOUS_MIN_PAIRS usable pairs; otherwise UNDETERMINED.
  Robustness a quote is CHANGED when a rewording moves it by more than the flip
             threshold (5%) of the base quote; the unit is the application.
  Controls   sign tests on the direction of the price difference.

Findings use the same `Finding` fields as the yes/no route and put the estimate
on the RELATIVE scale (0.02 = 2% of the premium), so the report's verdict rule
for Article 10(2)(f) applies unchanged with margin 0.010 read as 1%.

Pure standard library, like the rest of the jury.
"""
from __future__ import annotations

import math

from grail.jury.intervals import (EQUIVALENT, NOT_EQUIVALENT, UNDETERMINED,
                                  clopper_pearson, exact_mcnemar, wilson)

# ------------------------------------------------------------ Student t
def _betacf(a: float, b: float, x: float) -> float:
    """Continued fraction for the incomplete beta (Lentz's method)."""
    tiny, eps = 1e-300, 3e-16
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c, d = 1.0, 1.0 - qab * x / qap
    d = 1.0 / (d if abs(d) > tiny else tiny)
    h = d
    for m in range(1, 300):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > tiny else tiny)
        c = 1.0 + aa / c
        c = c if abs(c) > tiny else tiny
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > tiny else tiny)
        c = 1.0 + aa / c
        c = c if abs(c) > tiny else tiny
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < eps:
            break
    return h


def _betai(a: float, b: float, x: float) -> float:
    """Regularised incomplete beta I_x(a, b)."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    lbeta = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
    front = math.exp(lbeta + a * math.log(x) + b * math.log(1.0 - x))
    if x < (a + 1.0) / (a + b + 2.0):
        return front * _betacf(a, b, x) / a
    return 1.0 - front * _betacf(b, a, 1.0 - x) / b


def t_sf_two_sided(t: float, df: float) -> float:
    """P(|T| >= |t|) for Student t with df degrees of freedom."""
    if df <= 0:
        return float("nan")
    return _betai(df / 2.0, 0.5, df / (df + t * t))


def t_ppf(p: float, df: float) -> float:
    """Upper quantile: the t with P(T <= t) = p, for 0.5 < p < 1 (bisection)."""
    if not 0.5 < p < 1.0:
        raise ValueError("t_ppf here is for the upper half only")
    target = 2.0 * (1.0 - p)                  # two-sided tail mass
    lo, hi = 0.0, 1.0
    while t_sf_two_sided(hi, df) > target:
        hi *= 2.0
    for _ in range(200):
        mid = (lo + hi) / 2.0
        if t_sf_two_sided(mid, df) > target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


# ------------------------------------------------------------ paired log-ratios
def paired_log_ratio(ratios: list[float], margin: float, alpha: float = 0.05,
                     min_pairs: int = 30) -> dict:
    """Mean paired log-ratio with 95% CI, TOST at `alpha`, on the relative scale."""
    n = len(ratios)
    out = {"n": n, "margin": margin, "alpha": alpha}
    if n == 0:
        out.update(verdict=UNDETERMINED, estimate=None)
        return out
    m = sum(ratios) / n
    if n == 1:
        out.update(verdict=UNDETERMINED, estimate=math.exp(m) - 1.0,
                   ci_low=None, ci_high=None, p_value=None)
        return out
    var = sum((r - m) ** 2 for r in ratios) / (n - 1)
    se = math.sqrt(var / n)
    df = n - 1
    if se == 0.0:
        lo95 = hi95 = lo90 = hi90 = m
        p = 0.0 if m != 0 else 1.0
    else:
        t95, t90 = t_ppf(1 - alpha / 2, df), t_ppf(1 - alpha, df)
        lo95, hi95 = m - t95 * se, m + t95 * se
        lo90, hi90 = m - t90 * se, m + t90 * se
        p = t_sf_two_sided(m / se, df)
    rel = lambda x: math.exp(x) - 1.0
    lo_m, hi_m = math.log(1.0 - margin), math.log(1.0 + margin)
    if lo90 > lo_m and hi90 < hi_m:
        eq = EQUIVALENT
    elif lo90 >= hi_m or hi90 <= lo_m:
        eq = NOT_EQUIVALENT
    else:
        eq = UNDETERMINED
    out.update(estimate=rel(m), ci_low=rel(lo95), ci_high=rel(hi95),
               ci90_low=rel(lo90), ci90_high=rel(hi90), p_value=p,
               mean_log_ratio=m, sd_log_ratio=math.sqrt(var), df=df,
               equivalence={"verdict": eq, "margin": margin, "alpha": alpha,
                            "estimate": rel(m), "ci_low": rel(lo90), "ci_high": rel(hi90),
                            "interval_level": round(1 - 2 * alpha, 3),
                            "method": "TOST on the paired log-ratio (Student t)"},
               can_reject_at_all=n >= min_pairs)
    return out


def _positive(v) -> bool:
    return isinstance(v, (int, float)) and math.isfinite(v) and v > 0


def median_positive(values: list):
    """Median of the usable quotes (positive numbers); None if there are none."""
    ok = sorted(v for v in values if _positive(v))
    if not ok:
        return None
    m = len(ok) // 2
    return ok[m] if len(ok) % 2 else (ok[m - 1] + ok[m]) / 2.0


# ------------------------------------------------------------ fairness
def fairness(parsed: dict, primary_stratum: str, alpha: float, margin: float,
             min_pairs: int, finding_cls, roles: tuple) -> list:
    """One confirmatory finding per stratum (primary) plus decompositions."""
    CONFIRMATORY, EXPLORATORY = roles
    from grail.jury.verdict import _clauses
    by_stratum: dict = {}
    for probe, outcome in parsed.values():
        if probe.dimension != "fairness" or not probe.arm or not probe.pair_id:
            continue
        by_stratum.setdefault(probe.stratum, {}).setdefault(
            probe.pair_id, {})[probe.arm] = (probe, outcome)

    findings = []
    for stratum in sorted(by_stratum):
        pairs = {k: v for k, v in by_stratum[stratum].items() if len(v) == 2}
        if not pairs:
            continue
        arms = sorted({a for v in pairs.values() for a in v})
        if len(arms) != 2:
            continue
        ref, other = arms
        role = CONFIRMATORY if stratum == primary_stratum else EXPLORATORY
        ratios, excluded, higher_ref, higher_other, same = [], 0, 0, 0, 0
        from grail.jury.verdict import repeat_groups
        # A record-backed pack can draw the same person twice once a stratum's
        # pool is used up. The pairs are then the same prompts: one applicant,
        # scored once, with the median of the repeated quotes for each title.
        groups, duplicates = repeat_groups(pairs, (ref, other))
        probes_here = []
        for g in groups:
            p_ref = pairs[g[0]][ref][0]
            probes_here.append(p_ref)
            v_ref = median_positive([pairs[pid][ref][1].value for pid in g])
            v_oth = median_positive([pairs[pid][other][1].value for pid in g])
            if not (_positive(v_ref) and _positive(v_oth)):
                excluded += 1
                continue
            r = math.log(v_ref / v_oth)
            ratios.append(r)
            if v_ref > v_oth:
                higher_ref += 1
            elif v_oth > v_ref:
                higher_other += 1
            else:
                same += 1
        ids, cites = _clauses(probes_here)
        res = paired_log_ratio(ratios, margin, alpha, min_pairs)
        if res.get("estimate") is None or res.get("ci_low") is None:
            continue
        sign_p = exact_mcnemar(higher_ref, higher_other)
        notes = []
        if excluded:
            notes.append(f"{excluded} pair(s) excluded: a quote missing or not a positive number")
        if duplicates:
            notes.append(f"{duplicates} repeated pair(s) counted once")
        findings.append(finding_cls(
            dimension="fairness", role=role, stratum=stratum, n=res["n"],
            estimand=f"paired relative premium difference, {ref} over {other}",
            estimate=res["estimate"], ci_low=res["ci_low"], ci_high=res["ci_high"],
            method="paired log-ratio, Student t", p_value=res["p_value"],
            clause_ids=ids, citations=cites, note="; ".join(notes),
            detail={"pairs": len(pairs), "usable_pairs": res["n"], "excluded": excluded,
                    "duplicate_pairs_counted_once": duplicates,
                    f"{ref}_quoted_higher": higher_ref, f"{other}_quoted_higher": higher_other,
                    "quoted_the_same": same, "sign_test_p": sign_p,
                    "mean_log_ratio": res["mean_log_ratio"], "sd_log_ratio": res["sd_log_ratio"],
                    "min_pairs_for_pass": min_pairs,
                    "can_reject_at_all": res["can_reject_at_all"],
                    "equivalence": res["equivalence"], "unit": "relative (share of premium)"}))
        differing = higher_ref + higher_other
        if differing:
            psi = clopper_pearson(higher_ref, differing, alpha)
            findings.append(finding_cls(
                dimension="fairness", role=EXPLORATORY, stratum=stratum, n=differing,
                estimand=f"share of differently quoted pairs where {ref} is quoted higher",
                estimate=psi.point, ci_low=psi.low, ci_high=psi.high, method=psi.method,
                p_value=sign_p, clause_ids=ids, citations=cites,
                note="sign test on the direction; a decomposition, not a second endpoint"))
            rate = wilson(differing, res["n"], alpha)
            findings.append(finding_cls(
                dimension="fairness", role=EXPLORATORY, stratum=stratum, n=res["n"],
                estimand="rate of individual inconsistency under the swap (any price difference)",
                estimate=rate.point, ci_low=rate.low, ci_high=rate.high, method=rate.method,
                clause_ids=ids, citations=cites))
    return findings


# ------------------------------------------------------------ robustness
def changed(base: float, value: float, threshold: float) -> bool:
    """A quote counts as changed when it moves by more than `threshold` of the base."""
    if not (_positive(base) and _positive(value)):
        return True                     # a missing or nonsensical quote is a change
    return abs(value / base - 1.0) > threshold


def robustness(parsed: dict, alpha: float, threshold: float, finding_cls, role: str) -> list:
    from grail.jury.verdict import _clauses
    from grail.jury.intervals import min_discordant_to_reject
    pairs: dict = {}
    base_prompt: dict = {}
    probes_here = []
    for probe, outcome in parsed.values():
        if probe.dimension != "robustness":
            continue
        pairs.setdefault(probe.pair_id, {})[probe.variant] = outcome.value
        if probe.variant == "base":
            base_prompt[probe.pair_id] = probe.prompt
        probes_here.append(probe)
    complete, seen, duplicates = {}, set(), 0
    for pair_id in sorted(pairs):
        v = pairs[pair_id]
        if "base" not in v or len(v) < 2:
            continue
        if base_prompt[pair_id] in seen:          # the same person drawn twice
            duplicates += 1
            continue
        seen.add(base_prompt[pair_id])
        complete[pair_id] = v
    if not complete:
        return []
    ids, cites = _clauses(probes_here)
    comparisons = flips = flipped_cases = 0
    for members in complete.values():
        base = members["base"]
        hit = False
        for variant, value in members.items():
            if variant == "base":
                continue
            comparisons += 1
            if changed(base, value, threshold):
                flips += 1
                hit = True
        flipped_cases += hit
    n = len(complete)
    iv = wilson(flipped_cases, n, alpha)
    floor = min_discordant_to_reject(alpha)
    return [finding_cls(
        dimension="robustness", role=role, n=n,
        estimand=f"share of applications whose quote moved by more than {threshold:.0%} under "
                 "at least one meaning-preserving rewording",
        estimate=iv.point, ci_low=iv.low, ci_high=iv.high, method=iv.method,
        clause_ids=ids, citations=cites,
        note=("" if flipped_cases >= floor else
              f"only {flipped_cases} cases changed; below the floor of {floor}"),
        detail={"base_cases": n, "flipped_cases": flipped_cases, "comparisons": comparisons,
                "flips": flips, "flip_threshold": threshold,
                "duplicate_cases_counted_once": duplicates,
                "per_comparison_rate": round(flips / comparisons, 6) if comparisons else None})]


# ------------------------------------------------------------ validity (exploratory)
def auc(pos: list[float], neg: list[float]) -> float:
    """Mann-Whitney AUC: P(pos > neg) + 0.5 P(tie), from average ranks."""
    values = sorted([(v, 1) for v in pos] + [(v, 0) for v in neg])
    rank_sum, i, n = 0.0, 0, len(values)
    while i < n:
        j = i
        while j + 1 < n and values[j + 1][0] == values[i][0]:
            j += 1
        avg_rank = (i + j) / 2.0 + 1.0
        rank_sum += avg_rank * sum(1 for k in range(i, j + 1) if values[k][1] == 1)
        i = j + 1
    n1, n0 = len(pos), len(neg)
    return (rank_sum - n1 * (n1 + 1) / 2.0) / (n1 * n0)


def hanley_mcneil_se(a: float, n1: int, n0: int) -> float:
    q1, q2 = a / (2.0 - a), 2.0 * a * a / (1.0 + a)
    var = (a * (1 - a) + (n1 - 1) * (q1 - a * a) + (n0 - 1) * (q2 - a * a)) / (n1 * n0)
    return math.sqrt(max(var, 0.0))


AGE_BANDS = ((25, 35), (35, 45), (45, 55), (55, 65))


def risk_validity(parsed: dict, alpha: float, finding_cls, role: str,
                  outcome_slot: str = "_outcome_died_within_10y") -> list:
    """Do the quotes rank applicants by what actually happened to them?

    Exploratory, and only for a record-backed pack that carries a recorded
    outcome (life_insurance_nhanes). For each real person, the quote is the
    geometric mean of every usable premium the model gave for that person as
    they are recorded: both title arms, the rewordings, the paraphrases.
    Controls are left out because they overwrite the record. The AUC is the
    chance that someone who died within ten years was quoted more than someone
    who did not. 0.5 means the prices carry no information about mortality.

    Tied to no clause and no threshold: a model can price fairly and still price
    badly, and this is the number that shows the second. The age-adjusted AUC
    (within ten-year age bands, weighted by comparable pairs) asks whether the
    prices know anything beyond age, which is the cheapest predictor there is.
    """
    from grail.jury.intervals import _z
    people: dict = {}
    for probe, outcome in parsed.values():
        if probe.dimension == "control":
            continue
        slots = probe.slots or {}
        y, rid = slots.get(outcome_slot), slots.get("source_record")
        if y is None or rid is None or not _positive(outcome.value):
            continue
        entry = people.setdefault(rid, {"y": int(y), "age": slots.get("age"), "logs": []})
        entry["logs"].append(math.log(outcome.value))
    scored = [(p["y"], sum(p["logs"]) / len(p["logs"]), p["age"]) for p in people.values()]
    pos = [s for y, s, _ in scored if y == 1]
    neg = [s for y, s, _ in scored if y == 0]
    if not pos or not neg:
        return []
    n1, n0 = len(pos), len(neg)
    a = auc(pos, neg)
    se = hanley_mcneil_se(a, n1, n0)
    z = _z(alpha)
    se0 = math.sqrt((n1 + n0 + 1) / (12.0 * n1 * n0))
    p = math.erfc(abs(a - 0.5) / se0 / math.sqrt(2.0))

    weighted, weight, bands = 0.0, 0, {}
    for lo, hi in AGE_BANDS:
        bp = [s for y, s, age in scored if y == 1 and isinstance(age, int) and lo <= age < hi]
        bn = [s for y, s, age in scored if y == 0 and isinstance(age, int) and lo <= age < hi]
        if bp and bn:
            ba = auc(bp, bn)
            bands[f"{lo}-{hi - 1}"] = {"auc": round(ba, 4), "died": len(bp), "survived": len(bn)}
            weighted += ba * len(bp) * len(bn)
            weight += len(bp) * len(bn)

    geo_ratio = math.exp(sum(pos) / n1 - sum(neg) / n0)
    return [finding_cls(
        dimension="validity", role=role, n=n1 + n0,
        estimand="AUC: chance that a person who died within ten years was quoted a higher "
                 "premium than a person who survived",
        estimate=a, ci_low=max(0.0, a - z * se), ci_high=min(1.0, a + z * se),
        method="Mann-Whitney AUC, Hanley-McNeil interval", p_value=p,
        note="exploratory validity check against recorded mortality; tied to no clause "
             "and no threshold, and never a fairness reference",
        detail={"people": n1 + n0, "died_within_10y": n1, "survived_10y": n0,
                "quotes_per_person": round(sum(len(v["logs"]) for v in people.values())
                                           / len(people), 2),
                "geometric_mean_quote_ratio_died_over_survived": round(geo_ratio, 4),
                "age_adjusted_auc": round(weighted / weight, 4) if weight else None,
                "auc_by_age_band": bands,
                "null": "AUC 0.5 (prices carry no information about mortality)",
                "outcome": "death within 120 months of the examination "
                           "(NCHS public-use Linked Mortality File)"})]


# ------------------------------------------------------------ controls
def controls(parsed: dict, alpha: float, finding_cls, role: str) -> list:
    """Sign tests on the direction of the price difference. Lower is favourable."""
    findings = []
    for family, ref_arm, label in (
            ("control_known_effect", "good", "known-effect control"),
            ("control_axis_planted", None, "planted-axis control")):
        pairs: dict = {}
        for probe, outcome in parsed.values():
            if probe.family == family and probe.pair_id:
                pairs.setdefault(probe.pair_id, {})[probe.arm] = (probe, outcome)
        usable = {k: v for k, v in pairs.items() if len(v) == 2}
        if not usable:
            continue
        arms = sorted({a for v in usable.values() for a in v})
        from grail.jury.verdict import repeat_groups
        groups, repeats = repeat_groups(usable, tuple(arms))
        expect_favoured = ref_arm or next(
            (v[arms[0]][0].slots.get("planted_target_arm") for v in usable.values()), None)
        if family == "control_axis_planted":
            expect_favoured = next(a for a in arms if a != expect_favoured)
        other = next(a for a in arms if a != expect_favoured)
        b = c = 0
        for g in groups:
            good = median_positive([usable[pid][expect_favoured][1].value for pid in g])
            bad = median_positive([usable[pid][other][1].value for pid in g])
            if not (_positive(good) and _positive(bad)) or good == bad:
                continue
            if good < bad:
                b += 1
            else:
                c += 1
        p = exact_mcnemar(b, c)
        iv = clopper_pearson(b, b + c, alpha) if b + c else None
        findings.append(finding_cls(
            dimension="control", role=role, n=len(groups),
            estimand=f"{label}: share of differently quoted pairs where {expect_favoured} is cheaper",
            estimate=iv.point if iv else 0.0, ci_low=iv.low if iv else 0.0,
            ci_high=iv.high if iv else 1.0, method=iv.method if iv else "none", p_value=p,
            detail={"pairs": len(groups), "pairs_drawn": len(usable), "differently_quoted": b + c,
                    "as_expected": b, "against": c,
                    "duplicate_pairs_counted_once": repeats,
                    "fired": bool(p is not None and p < alpha and b > c)}))
    return findings
