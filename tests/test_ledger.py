"""The ledger — what makes a number admissible rather than merely true.

The jury and the judge decide whether a finding is correct. These tests are
about the narrower question the ledger answers: does the finding carry what a
reader needs in order to check it, and can it be quietly changed afterwards.
"""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from grail.ledger import Entry, Ledger, UntraceableFinding


def entry(**kw) -> Entry:
    base = dict(clause_ids=["AIA:Art10(2)(f)"], dimension="fairness",
                estimand="paired difference in favourable outcome under a title swap",
                evidence_type="deterministic", sample_kind="core", verdict="FAIL",
                n=4740, estimate=0.0196, ci_low=0.0158, ci_high=0.0241,
                method="exact McNemar, profile-likelihood interval")
    base.update(kw)
    return Entry(**base)


# --- admissibility ----------------------------------------------------------
def test_a_finding_with_no_clause_is_refused():
    """The invariant that keeps this an audit rather than a benchmark."""
    with pytest.raises(UntraceableFinding, match="names no clause"):
        entry(clause_ids=[]).check()


def test_judged_evidence_must_name_its_judge():
    """A model verdict whose author is unrecorded cannot be excluded later."""
    with pytest.raises(UntraceableFinding, match="no judge named"):
        entry(evidence_type="judged", judge_id="").check()


def test_a_judge_on_deterministic_evidence_is_a_contradiction():
    with pytest.raises(UntraceableFinding, match="One of the two is wrong"):
        entry(evidence_type="deterministic", judge_id="microsoft/phi-4").check()


def test_an_empty_sample_is_not_a_weak_finding():
    with pytest.raises(UntraceableFinding, match="not a finding"):
        entry(n=0).check()


def test_undetermined_is_a_verdict_and_a_missing_one_is_not():
    entry(verdict="UNDETERMINED").check()          # fine
    with pytest.raises(UntraceableFinding, match="is not one of"):
        entry(verdict="").check()


# --- what may carry a headline ----------------------------------------------
def test_only_the_pre_registered_sample_carries_a_headline():
    assert entry(sample_kind="core").headline_eligible
    assert not entry(sample_kind="control").headline_eligible
    assert not entry(sample_kind="adaptive").headline_eligible


def test_an_unvalidated_judge_cannot_carry_a_headline():
    """Its verdicts are an input to the validation study, not a result.

    This is the whole reason the annotation study exists, so the ledger refuses
    to let a judged number graduate into a claim before that study has run.
    """
    judged = dict(evidence_type="judged", judge_id="microsoft/phi-4",
                  clause_ids=["AIA:Art13(1)"], dimension="transparency")
    assert not entry(**judged, judge_validated=False).headline_eligible
    assert entry(**judged, judge_validated=True).headline_eligible


# --- the chain --------------------------------------------------------------
def test_the_chain_detects_a_deleted_finding(tmp_path):
    """The discipline matters most when a result is inconvenient."""
    p = str(tmp_path / "ledger.jsonl")
    led = Ledger(p)
    for i in range(3):
        led.append(entry(estimand=f"finding {i}"))
    assert led.verify()[0]

    lines = open(p).read().splitlines()
    open(p, "w").write("\n".join([lines[0], lines[2]]) + "\n")   # drop the middle
    ok, why = Ledger(p).verify()
    assert not ok and "removed, reordered or inserted" in why


def test_the_chain_detects_an_edited_finding(tmp_path):
    p = str(tmp_path / "ledger.jsonl")
    led = Ledger(p)
    led.append(entry(estimate=0.0196, verdict="FAIL"))
    doctored = open(p).read().replace('"verdict": "FAIL"', '"verdict": "PASS"')
    open(p, "w").write(doctored)
    ok, why = Ledger(p).verify()
    assert not ok and "edited after" in why


def test_appending_survives_a_reopen(tmp_path):
    p = str(tmp_path / "ledger.jsonl")
    Ledger(p).append(entry(estimand="first"))
    Ledger(p).append(entry(estimand="second"))     # fresh handle, same file
    led = Ledger(p)
    assert len(led) == 2 and led.verify()[0]
    assert [e.estimand for e in led.entries] == ["first", "second"]


def test_findings_can_be_read_back_per_clause(tmp_path):
    p = str(tmp_path / "ledger.jsonl")
    led = Ledger(p)
    led.append(entry(clause_ids=["AIA:Art10(2)(f)", "AIA:Art10(2)(g)"]))
    led.append(entry(clause_ids=["AIA:Art15(1)"], dimension="robustness"))
    assert len(led.for_clause("AIA:Art10(2)(g)")) == 1
    assert led.clauses() == ["AIA:Art10(2)(f)", "AIA:Art10(2)(g)", "AIA:Art15(1)"]
