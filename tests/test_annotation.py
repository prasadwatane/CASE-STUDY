"""Tests for the annotation study.

Most of these guard against a κ that looks fine and means nothing. The degenerate
case is the important one: two raters who label every item the same way have
chance agreement of 1.0, so κ is 0/0. Returning 0.0 there — as several
implementations do — reports "no agreement" when the truth is "perfect agreement,
nothing to correct against", and that number would go straight into a thesis.
"""
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from grail.annotate.agreement import (agreement, bootstrap_ci, cohen_kappa,
                                      interpret, n_for_kappa_lower_bound)
from grail.annotate.report import score
from grail.annotate.study import (PRIMARY, SECOND, StudyDesign, allocate, assign,
                                  export, load_sheet, select, token_for)

LABELS = ["adequate", "inadequate"]


# --- kappa ------------------------------------------------------------------
def test_perfect_agreement_with_variance_is_one():
    a = ["adequate", "inadequate"] * 20
    k, po, pe, reason = cohen_kappa(a, list(a))
    assert k == pytest.approx(1.0) and po == 1.0 and reason == ""


def test_constant_labels_make_kappa_undefined_not_zero():
    """The trap: 100% agreement, chance agreement also 100%, so kappa is 0/0."""
    a = ["adequate"] * 40
    k, po, pe, reason = cohen_kappa(a, list(a))
    assert k is None, "returned a number where kappa is undefined"
    assert po == 1.0 and pe == pytest.approx(1.0)
    assert "single label" in reason
    ag = agreement(a, list(a))
    assert ag.kappa is None and ag.ci_low is None
    assert not ag.meets(0.61), "an undefined kappa must not satisfy a threshold"


def test_chance_level_agreement_is_about_zero():
    a = ["adequate", "inadequate"] * 50
    b = ["adequate", "adequate", "inadequate", "inadequate"] * 25
    k, _, _, _ = cohen_kappa(a, b)
    assert abs(k) < 0.15


def test_kappa_is_below_raw_agreement_when_one_label_dominates():
    """Why raw agreement alone is never reported: it flatters a skewed task.

    91% agreement sounds excellent. Corrected for the 81% two raters would reach
    by chance on a task this skewed, it is a κ of 0.52 — moderate at best.
    """
    a = ["adequate"] * 90 + ["inadequate"] * 10
    b = (["adequate"] * 85 + ["inadequate"] * 5
         + ["adequate"] * 4 + ["inadequate"] * 6)
    ag = agreement(a, b, iterations=400)
    assert ag.percent_agreement == pytest.approx(0.91)
    assert ag.expected_agreement > 0.80
    assert ag.kappa == pytest.approx(0.52, abs=0.02)
    assert ag.kappa < ag.percent_agreement - 0.35


def test_mismatched_lengths_are_refused():
    with pytest.raises(ValueError):
        cohen_kappa(["adequate"], ["adequate", "inadequate"])


# --- intervals --------------------------------------------------------------
def test_bootstrap_interval_brackets_the_estimate_and_is_reproducible():
    a = ["adequate"] * 60 + ["inadequate"] * 40
    b = ["adequate"] * 52 + ["inadequate"] * 8 + ["inadequate"] * 34 + ["adequate"] * 6
    ag = agreement(a, b, iterations=500)
    assert ag.ci_low < ag.kappa < ag.ci_high
    again = agreement(a, b, iterations=500)
    assert (again.ci_low, again.ci_high) == (ag.ci_low, ag.ci_high)


def test_threshold_is_judged_on_the_lower_bound_not_the_estimate():
    """A point estimate above 0.61 with an interval crossing it is not evidence."""
    a = ["adequate"] * 20 + ["inadequate"] * 20
    b = ["adequate"] * 17 + ["inadequate"] * 3 + ["inadequate"] * 17 + ["adequate"] * 3
    ag = agreement(a, b, iterations=500)
    assert ag.kappa > 0.61
    if ag.ci_low < 0.61:
        assert not ag.meets(0.61)


def test_overlap_sizing_grows_as_the_margin_narrows():
    """86 is the bare minimum at κ≈0.75; the study plans 120 to leave margin."""
    assert n_for_kappa_lower_bound(0.61, 0.75) == 86
    assert n_for_kappa_lower_bound(0.61, 0.85) < n_for_kappa_lower_bound(0.61, 0.75)
    assert n_for_kappa_lower_bound(0.61, 0.70) > n_for_kappa_lower_bound(0.61, 0.75)
    with pytest.raises(ValueError):
        n_for_kappa_lower_bound(0.80, 0.70)      # expected must exceed the target


