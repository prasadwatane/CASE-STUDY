"""S2 / S2b as pre-registered: AC1 primary, BCa one-sided bounds, three verdicts."""
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from grail.annotate.judge_validation import s2, s2b


def _raters(n=200, prev=0.7, err=0.05, seed=1):
    rng = random.Random(seed)
    truth = [rng.random() < prev for _ in range(n)]
    noisy = lambda e: [t if rng.random() > e else (not t) for t in truth]
    return truth, noisy


def test_a_judge_as_good_as_a_human_is_non_inferior():
    truth, noisy = _raters()
    a, b, j = noisy(0.05), noisy(0.05), noisy(0.05)
    res = s2(a, b, j, iterations=600)
    assert res["verdict"] == "met"
    assert res["ac1"]["lower"] > -0.10 and res["kappa"]["D"] is not None


def test_a_coin_flip_judge_is_shown_inferior():
    truth, noisy = _raters()
    rng = random.Random(9)
    a, b = noisy(0.03), noisy(0.03)
    j = [rng.random() < 0.5 for _ in a]
    assert s2(a, b, j, iterations=600)["verdict"] == "not met"


def test_s2b_needs_the_judge_to_beat_the_rule():
    truth, noisy = _raters(seed=4)
    ref = truth
    good, bad = noisy(0.03), noisy(0.30)
    assert s2b(good, bad, ref, iterations=600)["verdict"] == "met"
    assert s2b(bad, good, ref, iterations=600)["verdict"] == "not met"


def test_bounds_are_ordered_and_reproducible():
    truth, noisy = _raters(seed=7)
    a, b, j = noisy(0.08), noisy(0.08), noisy(0.10)
    r1 = s2(a, b, j, iterations=400)
    r2 = s2(a, b, j, iterations=400)
    assert r1 == r2
    assert r1["ac1"]["lower"] <= r1["ac1"]["D"] <= r1["ac1"]["upper"]
