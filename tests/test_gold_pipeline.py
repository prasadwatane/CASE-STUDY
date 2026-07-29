"""Tests for the gold pipeline.

The formula tests deliberately do not re-state the formula — asserting
`annuity_payment(...) == <the annuity formula>` would only prove the code equals
itself. Each is checked against an independent construction instead: the
instalment is verified by simulating the amortisation month by month and
requiring the balance to land on zero, compounding by repeated multiplication.

The conformal tests check the refusal as carefully as the acceptance. A gate that
certifies a bound it cannot support is worse than no gate, so the interesting
assertions are that a small calibration set certifies nothing and that the
minimum-n arithmetic is right.
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from grail.gold import formulas
from grail.gold.conformal import (binom_cdf, calibrate, clopper_pearson_upper,
                                  min_calibration_n, nonconformity)
from grail.gold.proposer import StubProposer
from grail.gold.router import build_golds
from grail.gold.schema import (AMBER, ESCALATED, GREEN, GoldRecord,
                               append_ledger, load_ledger, save_ledger,
                               seal_chain, verify_chain)
from grail.probe.generators.truthfulness import load_seed_bank


# --- formulas: checked against independent constructions --------------------
def test_annuity_payment_amortises_to_zero():
    principal, rate, n = 12000.0, 0.065, 48
    payment = formulas.annuity_payment(principal, rate, n)
    balance, i = principal, rate / 12.0
    for _ in range(n):
        balance = balance * (1.0 + i) - payment
    assert abs(balance) < 1e-6, f"loan does not amortise to zero, ends at {balance}"


def test_annuity_zero_rate_is_straight_line():
    assert formulas.annuity_payment(1200.0, 0.0, 12) == pytest.approx(100.0)


def test_annuity_rejects_impossible_terms():
    with pytest.raises(ValueError):
        formulas.annuity_payment(1000.0, 0.05, 0)


def test_compound_balance_equals_repeated_multiplication():
    balance = 2400.0
    for _ in range(3):
        balance *= 1.015
    assert formulas.compound_balance(2400.0, 0.015, 3) == pytest.approx(balance)


def test_compound_balance_beats_the_linear_lure():
    """The seed item's lure is the naive linear answer; they must differ."""
    compounded = formulas.compound_balance(2400.0, 0.015, 3)
    linear = 2400.0 * (1 + 0.015 * 3)
    assert compounded > linear
    assert round(compounded, 2) != round(linear, 2)


def test_simple_ratios():
    assert formulas.dti_percent(620, 42000) == pytest.approx(100 * 7440 / 42000)
    assert formulas.share_of_income_percent(495, 2200) == pytest.approx(22.5)
    assert formulas.total_interest(310, 60, 15000) == pytest.approx(3600.0)
    assert formulas.total_repaid_with_fee(8000, 240) == pytest.approx(8240.0)


def test_unknown_formula_is_refused():
    with pytest.raises(KeyError):
        formulas.evaluate({"formula": "no_such_formula", "args": {}})


def test_evaluate_records_recomputable_provenance():
    _, formatted, prov = formulas.evaluate(
        {"formula": "dti_percent", "args": {"monthly_debt": 620, "annual_income": 42000}})
    assert prov["recomputable"] is True
    assert prov["formula"] == "dti_percent"
    assert prov["args"] == {"monthly_debt": 620, "annual_income": 42000}
    assert "percent" in formatted


def test_every_computed_seed_item_resolves():
    """A compute spec that addresses a missing solver must fail loudly, here."""
    for item in load_seed_bank(_seed_dir()):
        if item.get("gold_route") == "computed":
            assert "compute" in item, f"{item['id']} is computed but has no spec"
            value, formatted, _ = formulas.evaluate(item["compute"])
            assert math.isfinite(value) and formatted


def _seed_dir():
    from config import PROBE_SEED_DIR
    return PROBE_SEED_DIR


# --- conformal gate ---------------------------------------------------------
def test_binom_cdf_is_a_distribution():
    assert binom_cdf(10, 10, 0.3) == 1.0
    assert binom_cdf(-1, 10, 0.3) == 0.0
    assert binom_cdf(3, 10, 0.3) < binom_cdf(4, 10, 0.3)


def test_clopper_pearson_matches_the_closed_form_at_zero_errors():
    # with k=0 the bound solves (1-p)^n = delta exactly
    for n in (5, 20, 100):
        expected = 1.0 - 0.05 ** (1.0 / n)
        assert clopper_pearson_upper(0, n, 0.05) == pytest.approx(expected, abs=1e-6)


def test_minimum_calibration_size_is_59_at_five_percent():
    assert min_calibration_n(0.05, 0.05) == 59
    assert min_calibration_n(0.10, 0.05) == 29
    n = min_calibration_n(0.05, 0.05)
    assert clopper_pearson_upper(0, n, 0.05) <= 0.05
    assert clopper_pearson_upper(0, n - 1, 0.05) > 0.05


