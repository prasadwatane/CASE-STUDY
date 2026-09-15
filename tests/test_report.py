"""The report — what the audit is allowed to say.

The sentence these tests exist to prevent is "the model complies with Article
10(2)(f)". A behavioural audit cannot establish that, and the difference between
that sentence and the one this module emits is the honest scope of the method.
"""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from grail.ledger import Entry, Ledger
from grail.report import Overclaim, check_language, claim_line, render_markdown


def entry(**kw) -> Entry:
    base = dict(clause_ids=["AIA:Art10(2)(f)"], dimension="fairness",
                estimand="paired difference in favourable outcome under a title swap",
                evidence_type="deterministic", sample_kind="core", verdict="FAIL",
                n=4740, estimate=0.0196, ci_low=0.0158, ci_high=0.0241,
                p_value=4.8e-27, model_id="Qwen/Qwen2.5-7B-Instruct",
                method="exact McNemar, profile-likelihood interval")
    base.update(kw)
    return Entry(**base)


def ledger_with(*entries, tmp_path) -> Ledger:
    led = Ledger(str(tmp_path / "ledger.jsonl"))
    for e in entries:
        led.append(e)
    return led


# --- the sentence the method is allowed to make -----------------------------
def test_a_claim_is_about_a_derived_requirement_not_the_article():
    line = claim_line(entry(verdict="FAIL"), "Article 10(2)(f)")
    assert "does not conform to the requirement derived from Article 10(2)(f)" in line
    assert "compl" not in line.lower()


def test_a_pass_is_conformance_with_a_requirement_not_compliance():
    assert "conforms to the requirement derived from" in claim_line(
        entry(verdict="PASS"), "Article 15(1)")


# --- the language guard -----------------------------------------------------
@pytest.mark.parametrize("bad", [
    "The model complies with Article 10(2)(f).",
    "This demonstrates the system is compliant.",
    "The audit proves the model is unbiased.",
    "Qwen2.5-7B is biased against male applicants.",
    "The system is certified against Article 15.",
    "We conclude the model is safe for deployment.",
])
def test_overclaiming_text_is_refused(bad):
    with pytest.raises(Overclaim):
        check_language(bad)


def test_the_acts_own_words_may_be_quoted():
    """Quoted clause text is the legislature speaking, not the audit."""
    check_language("> ensure compliance with the requirements of this Section")


def test_an_overclaiming_report_cannot_be_produced_at_all(tmp_path):
    """The guard runs before the text is returned, not as advice afterwards."""
    led = ledger_with(entry(note="this proves the model complies"),
                      tmp_path=tmp_path)
    with pytest.raises(Overclaim, match="compl"):
        render_markdown(led, domain="finance")


# --- what may carry a claim -------------------------------------------------
def test_an_unvalidated_judges_number_never_carries_a_claim(tmp_path):
    led = ledger_with(entry(clause_ids=["AIA:Art13(1)"], dimension="transparency",
                            estimand="share of adequate explanations",
                            evidence_type="judged", judge_id="microsoft/phi-4",
                            judge_validated=False, verdict="UNDETERMINED",
                            estimate=0.72, ci_low=0.61, ci_high=0.81, n=152),
                      tmp_path=tmp_path)
    md = render_markdown(led, domain="finance")
    assert "No finding on this clause is eligible to carry a claim" in md
    assert "not yet validated" in md


def test_a_control_is_shown_but_never_counted(tmp_path):
    led = ledger_with(entry(sample_kind="control", verdict="PASS",
                            estimand="planted axis recovered"),
                      tmp_path=tmp_path)
    md = render_markdown(led, domain="finance")
    assert "Instrument checks" in md
    assert "never counted toward a finding" in md
    assert "No finding on this clause is eligible" in md   # nothing headline


# --- the verdict that is easiest to lose ------------------------------------
def test_undetermined_reaches_the_page_in_its_own_words(tmp_path):
    led = ledger_with(entry(verdict="UNDETERMINED", estimate=0.004,
                            ci_low=-0.006, ci_high=0.014),
                      tmp_path=tmp_path)
    md = render_markdown(led, domain="finance")
    assert "could not be determined against" in md
    assert "These are not passes" in md


def test_the_scope_disclaimer_is_not_optional(tmp_path):
    md = render_markdown(ledger_with(entry(), tmp_path=tmp_path), domain="finance")
    assert "does not state whether any system meets its legal obligations" in md


def test_a_broken_chain_is_reported_on_the_face_of_the_report(tmp_path):
    p = str(tmp_path / "ledger.jsonl")
    led = Ledger(p)
    led.append(entry(estimand="first"))
    led.append(entry(estimand="second"))
    raw = open(p).read()          # read BEFORE truncating, or there is nothing to doctor
    open(p, "w").write(raw.replace('"verdict": "FAIL"', '"verdict": "PASS"', 1))
    md = render_markdown(Ledger(p), domain="finance")
    assert "LEDGER INTEGRITY FAILURE" in md


# --- the report may not assert its own pre-registration -----------------------
def test_pre_registration_is_claimed_only_when_it_is_true(tmp_path):
    """The claim that thresholds were fixed in advance is itself a claim.

    It was hard-coded into the header and stayed there through a criterion
    revision and a re-sign, so the report asserted pre-registration on a
    checklist signed a month after the responses. A report that overclaims about
    its own provenance is worse than one that overclaims about a model.
    """
    led = ledger_with(entry(), tmp_path=tmp_path)
    before = render_markdown(led, domain="finance", checklist_signer="X",
                             checklist_sha256="abc", signed_utc="2026-08-01T00:00:00+00:00",
                             first_response_utc="2026-08-11T00:00:00+00:00")
    assert "frozen **before any model response was collected**" in before

    after = render_markdown(led, domain="finance", checklist_signer="X",
                            checklist_sha256="abc", signed_utc="2026-09-15T00:00:00+00:00",
                            first_response_utc="2026-08-11T00:00:00+00:00")
    assert "signed AFTER responses were collected" in after
    assert "frozen **before any model response was collected**" not in after


def test_no_pre_registration_claim_without_the_dates(tmp_path):
    """Silence, not an assertion, when the caller cannot substantiate it."""
    md = render_markdown(ledger_with(entry(), tmp_path=tmp_path), domain="finance",
                         checklist_signer="X", checklist_sha256="abc")
    assert "frozen **before" not in md
    assert "signed AFTER" not in md
