"""Tests for record-backed cases (German Credit).

Real records buy realism, and they bring three ways to be quietly wrong. Each has
a test here because none of them would raise an error on their own:

* **Leaking the protected attribute.** The dataset records sex in attribute 9. If
  it reaches the prompt, the system sees the recorded gender *and* the arm's
  title, so the counterbalanced pair no longer differs in one thing.
* **Leaking the outcome into the design.** Stratifying on the good/bad label, or
  on anything gender-correlated, rebuilds the confound the counterbalancing
  exists to remove.
* **Treating the label as a fairness gold.** It records observed repayment. Used
  as a fairness reference it would make historical lending decisions the standard
  under audit.

The fixture is SYNTHETIC data in the real wire format, so the suite runs offline
and CI never depends on a download.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from config import STIMULUS_DIR
from grail.probe import records as R
from grail.probe.schema import leakage_terms
from grail.probe.templates import load_pack, render, sample_case

FIXTURE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "fixtures", "german_credit_synthetic.data")


@pytest.fixture
def pack(tmp_path):
    p = dict(load_pack("credit_real", STIMULUS_DIR))
    p["source"] = dict(p["source"], path=FIXTURE)
    return p


# --- parsing ----------------------------------------------------------------
def test_records_parse_into_every_declared_column():
    recs = R.load_records(FIXTURE)
    assert len(recs) == 120
    for rec in recs[:5]:
        for col in R.COLUMNS:
            assert col in rec
        assert isinstance(rec["age"], int)
        assert rec["recorded_gender"] in ("male", "female")
        assert isinstance(rec["repaid"], bool)


def test_a_malformed_row_is_refused():
    with pytest.raises(ValueError, match="expected 21 fields"):
        R.parse_line("A11 6 A34", 0)


def test_a_missing_record_file_says_how_to_fetch_it():
    with pytest.raises(SystemExit, match="fetch_german_credit"):
        R.load_records("/nonexistent/german.data")


# --- the protected attribute must not reach the prompt ----------------------
def test_recorded_sex_is_redacted_from_the_prompt(pack):
    """Attribute 9 encodes sex. If it renders, the pair differs in two things."""
    for stratum in pack["strata"]:
        for i in range(12):
            slots = sample_case(pack, 1, "finance", i, stratum, ns="t")
            prompt = render(pack, slots)
            for phrase in ("male", "female", "divorced", "widowed", "single"):
                assert phrase not in prompt.lower(), (
                    f"'{phrase}' reached the prompt — the recorded sex is visible")
            assert "personal_status_sex" not in slots
            assert slots["_redacted_personal_status_sex"].startswith("A9")


def test_foreign_worker_is_redacted_by_default(pack):
    slots = sample_case(pack, 1, "finance", 0, "marginal", ns="t")
    assert "foreign_worker" not in slots
    assert slots["_redacted_foreign_worker"].startswith("A20")
    assert "foreign" not in render(pack, slots).lower()


def test_real_records_still_render_without_legal_vocabulary(pack):
    for stratum in pack["strata"]:
        for lang in pack["render"]:
            slots = sample_case(pack, 3, "finance", 1, stratum, ns="t")
            prompt = render(pack, slots, lang=lang)
            assert leakage_terms(prompt) == [], leakage_terms(prompt)


# --- stratification must not use the label or the protected fields ----------
def test_strength_score_ignores_the_label_and_the_protected_fields():
    """Same record, flipped label and flipped sex — the score must not move."""
    rec = dict(R.load_records(FIXTURE)[0])
    before = R.strength(rec)
    rec["label"] = 1 if rec["label"] == 2 else 2
    rec["personal_status_sex"] = "A95" if rec["personal_status_sex"] != "A95" else "A93"
    rec["foreign_worker"] = "A201" if rec["foreign_worker"] == "A202" else "A202"
    assert R.strength(rec) == before


def test_strata_are_terciles_of_the_strength_score():
    recs = R.load_records(FIXTURE)
    bands = R.stratify(recs, ("weak", "marginal", "strong"))
    assert sum(len(v) for v in bands.values()) == len(recs)
    assert max(R.strength(r) for r in bands["weak"]) <= min(
        R.strength(r) for r in bands["marginal"])
    assert max(R.strength(r) for r in bands["marginal"]) <= min(
        R.strength(r) for r in bands["strong"])


def test_strata_do_not_sort_the_genders_apart():
    """If a band were gender-skewed, the 'counterbalanced' pairs would be confounded."""
    recs = R.load_records(FIXTURE)
    bands = R.stratify(recs, ("weak", "marginal", "strong"))
    shares = {}
    for name, pool in bands.items():
        female = sum(1 for r in pool if r["recorded_gender"] == "female")
        shares[name] = female / len(pool)
    assert max(shares.values()) - min(shares.values()) < 0.35, shares


# --- the label is available, and only for the right thing -------------------
def test_the_repayment_label_travels_but_never_into_the_prompt(pack):
    slots = sample_case(pack, 1, "finance", 0, "marginal", ns="t")
    assert isinstance(slots["_repaid"], bool), "label unavailable for robustness"
    prompt = render(pack, slots)
    assert "repaid" not in prompt.lower() and "default" not in prompt.lower()


def test_every_case_carries_its_source_record(pack):
    slots = sample_case(pack, 1, "finance", 4, "strong", ns="t")
    assert slots["source_record"].startswith("german_credit:")


# --- determinism and arm independence ---------------------------------------
def test_record_selection_is_deterministic_and_arm_independent(pack):
    a = sample_case(pack, 7, "finance", 3, "marginal", ns="fairness/gender")
    b = sample_case(pack, 7, "finance", 3, "marginal", ns="fairness/gender")
    assert a == b
    assert sample_case(pack, 8, "finance", 3, "marginal", ns="fairness/gender") != a
    assert sample_case(pack, 7, "finance", 3, "marginal", ns="robustness") != a


# --- end to end through the unchanged generators ----------------------------
def test_counterbalancing_holds_on_real_records(tmp_path, pack):
    from grail.ground.checklist import Checklist, ChecklistItem
    from grail.ground.notary import save_signed, sign
    from grail.probe.generate import generate_probeset

    c = Checklist("finance", "EU AI Act", "2026-01-01T00:00:00+00:00")
    c.items = [ChecklistItem("AIA:Art10(2)(f)", "Article 10(2)(f)", "hybrid",
                             "fairness", "text", "req", "")]
    path = tmp_path / "real_signed.json"
    save_signed(sign(c, "Tester"), str(path))

    ps, notes = generate_probeset(
        str(path), core_n={"fairness": 30}, pack=pack,
        strata={"weak": 0.2, "marginal": 0.6, "strong": 0.2})

    pairs = {}
    for p in ps.probes:
        if p.dimension == "fairness":
            pairs.setdefault(p.pair_id, []).append(p)
    assert len(pairs) == 30
    for pair_id, (a, b) in pairs.items():
        differing = {k for k in set(a.slots) | set(b.slots)
                     if a.slots.get(k) != b.slots.get(k)}
        assert differing == {"title"}, f"{pair_id} differs in {sorted(differing)}"
        assert set(a.prompt.split()) ^ set(b.prompt.split()) == {"Ms.", "Mr."}
        assert a.slots["source_record"] == b.slots["source_record"]


def _real_fairness_probes(tmp_path, pack, n=90):
    from grail.ground.checklist import Checklist, ChecklistItem
    from grail.ground.notary import save_signed, sign
    from grail.probe.generate import generate_probeset

    c = Checklist("finance", "EU AI Act", "2026-01-01T00:00:00+00:00")
    c.items = [ChecklistItem("AIA:Art10(2)(f)", "Article 10(2)(f)", "hybrid",
                             "fairness", "text", "req", "")]
    path = tmp_path / "bias_signed.json"
    save_signed(sign(c, "Tester"), str(path))
    ps, _ = generate_probeset(str(path), core_n={"fairness": n}, pack=pack,
                              strata={"weak": 0.2, "marginal": 0.6, "strong": 0.2})
    return [p for p in ps.probes if p.dimension == "fairness"]


def _blind(probe):
    """Scores on the record's financial strength only. Cannot see the arm."""
    return "APPROVE" if probe.slots["_strength"] >= 7 else "DECLINE"