def test_small_calibration_set_certifies_nothing():
    """Six clean points cannot support a 5% bound, and must not pretend to."""
    cal = calibrate([(0.0, True)] * 6, alpha=0.05, delta=0.05)
    assert not cal.certified
    assert cal.threshold is None
    assert "at least 59" in cal.reason


def test_large_clean_calibration_certifies():
    cal = calibrate([(0.0, True)] * 200, alpha=0.05, delta=0.05)
    assert cal.certified
    assert cal.error_bound is not None and cal.error_bound <= 0.05


def test_gate_excludes_the_band_where_the_proposer_is_wrong():
    """Confident proposals are right, split ones are coin flips: cut below the split."""
    obs = [(0.0, True)] * 150 + [(0.4, i % 2 == 0) for i in range(60)]
    cal = calibrate(obs, alpha=0.05, delta=0.05)
    assert cal.certified
    assert cal.threshold < 0.4, "gate accepted the band it gets half wrong"
    selected = [ok for score, ok in obs if score <= cal.threshold]
    empirical = 1 - sum(selected) / len(selected)
    assert empirical <= cal.error_bound


def test_no_calibration_data_is_handled():
    cal = calibrate([], alpha=0.05, delta=0.05)
    assert not cal.certified and "no calibration data" in cal.reason


def test_nonconformity_is_order_independent():
    a = nonconformity(["x", "x", "y", "x", "y"])
    b = nonconformity(["y", "x", "y", "x", "x"])
    assert a == b
    assert a[1] == "x" and a[2] == pytest.approx(0.6)
    assert nonconformity([]) == (1.0, "", 0.0)


# --- ledger -----------------------------------------------------------------
def _record(item_id="tc001", status=GREEN):
    return GoldRecord(item_id=item_id, domain="finance", dimension="truthfulness",
                      route="computed", status=status, answer="1.00 EUR",
                      answer_kind="value", provenance={"method": "test"})


def test_a_gold_without_provenance_cannot_be_written():
    with pytest.raises(ValueError, match="trust me"):
        GoldRecord(item_id="x", domain="finance", dimension="truthfulness",
                   route="sourced", status=GREEN, answer="42",
                   answer_kind="value", provenance={})


def test_ledger_chain_verifies_and_detects_tampering(tmp_path):
    recs = seal_chain([_record("tc001"), _record("tc002"), _record("tc003")])
    ok, reason = verify_chain(recs)
    assert ok, reason

    path = str(tmp_path / "golds.jsonl")
    save_ledger(recs, path)
    loaded = load_ledger(path)
    assert verify_chain(loaded)[0]

    loaded[1].answer = "999.00 EUR"          # edit a row after the fact
    ok, reason = verify_chain(loaded)
    assert not ok and "no longer matches its hash" in reason


def test_deleting_a_row_breaks_the_chain():
    recs = seal_chain([_record("tc001"), _record("tc002"), _record("tc003")])
    ok, reason = verify_chain([recs[0], recs[2]])
    assert not ok and "row 1" in reason


def test_append_continues_the_chain(tmp_path):
    path = str(tmp_path / "golds.jsonl")
    save_ledger(seal_chain([_record("tc001")]), path)
    combined = append_ledger(path, [_record("tc002", status=AMBER)])
    assert len(combined) == 2
    assert verify_chain(combined)[0]
    assert verify_chain(load_ledger(path))[0]


def test_truncating_the_ledger_is_detected_by_the_anchor(tmp_path):
    """A shortened chain still verifies on its own — the anchor is what catches it."""
    path = str(tmp_path / "golds.jsonl")
    save_ledger(seal_chain([_record("tc001"), _record("tc002")]), path)
    lines = open(path).read().strip().split("\n")
    open(path, "w").write(lines[0] + "\n")     # lop the last row off

    assert verify_chain(load_ledger(path))[0], (
        "a truncated chain verifies in isolation — that is why the anchor exists")
    with pytest.raises(SystemExit, match="Rows were removed"):
        append_ledger(path, [_record("tc003")])


def test_append_refuses_onto_an_edited_ledger(tmp_path):
    import json as _json
    path = str(tmp_path / "golds.jsonl")
    save_ledger(seal_chain([_record("tc001"), _record("tc002")]), path)
    lines = open(path).read().strip().split("\n")
    row = _json.loads(lines[1])
    row["answer"] = "999.00 EUR"
    open(path, "w").write(lines[0] + "\n" + _json.dumps(row) + "\n")
    with pytest.raises(SystemExit, match="refusing to append"):
        append_ledger(path, [_record("tc003")])


# --- router -----------------------------------------------------------------
def _bank():
    return load_seed_bank(_seed_dir())


def test_stub_proposer_is_refused_by_default():
    with pytest.raises(SystemExit, match="not evidence"):
        build_golds(_bank(), [], StubProposer(), domain="finance")


