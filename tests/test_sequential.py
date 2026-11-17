"""Sequentially valid allocation — the properties the RQ3 claim rests on.

1. The fast three-point fixed rule IS the jury's rule (otherwise the replay
   compares against a different audit).
2. The uncorrected adaptive policy reproduces replay.py's purchases.
3. A confidence-sequence verdict is never more permissive than the fixed one.
4. Under a known truth, repeated looks inflate the false-verdict rate and the
   corrections bring it back to alpha.
"""
from __future__ import annotations

import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from grail.allocate.replay import (Requirement, adaptive_allocation,
                                   fairness_verdict, robustness_verdict)
from grail.allocate.sequential import (
    ALPHA, CSRule, Rule, SpendingRule, adaptive_policy, cs_bounds_rate,
    cs_fairness_verdict, cs_robustness_verdict, fairness_counts,
    fixed_fairness_verdict, fixed_robustness_verdict, look_alphas,
    null_error_rates, robustness_counts, spend_obf, spend_pocock)


def _table(rng, n, pb, pc):
    units = []
    for _ in range(n):
        u = rng.random()
        units.append((True, False) if u < pb else (False, True) if u < pb + pc
                     else ((True, True) if rng.random() < 0.6 else (False, False)))
    return units


def test_fast_fixed_rule_matches_the_jury_on_random_tables():
    rng = random.Random(3)
    for _ in range(150):
        n = rng.choice([40, 120, 400, 948, 2844])
        pb = rng.choice([0.0, 0.005, 0.01, 0.02, 0.05])
        pc = rng.choice([0.0, 0.005, 0.01, 0.02, 0.05])
        units = _table(rng, n, pb, pc)
        assert fixed_fairness_verdict(*fairness_counts(units)) == fairness_verdict(units)


def test_fast_fixed_robustness_matches_the_jury():
    for n in (20, 80, 300, 725):
        for k in range(0, n + 1, max(1, n // 40)):
            units = [("A", ["B"])] * k + [("A", ["A"])] * (n - k)
            assert fixed_robustness_verdict(*robustness_counts(units)) == robustness_verdict(units)


def test_cs_never_more_permissive_than_fixed():
    rng = random.Random(5)
    for _ in range(200):
        n = rng.choice([60, 300, 948, 2844])
        units = _table(rng, n, rng.choice([0.0, 0.01, 0.03, 0.08]),
                       rng.choice([0.0, 0.01, 0.03]))
        b, c, conc = fairness_counts(units)
        cs = cs_fairness_verdict(b, c, conc)
        if cs != "UNDETERMINED":
            assert cs == fixed_fairness_verdict(b, c, conc)
    for n in (50, 200, 725):
        for k in range(0, n + 1, max(1, n // 50)):
            cs = cs_robustness_verdict(k, n)
            if cs != "UNDETERMINED":
                assert cs == fixed_robustness_verdict(k, n)


def test_cs_bounds_contain_estimate_and_shrink():
    lo1, hi1 = cs_bounds_rate(20, 100)
    lo2, hi2 = cs_bounds_rate(200, 1000)
    assert lo1 < 0.2 < hi1 and lo2 < 0.2 < hi2
    assert (hi2 - lo2) < (hi1 - lo1)


def test_spending_sums_to_alpha():
    for fn in (spend_obf, spend_pocock):
        a = look_alphas(9, fn)
        assert abs(sum(a) - ALPHA) < 1e-9
        assert all(x > 0 for x in a)


def _reqs(seed=0):
    rng = random.Random(seed)
    out = []
    for i, (pb, pc) in enumerate([(0.06, 0.02), (0.02, 0.02), (0.03, 0.025)]):
        out.append(Requirement(f"m{i}|fairness|s", "fairness", f"m{i}", "s",
                               _table(rng, 900, pb, pc), 2))
    out.append(Requirement("m|robustness|-", "robustness", "m", "-",
                           [("A", ["B" if rng.random() < 0.3 else "A"]) for _ in range(400)], 7))
    return out


def test_uncorrected_policy_reproduces_replay_purchases():
    reqs = _reqs()
    budget = sum(r.n_available * r.cost_per_unit for r in reqs) // 2
    for s in range(4):
        t1, s1 = adaptive_allocation(reqs, budget, random.Random(1000 + s))
        t2, s2, _ = adaptive_policy(reqs, budget, random.Random(1000 + s), Rule())
        assert t1 == t2 and s1 == s2


def test_corrected_rules_spend_at_least_as_much_evidence():
    reqs = _reqs(1)
    budget = sum(r.n_available * r.cost_per_unit for r in reqs)
    _, s_fix, _ = adaptive_policy(reqs, budget, random.Random(1), Rule())
    _, s_cs, _ = adaptive_policy(reqs, budget, random.Random(1), CSRule())
    assert s_cs >= s_fix


def test_repeated_looks_inflate_error_and_cs_restores_it():
    r = null_error_rates("robustness_tol", n=400, sims=150)
    assert r["adaptive"]["false_rate"] > r["static"]["false_rate"]
    assert r["adaptive_cs"]["false_rate"] <= 0.08      # alpha 0.05 + MC slack
    assert r["adaptive_cs"]["false_rate"] <= r["adaptive"]["false_rate"]
