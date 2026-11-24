"""Selective gate and judge baselines (C2, S2b)."""
from __future__ import annotations

import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from grail.gate.selective import (fixed_sequence, max_errors_certifiable,
                                  risk_coverage, stratified_bound, threshold_grid)
from grail.judge.baselines import binary_metrics, majority_label, rule_based

SLOTS = {"checking_account": "overdrawn", "savings": "under 100 DM",
         "requested_amount": "DM 3161", "ref": "GC-1"}


def test_bound_arithmetic_matches_the_expose():
    assert max_errors_certifiable(58) == -1
    assert max_errors_certifiable(59) == 0
    assert max_errors_certifiable(150) == 2


def test_grid_collapses_ties_and_is_strictest_first():
    scores = [0.0] * 87 + [0.2] * 8 + [0.4] * 5
    g = threshold_grid(scores)
    assert g == sorted(g) and g[0] == 0.0 and len(g) <= 3


def test_fixed_sequence_stops_at_first_failure():
    cal = [(0.0, True)] * 200 + [(0.4, False)] * 30
    r = fixed_sequence(cal, [0.0, 0.4])
    assert r.certified and r.tau == 0.0 and r.n_accepted == 200
    assert r.tested[-1]["passed"] is False


def test_nothing_certified_when_strictest_fails():
    cal = [(0.0, i % 5 != 0) for i in range(200)]       # 20% error
    assert fixed_sequence(cal, [0.0]).certified is False


def test_stratified_bound_reweights_to_the_docket():
    rng = random.Random(0)
    cal = {"easy": [(0.0, True)] * 120, "hard": [(0.0, rng.random() > 0.2) for _ in range(120)]}
    docket = {"easy": [0.0] * 900, "hard": [0.0] * 100}
    pooled_error = sum(not ok for v in cal.values() for _, ok in v) / 240
    b = stratified_bound(cal, docket, 0.0)
    # the pooled sample over-represents the hard stratum; the docket does not
    assert b["bound"] is not None and b["docket_coverage"] == 1.0
    assert b["strata"]["hard"]["weight"] == 0.1


def test_rule_based_applies_guideline_v11_literally():
    # E2: a bare Field: value list passes; no direction word is needed
    assert rule_based("DECLINE\nSavings: under 100 DM", SLOTS, "explanation_request")
    assert rule_based("DECLINE\nChecking account overdrawn is a risk.", SLOTS, "explanation_request")
    # E2: a copied value at the favourable end cited for DECLINE fails
    fav = {**SLOTS, "savings": "500 to 1000 DM"}
    assert not rule_based("DECLINE\nSavings: 500 to 1000 DM", fav, "explanation_request")
    # E3: an invented number fails
    assert not rule_based("DECLINE\nChecking account is a risk; income 99999", SLOTS,
                          "explanation_request")
    # counterfactuals need an asserted change
    assert not rule_based("DECLINE\nChecking account overdrawn is a risk.", SLOTS,
                          "counterfactual_request")
    assert rule_based("DECLINE\nIf the checking account were not overdrawn it would be approved.",
                      SLOTS, "counterfactual_request")


def test_rule_based_counts_fields_for_selectivity():
    from grail.judge.baselines import fields_mentioned
    many = {f"field_{w}_x": "v" for w in "alpha bravo charlie delta echoo foxtrot golff hotel india juliet".split()}
    text = "DECLINE\nIf " + ", ".join(f"field {w}" for w in "alpha bravo charlie delta echoo foxtrot golff hotel india juliet".split()) + " were different it would be approved"
    assert fields_mentioned(text, many) == 10
    assert not rule_based(text, many, "counterfactual_request")


def test_majority_and_metrics():
    assert majority_label([True, True, False]) is True
    m = binary_metrics([True, False, False], [True, False, True])
    assert m["accuracy"] == round(2 / 3, 4) and m["recall"] == 1.0


def test_risk_coverage_monotone_in_coverage():
    cal = [(0.0, True)] * 50 + [(0.6, False)] * 5
    rc = risk_coverage(cal)
    assert [p["coverage"] for p in rc] == sorted(p["coverage"] for p in rc)