def _biased(probe):
    return ("DECLINE" if probe.arm == "female" and probe.stratum == "marginal"
            else _blind(probe))


def _gap(probes, scorer):
    rates = {}
    for arm in {p.arm for p in probes}:
        pool = [p for p in probes if p.arm == arm]
        rates[arm] = sum(scorer(p) == "APPROVE" for p in pool) / len(pool)
    return rates, abs(rates["male"] - rates["female"])


def test_real_records_introduce_no_confound_of_their_own(tmp_path, pack):
    """The property that matters most once profiles stop being synthetic.

    Real records have a joint distribution nobody designed, so this is where a
    hidden association between the arm and a financial field would show up. A
    scorer blind to the arm must still produce a gap of exactly zero.
    """
    probes = _real_fairness_probes(tmp_path, pack)
    rates, gap = _gap(probes, _blind)
    assert gap == 0.0, (
        f"a scorer blind to the arm shows a {gap:.3f} gap ({rates}) — the "
        "record-backed probe set is confounded")
    assert 0.0 < rates["male"] < 1.0, "degenerate probe set: nothing to measure"


def test_injected_bias_is_still_detected_on_real_records(tmp_path, pack):
    probes = _real_fairness_probes(tmp_path, pack)
    rates, gap = _gap(probes, _biased)
    assert rates["male"] > rates["female"]
    assert gap > 0.10, f"injected bias invisible on real records (gap {gap:.3f})"


def test_a_record_pack_must_declare_its_licence(tmp_path):
    import json
    from grail.probe.templates import load_pack as lp
    bad = json.loads(open(os.path.join(STIMULUS_DIR, "credit_real", "pack.json")).read())
    del bad["source"]["licence"]
    d = tmp_path / "nolicence"
    d.mkdir()
    (d / "pack.json").write_text(json.dumps(bad))
    with pytest.raises(SystemExit, match="licence and attribution"):
        lp("nolicence", str(tmp_path))
