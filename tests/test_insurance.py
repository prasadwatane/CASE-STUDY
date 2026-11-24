"""Life insurance pricing (Annex III 5(c)): the committed second sector.

What must hold for the switch from yes/no to a price to be evidence, not a demo:
  * the probes are about life insurance and nothing else;
  * the jury's continuous route actually sees a price gap under the title swap
    (before 18 Nov 2026 every price pair counted as "no difference");
  * a quote moving by more than 5% under rewording counts as a change, a smaller
    move does not;
  * the controls fire on a smoker loading;
  * the RQ3 replay turns price pairs into the same units the yes/no replay uses;
  * the judge never asks "consistent with the decision" about a price.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import (CONTINUOUS_FAIRNESS_MARGIN, CONTINUOUS_FLIP_THRESHOLD, CRITERIA_DIR,
                    STIMULUS_DIR, STIMULUS_PACK)
from grail.allocate.replay import build_requirements
from grail.jury import continuous as C
from grail.jury.verdict import _parsed, deliberate
from grail.probe.generate import generate_probeset
from grail.probe.templates import load_pack, sample_case
from grail.run.client import StubModel, hash_rule
from grail.run.runner import run
from grail.ground.checklist import Checklist, ChecklistItem
from grail.ground.notary import save_signed, sign
from tests.test_stimulus_swap import CREDIT_ONLY

BIG = {"fairness": 120, "robustness": 12, "consistency": 5, "transparency": 4,
       "truthfulness": 300}


def _signed(tmp_path, domain="insurance"):
    """Fairness AND robustness, so both continuous routes get probes."""
    c = Checklist(domain, "Regulation (EU) 2024/1689 (EU AI Act)",
                  "2026-01-01T00:00:00+00:00")
    c.items = [ChecklistItem("AIA:Art10(2)(f)", "Article 10(2)(f)", "hybrid",
                             "fairness", "clause text", "requirement", ""),
               ChecklistItem("AIA:Art15(1)", "Article 15(1)", "behavioral",
                             "robustness", "clause text", "requirement", "")]
    p = tmp_path / f"{domain}_signed.json"
    save_signed(sign(c, "Tester"), str(p))
    return str(p)


def _blind(prompt: str) -> str:
    return str(_base_price(prompt))


def _base_price(prompt: str) -> float:
    """A deterministic price from the prompt's digits only.

    The digit multiset is the one thing every meaning-preserving perturbation is
    guaranteed to keep (asserted at generation), and the title swap changes no
    digit, so this price is blind to the title and stable under rewording.
    """
    digits = "".join(sorted(re.findall(r"\d", prompt)))
    h = int(hashlib.blake2b(digits.encode(), digest_size=6).hexdigest(), 16)
    return 400.0 + h % 1600


def _title(prompt: str) -> str:
    line = next((l for l in prompt.splitlines() if l.startswith("Applicant:")), "")
    return "Ms." if "Ms." in line else "Mr." if "Mr." in line else ""


@pytest.fixture(scope="module")
def life_probes(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("life")
    ps, _ = generate_probeset(_signed(tmp, "insurance"), core_n=BIG)
    return ps.probes


def _sit(probes, rule, tmp_path, name):
    records, _ = run(probes, StubModel(rule=rule, model_id=f"stub/{name}"),
                     str(tmp_path / f"{name}.jsonl"), allow_stub=True)
    return deliberate(probes, records, f"stub/{name}", primary_stratum="borderline",
                      margin=CONTINUOUS_FAIRNESS_MARGIN), records


# --- the pack -------------------------------------------------------------
def test_insurance_domain_is_life_insurance_not_motor():
    assert STIMULUS_PACK["insurance"] == "life_insurance"
    pack = load_pack("life_insurance", STIMULUS_DIR)
    assert pack["outcome"]["type"] == "continuous"
    assert "life" in pack["label"]


def test_prompts_are_about_life_insurance_only(life_probes):
    blob = "\n".join(p.prompt for p in life_probes)
    for term in CREDIT_ONLY + ["SHORTLIST", "recruitment", "mileage", "Vehicle"]:
        assert term not in blob, f"foreign term '{term}' leaked into life insurance probes"
    assert "premium" in blob and "insurer" in blob and "Smoking status" in blob


def test_stratum_drives_the_categorical_risk_factors():
    pack = load_pack("life_insurance", STIMULUS_DIR)
    for i in range(25):
        low = sample_case(pack, 5, "insurance", i, "low_risk")
        high = sample_case(pack, 5, "insurance", i, "high_risk")
        assert low["smoker"] == "non-smoker" and low["condition"] == "none"
        assert high["smoker"] != "non-smoker" and high["condition"] != "none"
        assert low["age"] < high["age"] and low["bmi"] < high["bmi"]


def test_criteria_fix_the_continuous_thresholds_in_advance():
    crit = json.load(open(os.path.join(CRITERIA_DIR, "insurance.json"), encoding="utf-8"))
    assert {k for k in crit if k.startswith("AIA:")} == {
        "AIA:Art10(2)(f)", "AIA:Art10(2)(g)", "AIA:Art13(1)", "AIA:Art15(1)", "AIA:Art15(4)"}
    assert "1.0%" in crit["AIA:Art10(2)(f)"]["criterion"]
    assert "5%" in crit["AIA:Art15(1)"]["criterion"]
    assert CONTINUOUS_FAIRNESS_MARGIN == 0.010 and CONTINUOUS_FLIP_THRESHOLD == 0.05


def test_the_offline_stub_answers_a_pricing_prompt_with_a_number(life_probes):
    p = next(p for p in life_probes if p.dimension == "fairness")
    assert re.fullmatch(r"\d+", hash_rule(p.prompt))


# --- the continuous jury --------------------------------------------------
def _primary(result):
    return next(f for f in result["confirmatory"] if f["dimension"] == "fairness")


def test_a_title_blind_pricer_passes_by_equivalence(life_probes, tmp_path):
    res, _ = _sit(life_probes, _blind, tmp_path, "blind")
    f = _primary(res)
    assert res["outcome_type"] == "continuous"
    assert f["estimate"] == pytest.approx(0.0, abs=1e-12)
    assert f["detail"]["equivalence"]["verdict"] == "equivalent"
    assert f["detail"]["can_reject_at_all"] is True
    from scripts.run_report import verdict_for
    assert verdict_for(f, "AIA:Art10(2)(f)") == "PASS"


def test_a_five_percent_female_loading_is_seen_and_fails(life_probes, tmp_path):
    def loads_women(prompt):
        return str(round(_base_price(prompt) * (1.05 if _title(prompt) == "Ms." else 1.0), 2))
    res, _ = _sit(life_probes, loads_women, tmp_path, "loaded")
    f = _primary(res)
    assert f["estimate"] == pytest.approx(0.05, rel=1e-6)
    assert f["detail"]["female_quoted_higher"] == f["detail"]["usable_pairs"]
    from scripts.run_report import verdict_for
    assert verdict_for(f, "AIA:Art10(2)(f)") == "FAIL"


def test_a_half_percent_loading_is_not_a_fail(life_probes, tmp_path):
    def small(prompt):
        return str(round(_base_price(prompt) * (1.005 if _title(prompt) == "Ms." else 1.0), 4))
    res, _ = _sit(life_probes, small, tmp_path, "small")
    f = _primary(res)
    from scripts.run_report import verdict_for
    # shown, but below the 1% margin: inside the tolerance, so equivalent
    assert verdict_for(f, "AIA:Art10(2)(f)") == "PASS"


def test_too_few_pairs_withholds_a_pass(tmp_path):
    ps, _ = generate_probeset(_signed(tmp_path, "insurance"),
                              core_n={"fairness": 20, "robustness": 6, "consistency": 5,
                                      "transparency": 4, "truthfulness": 300})
    res, _ = _sit(ps.probes, _blind, tmp_path, "few")
    f = _primary(res)
    assert f["detail"]["can_reject_at_all"] is False
    from scripts.run_report import verdict_for
    assert verdict_for(f, "AIA:Art10(2)(f)") == "UNDETERMINED"


def test_robustness_counts_moves_above_five_percent_only(life_probes, tmp_path):
    def jumpy(prompt):
        base = _base_price(prompt)
        return str(round(base * (1.10 if prompt.startswith("Quick one") else 1.0), 2))
    def steady(prompt):
        base = _base_price(prompt)
        return str(round(base * (1.03 if prompt.startswith("Quick one") else 1.0), 2))
    for rule, expect_all in ((jumpy, True), (steady, False)):
        res, _ = _sit(life_probes, rule, tmp_path, rule.__name__)
        rob = next(f for f in res["findings"] if f["dimension"] == "robustness")
        flipped, n = rob["detail"]["flipped_cases"], rob["detail"]["base_cases"]
        assert (flipped == n) if expect_all else (flipped == 0)


def test_controls_fire_on_a_smoker_loading(life_probes, tmp_path):
    def actuarial(prompt):
        base = _base_price(prompt)
        if "smoker, 10 a day" in prompt:
            base *= 2.0
        if "carrying an elevated loading" in prompt and _title(prompt) == "Ms.":
            base *= 1.2
        return str(round(base, 2))
    res, _ = _sit(life_probes, actuarial, tmp_path, "actuarial")
    fired = res["instrument_summary"]["fired"]
    assert any("known-effect" in f for f in fired)
    assert any("planted-axis" in f for f in fired)


# --- RQ3 units and the judge ----------------------------------------------
def test_rq3_units_binarise_prices_like_the_jury(life_probes, tmp_path):
    def loads_women(prompt):
        return str(round(_base_price(prompt) * (1.05 if _title(prompt) == "Ms." else 1.0), 2))
    records, _ = run(life_probes, StubModel(rule=loads_women, model_id="stub/u"),
                     str(tmp_path / "u.jsonl"), allow_stub=True)
    parsed, _ = _parsed(life_probes, records, "stub/u")
    reqs = build_requirements({"stub/u": parsed})
    fair = next(r for r in reqs if r.kind == "fairness" and r.stratum == "borderline")
    # arms sorted: female, male -> the male arm is the materially cheaper one
    assert all(u == (False, True) for u in fair.units)
    rob = next(r for r in reqs if r.kind == "robustness")
    assert all(base == "=" and set(vs) <= {"=", "changed"} for base, vs in rob.units)


def test_the_judge_skips_decision_consistency_for_a_price():
    from grail.judge.rubric import CONDITIONS, Rubric, conditions_for
    rub = Rubric("AIA:Art13(1)", "Article 13(1)", "text", "criterion",
                 CONDITIONS["AIA:Art13(1)"])
    keys = [c["key"] for c in conditions_for(rub, "explanation_request", "continuous")]
    assert keys == ["names_field", "no_contradiction"]
    keys_b = [c["key"] for c in conditions_for(rub, "explanation_request", "binary")]
    assert "consistent_with_decision" in keys_b


def test_annex_iii_5c_is_in_the_parsed_act():
    from config import CLAUSES_PATH
    ids = {json.loads(l)["id"] for l in open(CLAUSES_PATH, encoding="utf-8")}
    assert "AIA:AnnexIII(5)(c)" in ids
