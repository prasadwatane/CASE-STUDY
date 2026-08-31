"""The jury, and a simulation study that calibrates it against known truth.

The project's central argument is that a measuring instrument has to be shown
capable of detecting an effect before its nulls mean anything. That argument
applies to the estimator exactly as it applies to the probe pipeline, and it is
cheap to honour: generate matched-pair data with a difference you chose, run the
jury, and check it recovers what you put in.

Three properties are asserted, and they are the three that make an interval
worth quoting:

  COVERAGE     a 95% interval contains the true value about 95% of the time
  TYPE I       at a true difference of zero, it rejects at most about 5%
  POWER        at a difference worth detecting, it usually does

Without these the intervals are decoration. With them, "no effect detected"
becomes a statement about the audited system rather than about the arithmetic.
"""
from __future__ import annotations

import os
import random
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from grail.jury.intervals import (clopper_pearson, exact_mcnemar,
                                  min_discordant_to_reject, newcombe_diff,
                                  paired_diff, wilson)
from grail.jury.verdict import CONFIRMATORY, EXPLORATORY, deliberate, fairness


# --- interval machinery -----------------------------------------------------
def test_wilson_behaves_where_wald_does_not():
    """Zero successes must still give a usable, in-range interval."""
    iv = wilson(0, 100)
    assert iv.low == 0.0 and 0 < iv.high < 0.05
    iv = wilson(100, 100)
    assert iv.high == 1.0 and 0.95 < iv.low < 1.0
    # Wald would give [0, 0] at k=0 — a claim of certainty from no evidence.


def test_clopper_pearson_is_conservative_relative_to_wilson():
    cp, wi = clopper_pearson(59, 66), wilson(59, 66)
    assert cp.low <= wi.low and cp.high >= wi.high


def test_paired_interval_ignores_the_concordant_split():
    """Concordant pairs carry almost no information about the difference.

    Worth asserting rather than assuming: it means the headline number does not
    depend on a quantity the report never separates out.
    """
    a_vals = [63, 300, 1389, 2700]
    outs = [paired_diff(a, 59, 7, 2778 - a) for a in a_vals]
    assert len({round(o.low, 4) for o in outs}) == 1
    assert len({round(o.high, 4) for o in outs}) == 1


def test_paired_interval_agrees_with_wald_when_wald_is_valid():
    """A cross-check: two methods, one answer, where both are trustworthy."""
    import math
    a, b, c, d = 63, 59, 7, 2715
    n = a + b + c + d
    iv = paired_diff(a, b, c, d)
    se = math.sqrt(b + c - (b - c) ** 2 / n) / n
    assert abs(iv.low - ((b - c) / n - 1.96 * se)) < 0.002
    assert abs(iv.high - ((b - c) / n + 1.96 * se)) < 0.002


def test_exact_mcnemar_floor():
    assert min_discordant_to_reject(0.05) == 6
    assert exact_mcnemar(4, 0) == pytest.approx(0.125)     # cannot reject
    assert exact_mcnemar(6, 0) == pytest.approx(0.03125)   # just can
    assert exact_mcnemar(0, 0) is None


def test_newcombe_stays_in_range():
    iv = newcombe_diff(0, 50, 50, 50)
    assert -1.0 <= iv.low and iv.high <= 1.0


# --- the simulation study ---------------------------------------------------
def _simulate(n_pairs: int, discordance: float, psi: float, rng,
              base: float = 0.18) -> tuple:
    """Matched pairs, parameterised the way the design actually behaves.

    An earlier version of this generator specified a raw difference and let the
    discordance rate fall where it may, which produced 37% discordant pairs —
    sixteen times what the audit observes. That inflates the noise the test has
    to see through and made a well-powered design look underpowered, so the
    simulation was measuring the generator rather than the jury.

    The honest parameters are the two the instrument reports: how often a pair
    disagrees at all, and how lopsided those disagreements are. The true
    difference follows as discordance x (2 psi - 1).
    """
    b = c = 0
    for _ in range(n_pairs):
        if rng.random() < discordance:
            if rng.random() < psi:
                b += 1
            else:
                c += 1
    conc = n_pairs - b - c
    a = sum(1 for _ in range(conc) if rng.random() < base)
    return a, b, c, conc - a


def true_delta(discordance: float, psi: float) -> float:
    return discordance * (2 * psi - 1)


@pytest.mark.parametrize("discordance,psi", [(0.023, 0.5), (0.023, 0.894),
                                             (0.10, 0.75), (0.30, 0.60)])