def test_the_planned_overlap_clears_the_minimum_with_margin():
    from grail.annotate.study import StudyDesign
    assert StudyDesign(domain="finance").n_overlap >= n_for_kappa_lower_bound(0.61, 0.75) * 1.35


def test_interpretation_bands():
    assert interpret(None) == "undefined"
    assert interpret(0.1) == "slight"
    assert interpret(0.65) == "substantial"
    assert interpret(0.9) == "almost perfect"


# --- design and export ------------------------------------------------------
def _candidates(n=400):
    out = []
    for i in range(n):
        strata = ["random"]
        if i % 3 == 0:
            strata.append("fairness_marginal")
        if i % 5 == 0:
            strata.append("judge_high_confidence")
        if i % 7 == 0:
            strata.append("judge_borderline")
        out.append({"probe_id": f"p{i:04d}", "dimension": "transparency",
                    "criterion": "states the decisive details",
                    "prompt": f"prompt {i}", "response": f"response {i}",
                    "strata": strata})
    return out


def test_allocation_sums_exactly():
    d = StudyDesign(domain="finance", n_items=300, n_overlap=120)
    a = allocate(d)
    assert sum(a.values()) == 300


def test_selection_is_deterministic_and_stratified():
    d = StudyDesign(domain="finance", n_items=100, n_overlap=40)
    a = select(_candidates(), d)
    b = select(_candidates(), d)
    assert [x["probe_id"] for x in a] == [x["probe_id"] for x in b]
    assert len({x["probe_id"] for x in a}) == len(a), "an item was selected twice"
    assert len({x["stratum"] for x in a}) > 1


def test_a_stratum_shortfall_is_reported_not_topped_up():
    """Quietly filling a stratum with random items fakes coverage."""
    thin = [{"probe_id": f"q{i}", "strata": ["random"], "dimension": "transparency",
             "prompt": "p", "response": "r", "criterion": "c"} for i in range(50)]
    d = StudyDesign(domain="finance", n_items=40, n_overlap=10)
    items = select(thin, d)
    shortfall = items[0]["_shortfall"]
    assert "fairness_marginal" in shortfall and shortfall["fairness_marginal"] > 0


def test_overlap_assignment_is_a_subset_of_the_primary_sheet():
    d = StudyDesign(domain="finance", n_items=100, n_overlap=40)
    items = select(_candidates(), d)
    sheets = assign(items, d)
    ids_a = {x["probe_id"] for x in sheets[PRIMARY]}
    ids_b = {x["probe_id"] for x in sheets[SECOND]}
    assert len(sheets[PRIMARY]) == 100 and len(sheets[SECOND]) == 40
    assert ids_b < ids_a


def test_export_is_blinded_and_ordered_differently_per_rater(tmp_path):
    d = StudyDesign(domain="finance", n_items=60, n_overlap=30)
    items = select(_candidates(), d)
    res = export(items, d, str(tmp_path), LABELS)

    rows = {}
    for rater in (PRIMARY, SECOND):
        with open(res["sheets"][rater], encoding="utf-8") as fh:
            rows[rater] = list(csv.DictReader(fh))
        blob = open(res["sheets"][rater], encoding="utf-8").read()
        assert "p0000" not in blob, "a probe id leaked onto a rater's sheet"
        assert "verdict" not in blob.lower() and "confidence" not in blob.lower()
        assert all(r["rating"] == "" for r in rows[rater]), "sheet shipped pre-filled"
        assert all(r["item"].startswith("IT-") for r in rows[rater])

    shared = [r["item"] for r in rows[SECOND]]
    order_a = [r["item"] for r in rows[PRIMARY] if r["item"] in set(shared)]
    assert order_a != shared, "both raters received the same ordering"


def test_key_file_holds_the_mapping_and_the_guidelines_hash(tmp_path):
    import json
    d = StudyDesign(domain="finance", n_items=40, n_overlap=20,
                    guidelines_sha256="abc123")
    items = select(_candidates(), d)
    res = export(items, d, str(tmp_path), LABELS)
    key = json.loads(open(res["key"], encoding="utf-8").read())
    assert key["design"]["guidelines_sha256"] == "abc123"
    assert len(key["items"]) == 40
    assert len(key["overlap_ids"]) == 20
    tok = token_for(items[0]["probe_id"], d.seed)
    assert key["items"][tok]["probe_id"] == items[0]["probe_id"]