def test_computed_items_are_green_with_no_model_in_their_provenance():
    records, report = build_golds(_bank(), [], StubProposer(), domain="finance",
                                  allow_stub=True)
    green = [r for r in records if r.status == GREEN]
    assert len(green) == 6, "expected the six numeric-trap items to be Green"
    for r in green:
        assert r.route == "computed"
        assert r.provenance["recomputable"] is True
        assert "proposer" not in r.provenance, (
            f"{r.item_id} is Green but a model appears in its provenance")
        assert r.proposals == []


def test_green_answers_match_the_solvers():
    records, _ = build_golds(_bank(), [], StubProposer(), domain="finance",
                             allow_stub=True)
    by_id = {r.item_id: r for r in records}
    _, expected, _ = formulas.evaluate(
        {"formula": "total_interest",
         "args": {"instalment": 310, "n_months": 60, "principal": 15000}})
    assert by_id["tc010"].answer == expected


def test_small_seed_bank_escalates_everything_it_cannot_compute():
    """Six calibration points cannot certify 5%, so leakage is 100% of the rest."""
    records, report = build_golds(_bank(), [], StubProposer(), domain="finance",
                                  allow_stub=True)
    assert report["counts"][GREEN] == 6
    assert report["counts"][AMBER] == 0
    assert report["counts"][ESCALATED] == 14
    assert not report["calibration"]["certified"]
    assert report["calibration"]["min_n_required"] == 59
    for r in records:
        if r.status == ESCALATED:
            assert "not certified" in r.escalation_reason
            assert r.answer is None


def test_report_split_is_complete_and_flags_the_stub():
    records, report = build_golds(_bank(), [], StubProposer(), domain="finance",
                                  allow_stub=True)
    c = report["counts"]
    assert c[GREEN] + c[AMBER] + c[ESCALATED] == report["n_items"] == len(records)
    assert report["proposer_is_stub"] is True
    assert report["proposer"] == "stub/deterministic-1.0"
    assert report["human_leakage"] == pytest.approx(14 / 20)
    assert verify_chain(records)[0]


def test_gate_accepts_once_calibration_is_large_enough():
    """Grow the calibration set past the floor and Amber golds start to appear."""
    bank = _bank()
    synthetic = []
    for i in range(120):
        synthetic.append({
            "id": f"syn{i:03d}", "type": "numeric_trap", "gold_route": "computed",
            "question": "synthetic", "compute": {
                "formula": "total_interest",
                "args": {"instalment": 100 + i, "n_months": 12, "principal": 1000}}})
    records, report = build_golds(bank + synthetic, [], StubProposer(),
                                  domain="finance", allow_stub=True)
    assert report["calibration"]["certified"], report["calibration"]["reason"]
    assert report["counts"][AMBER] > 0
    assert report["human_leakage"] < 1.0
    for r in records:
        if r.status == AMBER:
            assert r.error_bound is not None and r.error_bound <= 0.05
            assert r.nonconformity <= r.threshold
            assert r.provenance["proposer"] == "stub/deterministic-1.0"


def test_structural_items_need_their_construction_confirmed():
    """A gold that an entity does not exist is a claim, and has to be checked."""
    bank = _bank()
    synthetic = [{"id": f"syn{i:03d}", "type": "numeric_trap", "gold_route": "computed",
                  "question": "synthetic",
                  "compute": {"formula": "total_interest",
                              "args": {"instalment": 100 + i, "n_months": 12,
                                       "principal": 1000}}} for i in range(120)]
    records, _ = build_golds(bank + synthetic, [], StubProposer(), domain="finance",
                             allow_stub=True)
    structural = [r for r in records if r.route == "structural"]
    assert structural
    for r in structural:
        if r.status == ESCALATED and "construction" in r.escalation_reason:
            assert "construction_fails" in r.proposals
        if r.status == AMBER:
            assert r.answer_kind == "behaviour"


def test_golds_key_every_framing_of_their_item():
    from grail.ground.checklist import Checklist, ChecklistItem
    from grail.ground.notary import save_signed, sign
    from grail.probe.generate import generate_probeset
    import tempfile

    tmp = tempfile.mkdtemp()
    c = Checklist("finance", "EU AI Act", "2026-01-01T00:00:00+00:00")
    c.items = [ChecklistItem("AIA:Art15(1)", "Article 15(1)", "behavioral",
                             "truthfulness", "text", "req", "")]
    path = os.path.join(tmp, "t_signed.json")
    save_signed(sign(c, "Tester"), path)
    ps, _ = generate_probeset(path, seed_dir=_seed_dir())

    records, _ = build_golds(_bank(), ps.probes, StubProposer(), domain="finance",
                             allow_stub=True)
    by_id = {r.item_id: r for r in records}
    # tc003 carries a lure, so it has all three framings
    assert len(by_id["tc003"].probe_ids) == 3
    assert all(pid.startswith("finance:truthfulness:tc003:")
               for pid in by_id["tc003"].probe_ids)
    # tc018 has no lure, so no sycophancy framing exists to key
    assert len(by_id["tc018"].probe_ids) == 2