def test_paired_interval_covers_the_truth(discordance, psi):
    """COVERAGE — a 95% interval should contain the true value ~95% of the time."""
    rng = random.Random(20260824)
    delta = true_delta(discordance, psi)
    trials, hits = 400, 0
    for _ in range(trials):
        a, b, c, d = _simulate(2844, discordance, psi, rng)
        iv = paired_diff(a, b, c, d)
        hits += iv.low <= delta <= iv.high
    coverage = hits / trials
    assert 0.90 <= coverage <= 1.0, (
        f"coverage {coverage:.3f} at discordance={discordance}, psi={psi}")


def test_type_one_error_is_controlled():
    """TYPE I — with disagreements symmetric, rejection should be rare."""
    rng = random.Random(7)
    trials, rejects = 400, 0
    for _ in range(trials):
        a, b, c, d = _simulate(2844, 0.023, 0.5, rng)
        p = exact_mcnemar(b, c)
        rejects += p is not None and p < 0.05
    rate = rejects / trials
    assert rate <= 0.08, f"type I error {rate:.3f} — the test rejects too readily"


def test_power_at_the_observed_effect_size():
    """POWER — the real finding's effect size should be caught almost always.

    2844 pairs at 2.3% discordance and psi = 0.894: the configuration the
    audit actually produced. If the jury could not reliably detect this, the
    reported p-value would be a lucky draw rather than a measurement.
    """
    rng = random.Random(11)
    trials, rejects = 200, 0
    for _ in range(trials):
        a, b, c, d = _simulate(2844, 0.023, 0.894, rng)
        p = exact_mcnemar(b, c)
        rejects += p is not None and p < 0.05
    assert rejects / trials >= 0.95, f"power {rejects / trials:.2f}"


def test_power_at_the_pre_registered_effect_size():
    """POWER — and at the weaker asymmetry that was actually pre-registered."""
    rng = random.Random(13)
    trials, rejects = 200, 0
    for _ in range(trials):
        a, b, c, d = _simulate(2844, 0.023, 0.75, rng)
        p = exact_mcnemar(b, c)
        rejects += p is not None and p < 0.05
    assert rejects / trials >= 0.80, f"power {rejects / trials:.2f} at psi=0.75"


# --- the jury as a whole ----------------------------------------------------
def _pairs_to_parsed(table, stratum, arms=("female", "male")):
    """Build the parsed structure the jury consumes, from a 2x2 table."""
    from grail.probe.schema import CORE, GOLD_NONE, Probe
    from grail.run.parse import Outcome, PARSED

    a, b, c, d = table
    parsed, i = {}, 0
    for count, (x, y) in ((a, (1, 1)), (b, (1, 0)), (c, (0, 1)), (d, (0, 0))):
        for _ in range(count):
            i += 1
            pair_id = f"finance:fairness:gender:{i:05d}"
            for arm, good in zip(arms, (x, y)):
                p = Probe(id=f"{pair_id}:{arm}", domain="finance",
                          dimension="fairness", family="f",
                          clause_ids=["AIA:Art10(2)(f)"], citations=["Article 10(2)(f)"],
                          prompt=f"Applicant {i} {arm}", sample_kind=CORE,
                          stratum=stratum, pair_id=pair_id, axis="gender", arm=arm,
                          gold_route=GOLD_NONE)
                parsed[p.id] = (p, Outcome(PARSED, "APPROVE" if good else "DECLINE"))
    return parsed


def test_jury_marks_exactly_one_confirmatory_endpoint():
    """Two views of one test must not become two primary endpoints."""
    parsed = _pairs_to_parsed((63, 59, 7, 2715), "marginal")
    fs = fairness(parsed, primary_stratum="marginal")
    confirmatory = [f for f in fs if f.role == CONFIRMATORY]
    assert len(confirmatory) == 1, [f.estimand for f in confirmatory]
    assert "paired difference" in confirmatory[0].estimand


def test_jury_recovers_the_real_finding():
    parsed = _pairs_to_parsed((63, 59, 7, 2715), "marginal")
    f = next(x for x in fairness(parsed, "marginal") if x.role == CONFIRMATORY)
    assert f.p_value < 1e-9
    assert f.estimate == pytest.approx(0.0183, abs=0.0005)
    assert f.ci_low > 0 and f.detail["can_reject_at_all"]


def test_jury_flags_a_stratum_that_could_not_have_rejected():
    parsed = _pairs_to_parsed((63, 4, 0, 326), "marginal")
    f = next(x for x in fairness(parsed, "marginal") if x.role == CONFIRMATORY)
    assert not f.detail["can_reject_at_all"]
    assert "cannot reach" in f.note


def test_non_primary_strata_are_exploratory():
    parsed = _pairs_to_parsed((22, 22, 0, 904), "strong")
    assert all(f.role == EXPLORATORY for f in fairness(parsed, "marginal"))


def test_deliberate_refuses_an_unknown_model():
    with pytest.raises(ValueError):
        deliberate([], [], "nobody/nothing")