def test_unrated_and_invalid_rows_are_counted_not_guessed(tmp_path):
    path = tmp_path / "s.csv"
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["item", "dimension", "criterion", "prompt", "response", "rating", "notes"])
        w.writerow(["IT-1", "transparency", "c", "p", "r", "adequate", ""])
        w.writerow(["IT-2", "transparency", "c", "p", "r", "", ""])
        w.writerow(["IT-3", "transparency", "c", "p", "r", "maybe", ""])
    got = load_sheet(str(path), LABELS)
    assert got["ratings"] == {"IT-1": "adequate"}
    assert got["blank"] == 1
    assert got["invalid"] == [("IT-3", "maybe")]


# --- the report -------------------------------------------------------------
def _key(tokens, dim="transparency"):
    return {"items": {t: {"probe_id": f"p{i}", "dimension": dim, "stratum": "random"}
                      for i, t in enumerate(tokens)},
            "allowed_labels": LABELS}


def test_report_leads_with_the_ceiling_and_judges_against_it():
    toks = [f"IT-{i:03d}" for i in range(80)]
    a = {t: ("adequate" if i % 3 else "inadequate") for i, t in enumerate(toks)}
    b = {t: ("adequate" if i % 3 or i % 7 == 0 else "inadequate")
         for i, t in enumerate(toks)}
    judge = {t: a[t] for t in toks}

    rep = score(a, b, _key(toks), judge=judge)
    assert rep["ceiling"]["kappa"] is not None
    assert rep["judge"]["share_of_ceiling"] is not None
    assert rep["judge"]["kappa"] >= rep["ceiling"]["kappa"], (
        "a judge matching rater A exactly should not score below the ceiling")


def test_report_warns_when_the_ceiling_itself_is_not_established():
    toks = [f"IT-{i:03d}" for i in range(60)]
    a = {t: ("adequate" if i % 2 else "inadequate") for i, t in enumerate(toks)}
    b = {t: ("adequate" if i % 3 else "inadequate") for i, t in enumerate(toks)}
    rep = score(a, b, _key(toks))
    assert not rep["ceiling"]["meets_threshold"]
    assert any("ceiling" in n for n in rep["notes"])


def test_thin_dimensions_are_flagged_rather_than_quietly_reported():
    toks = [f"IT-{i:03d}" for i in range(20)]
    a = {t: "adequate" if i % 2 else "inadequate" for i, t in enumerate(toks)}
    b = dict(a)
    rep = score(a, b, _key(toks))
    assert rep["by_dimension"]["transparency"]["warning"]


def test_only_double_annotated_items_enter_the_ceiling():
    toks = [f"IT-{i:03d}" for i in range(50)]
    a = {t: "adequate" if i % 2 else "inadequate" for i, t in enumerate(toks)}
    b = {t: a[t] for t in toks[:20]}
    rep = score(a, b, _key(toks))
    assert rep["n_double_annotated"] == 20
    assert rep["n_primary_only"] == 30


# --- the kappa paradox ------------------------------------------------------
def _raters(a, b, c, d):
    """(both yes, r1 only, r2 only, both no) -> two label vectors."""
    return (["ok"] * a + ["ok"] * b + ["no"] * c + ["no"] * d,
            ["ok"] * a + ["no"] * b + ["ok"] * c + ["no"] * d)


def test_kappa_collapses_where_ac1_does_not():
    """Skewed marginals deflate kappa toward zero at unchanged raw agreement.

    Transparency adequacy is expected to be high, so this is the normal case for
    this study rather than an edge case: two raters agreeing on nine items in ten
    would be scored 'fair' and fail a kappa >= 0.61 criterion, for a property of
    the label distribution rather than of the raters.
    """
    from grail.annotate.agreement import agreement
    skewed = agreement(*_raters(105, 6, 6, 3), iterations=300)
    assert skewed.percent_agreement == pytest.approx(0.90)
    assert skewed.kappa < 0.35
    assert skewed.ac1 > 0.85
    assert "KAPPA PARADOX" in skewed.paradox
    assert not skewed.meets(0.61) and skewed.meets_ac1(0.61)


def test_the_two_statistics_agree_when_marginals_are_balanced():
    """AC1 is not simply a looser kappa — it coincides where kappa is trustworthy."""
    from grail.annotate.agreement import agreement
    balanced = agreement(*_raters(48, 12, 12, 48), iterations=300)
    assert abs(balanced.kappa - balanced.ac1) < 0.02
    assert balanced.paradox == ""


def test_ac1_is_undefined_when_only_one_label_is_used():
    from grail.annotate.agreement import gwet_ac1
    ac1, po, _, reason = gwet_ac1(["ok"] * 20, ["ok"] * 20)
    assert ac1 is None and po == 1.0 and "only one label" in reason
