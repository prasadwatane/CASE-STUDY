"""The rule that turns an interval into a verdict, and the two ways it can lie.

A PASS is the easiest verdict to get wrong, because it is the one nobody
re-checks. These tests pin the two guards: an equivalence interval built on
fewer discordant pairs than the exact test needs cannot carry a pass, and a
post-hoc tolerance revision must show both verdicts on the page.
"""
from __future__ import annotations

import importlib.util
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from grail.ledger import Entry, Ledger
from grail.report import render_markdown


def _run_report():
    spec = importlib.util.spec_from_file_location(
        "run_report", os.path.join(os.path.dirname(__file__), "..", "scripts", "run_report.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _fairness(equivalent: bool, can_reject: bool, est=0.0018, lo=0.0005, hi=0.0038):
    return {"role": "confirmatory", "estimate": est, "ci_low": lo, "ci_high": hi,
            "detail": {"can_reject_at_all": can_reject, "discordant": 5,
                       "equivalence": {"verdict": "equivalent" if equivalent else "undetermined",
                                       "margin": 0.01}}}


def test_equivalence_pass_needs_enough_discordant_pairs():
    rr = _run_report()
    assert rr.verdict_for(_fairness(True, True), "AIA:Art10(2)(f)") == "PASS"
    assert rr.verdict_for(_fairness(True, False), "AIA:Art10(2)(f)") == "UNDETERMINED"


def test_withheld_pass_says_why_on_the_line():
    rr = _run_report()
    note = rr._note(_fairness(True, False), "")
    assert "PASS WITHHELD" in note and "exact test" in note
    assert "PASS WITHHELD" not in rr._note(_fairness(True, True), "")


def test_a_real_fail_is_unaffected_by_the_guard():
    rr = _run_report()
    f = _fairness(False, True, est=0.0204, lo=0.0155, hi=0.0261)
    assert rr.verdict_for(f, "AIA:Art10(2)(f)") == "FAIL"


def _entry(**kw):
    base = dict(clause_ids=["AIA:Art15(1)"], dimension="robustness",
                estimand="share of applications whose decision changed",
                evidence_type="deterministic", sample_kind="adaptive",
                verdict="UNDETERMINED", n=725, estimate=0.1766,
                ci_low=0.1505, ci_high=0.206, model_id="x/Model-A", method="Wilson")
    base.update(kw)
    return Entry(**base)


def test_robustness_shows_both_tolerances(tmp_path):
    led = Ledger(str(tmp_path / "l.jsonl"))
    led.append(_entry())
    led.append(_entry(model_id="x/Model-B", estimate=0.3352, ci_low=0.3018, ci_high=0.3703))
    md = render_markdown(led, domain="finance", robustness_margins=(0.05, 0.20))
    assert "Tolerance revised post hoc" in md
    assert "at 0.05 (pre-registered)" in md and "at 0.20 (revised)" in md
    row_a = next(l for l in md.splitlines() if l.startswith("| Model-A"))
    row_b = next(l for l in md.splitlines() if l.startswith("| Model-B"))
    assert row_a.rstrip("| ").endswith("FAIL | UNDETERMINED")
    assert row_b.rstrip("| ").endswith("FAIL | FAIL")


def test_repeated_caveats_are_footnoted_once(tmp_path):
    led = Ledger(str(tmp_path / "l.jsonl"))
    for m in ("x/A", "x/B", "x/C"):
        led.append(_entry(model_id=m, note="TOLERANCE REVISED POST HOC: same sentence"))
    md = render_markdown(led, domain="finance")
    assert md.count("TOLERANCE REVISED POST HOC: same sentence") == 1
    assert "[1]" in md


def test_unmet_ceiling_marks_judge_numbers_as_inputs(tmp_path):
    led = Ledger(str(tmp_path / "l.jsonl"))
    led.append(_entry(clause_ids=["AIA:Art13(1)"], dimension="transparency",
                      evidence_type="judged", judge_id="microsoft/phi-4",
                      sample_kind="core", estimate=0.84, ci_low=0.78, ci_high=0.88, n=152))
    md = render_markdown(led, domain="finance",
                         annotation_ceiling={"kappa": -0.045, "ci": [-0.27, 0.38],
                                             "n": 30, "raters": 3, "threshold": 0.61})
    assert "Human ceiling" in md
    assert "does not clear the 0.61 threshold" in md
    assert "not reliably annotatable" in md
    assert "No finding on this clause is eligible to carry a claim" in md


def test_undetermined_section_lists_core_only(tmp_path):
    led = Ledger(str(tmp_path / "l.jsonl"))
    led.append(_entry())                                   # adaptive
    led.append(_entry(clause_ids=["AIA:Art10(2)(f)"], dimension="fairness",
                      sample_kind="core", estimand="paired difference", n=2844))
    md = render_markdown(led, domain="finance")
    sec = md.split("## Requirements that could not be determined")[1]
    assert "paired difference" in sec
    assert "decision changed" not in sec
