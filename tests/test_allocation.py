"""Budget allocation by replay — what the comparison must not be allowed to claim.

The failure mode here is not a wrong number, it is a flattering one: an adaptive
policy that stops early looks better on coverage precisely when it is wrong.
These tests pin the checks that make the comparison honest.
"""
from __future__ import annotations

import os
import random
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from grail.allocate.replay import (Requirement, adaptive_allocation, determinate,
                                   fairness_verdict, reference_verdicts,
                                   robustness_verdict, static_allocation, verdict)


def fair_req(key="m|fairness|marginal", n=1000, gap=0.05, seed=0):
    """n pairs where a `gap` share are discordant in favour of the ref arm."""
    rng = random.Random(seed)
    units = []
    for _ in range(n):
        r = rng.random()
        if r < gap:
            units.append((True, False))
        elif r < gap + 0.02:
            units.append((False, True))
        else:
            units.append((True, True))
    return Requirement(key, "fairness", "m", "marginal", units, 2)


def rob_req(key="m|robustness|-", n=400, flip=0.35, seed=1):
    rng = random.Random(seed)
    units = [(("A"), ["B" if rng.random() < flip else "A"]) for _ in range(n)]
    return Requirement(key, "robustness", "m", "-", units, 7)


# --- the verdict rule itself ------------------------------------------------
def test_a_clear_gap_fails_and_no_gap_does_not():
    assert fairness_verdict(fair_req(gap=0.20).units) == "FAIL"
    assert fairness_verdict([(True, True)] * 500) == "UNDETERMINED"


def test_equivalence_pass_is_withheld_below_the_discordance_floor():
    # 3 discordant pairs: the interval may sit inside the tolerance, but the
    # exact test cannot reject at any split, so no PASS may be issued
    units = [(True, False)] * 3 + [(True, True)] * 997
    assert fairness_verdict(units) != "PASS"


def test_robustness_reads_the_tolerance_in_both_directions():
    assert robustness_verdict(rob_req(flip=0.45).units) == "FAIL"
    assert robustness_verdict(rob_req(flip=0.05).units) == "PASS"
    assert determinate(robustness_verdict(rob_req(flip=0.20).units)) is False


# --- allocation policies ----------------------------------------------------
def test_static_allocation_never_exceeds_the_budget():
    reqs = [fair_req("a"), fair_req("b", seed=2), rob_req("c")]
    full = sum(r.n_available * r.cost_per_unit for r in reqs)
    for frac in (0.1, 0.5, 1.0):
        alloc = static_allocation(reqs, int(full * frac))
        spent = sum(alloc[r.key] * r.cost_per_unit for r in reqs)
        assert spent <= int(full * frac) + len(reqs)   # rounding slack only
        assert all(alloc[r.key] <= r.n_available for r in reqs)


def test_adaptive_never_exceeds_the_budget_and_may_underspend():
    reqs = [fair_req("a", gap=0.25), fair_req("b", gap=0.0, seed=3), rob_req("c")]
    full = sum(r.n_available * r.cost_per_unit for r in reqs)
    alloc, spent = adaptive_allocation(reqs, full, random.Random(0))
    assert spent <= full
    assert all(alloc[r.key] <= r.n_available for r in reqs)


def test_adaptive_stops_buying_for_a_settled_requirement():
    """A requirement that settles immediately must not keep drawing budget."""
    settled = fair_req("settled", n=2000, gap=0.30)
    open_q = fair_req("open", n=2000, gap=0.011, seed=7)
    reqs = [settled, open_q]
    full = sum(r.n_available * r.cost_per_unit for r in reqs)
    alloc, _ = adaptive_allocation(reqs, full, random.Random(0))
    assert alloc["settled"] < alloc["open"]


# --- the honesty check ------------------------------------------------------
def test_coverage_is_not_reported_without_fidelity():
    """A determinate verdict is worthless if it disagrees with the full evidence.

    This is the optional-stopping hazard in one assertion: score a requirement
    on a small prefix and on everything, and require the comparison to be
    available. If run_replay ever stops emitting fidelity, this fails.
    """
    from grail.allocate.replay import run_replay
    reqs = [fair_req("a", gap=0.03), rob_req("c")]
    full = sum(r.n_available * r.cost_per_unit for r in reqs)
    rows = run_replay(reqs, [full // 4, full], seeds=3)
    assert rows and all("fidelity" in r and "contradictions_max" in r for r in rows)
    for r in rows:
        assert 0.0 <= r["fidelity"] <= 1.0
        assert r["contradictions_max"] >= 0


def test_reference_verdicts_use_every_unit():
    reqs = [fair_req("a", gap=0.20), rob_req("c", flip=0.45)]
    ref = reference_verdicts(reqs)
    assert ref["a"] == verdict(reqs[0], reqs[0].units)
    assert ref["c"] == "FAIL"
