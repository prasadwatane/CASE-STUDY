"""A repeated applicant is one observation, not several.

The Statlog-backed credit set draws 1,000 records with replacement, so its
marginal stratum holds 2,844 pairs but only 333 different applicants. At
temperature 0 a repeated prompt gets the same answer, so counting repeats as
independent pairs makes every interval far too narrow. These tests pin the
correction: the yes/no jury, the controls and the RQ1 replay all score each
distinct pair of prompts once, and say how many repeats they dropped.
"""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from grail.allocate.replay import build_requirements
from grail.jury.continuous import median_positive
from grail.jury.verdict import _parsed, deliberate, distinct_cases, distinct_pairs, modal
from grail.probe.generate import generate_probeset
from grail.run.client import StubModel
from grail.run.runner import run
from tests.test_insurance import _signed      # fairness + robustness items

# 600 pairs: 360 in the marginal stratum, drawn from ~333 Statlog records
SIZES = {"fairness": 600, "robustness": 60, "consistency": 5, "transparency": 4,
         "truthfulness": 300}


def _favours_ms(prompt: str) -> str:
    """Approve every Ms. application and decline every Mr. one: maximal discordance."""
    line = next((l for l in prompt.splitlines() if l.startswith("Applicant:")), "")
    return "APPROVE" if "Ms." in line else "DECLINE"


@pytest.fixture(scope="module")
def credit_run(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("repeats")
    ps, _ = generate_probeset(_signed(tmp, "finance"), core_n=SIZES)
    records, _ = run(ps.probes, StubModel(rule=_favours_ms, model_id="stub/ms"),
                     str(tmp / "r.jsonl"), allow_stub=True)
    return ps.probes, records


def _distinct_marginal(probes):
    pairs = {}
    for p in probes:
        if p.dimension == "fairness" and p.stratum == "marginal":
            pairs.setdefault(p.pair_id, {})[p.arm] = p.prompt
    prompts = {tuple(sorted(v.items())) for v in pairs.values() if len(v) == 2}
    return len(pairs), len(prompts)


def test_the_credit_set_does_repeat_applicants(credit_run):
    probes, _ = credit_run
    drawn, distinct = _distinct_marginal(probes)
    assert drawn == 360 and distinct < drawn


def test_jury_counts_each_applicant_once(credit_run):
    probes, records = credit_run
    drawn, distinct = _distinct_marginal(probes)
    res = deliberate(probes, records, "stub/ms", primary_stratum="marginal")
    f = next(f for f in res["confirmatory"] if f["dimension"] == "fairness")
    assert f["n"] == distinct
    assert f["detail"]["pairs_drawn"] == drawn
    assert f["detail"]["duplicate_pairs_counted_once"] == drawn - distinct
    # every distinct pair is discordant in the Ms. direction, once
    assert f["detail"]["female_only"] == distinct and f["detail"]["male_only"] == 0
    assert "counted once" in f["note"]


def test_robustness_counts_each_application_once(credit_run):
    probes, records = credit_run
    bases = {p.prompt for p in probes if p.dimension == "robustness" and p.variant == "base"}
    n_cases = len({p.pair_id for p in probes if p.dimension == "robustness"})
    res = deliberate(probes, records, "stub/ms", primary_stratum="marginal")
    rob = next(f for f in res["findings"] if f["dimension"] == "robustness")
    assert rob["n"] == len(bases)
    assert rob["detail"]["duplicate_cases_counted_once"] == n_cases - len(bases)


def test_replay_units_follow_the_jury(credit_run):
    probes, records = credit_run
    parsed, _ = _parsed(probes, records, "stub/ms")
    reqs = {r.key: r for r in build_requirements({"stub/ms": parsed})}
    drawn, distinct = _distinct_marginal(probes)
    assert reqs["ms|fairness|marginal"].n_available == distinct
    bases = {p.prompt for p in probes if p.dimension == "robustness" and p.variant == "base"}
    assert reqs["ms|robustness|-"].n_available == len(bases)


class _P:
    def __init__(self, prompt):
        self.prompt = prompt


def test_the_first_pair_by_id_is_kept():
    pairs = {"x:0002": {"a": (_P("p1"), None), "b": (_P("q1"), None)},
             "x:0001": {"a": (_P("p1"), None), "b": (_P("q1"), None)},
             "x:0003": {"a": (_P("p2"), None), "b": (_P("q2"), None)}}
    keep, repeats = distinct_pairs(pairs, ("a", "b"))
    assert keep == {"x:0001", "x:0003"} and repeats == 1
    keep, repeats = distinct_cases({"r:2": "base A", "r:1": "base A", "r:3": "base B"})
    assert keep == {"r:1", "r:3"} and repeats == 1


def test_repeats_that_disagree_take_the_majority_answer():
    assert modal([True, True, False]) is True
    assert modal([False, True, False]) is False
    assert modal([True, False]) is True and modal([False, True]) is False   # tie: first by id
    assert median_positive([500.0, None, 520.0, 510.0]) == 510.0
    assert median_positive([500.0, 520.0]) == 510.0
    assert median_positive([None, -1.0]) is None
