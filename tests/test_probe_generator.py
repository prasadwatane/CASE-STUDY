"""Tests for the auto-probe stage.

The important one is the injected-bias synthetic. A fairness probe set is only
worth running if a measured group gap can be attributed to the system under
audit rather than to the probes themselves, so two things have to hold and both
are tested here:

* score the probe set with a scorer that is *blind* to the protected arm and the
  gap must be exactly zero — anything else means a profile slot is tracking the
  arm (the slot-to-group mapping bug), and
* score it with a scorer carrying a known injected bias and the gap must show up
  at roughly the injected magnitude — a probe set that cannot detect a bias put
  there on purpose cannot detect a real one either.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from grail.ground.checklist import Checklist, ChecklistItem
from grail.ground.notary import save_signed, sign
from grail.probe import sizing
from grail.probe.generate import generate_probeset
from grail.probe.schema import (Probe, ProbeSet, assert_no_leakage, digits,
                                leakage_terms, save_probeset)
from grail.probe.templates import (PERTURBATIONS, load_pack, render,
                                   sample_case)
from grail.probe.schema import derive_rng

SMALL = {"fairness": 60, "robustness": 8, "consistency": 6, "transparency": 6,
         "truthfulness": 300}


def _pack(name="credit"):
    from config import STIMULUS_DIR
    return load_pack(name, STIMULUS_DIR)


# --- fixtures ---------------------------------------------------------------
def _signed_checklist(tmp_path, dimension="fairness", partition="hybrid",
                      name="finance_signed.json"):
    c = Checklist("finance", "Regulation (EU) 2024/1689 (EU AI Act)",
                  "2026-01-01T00:00:00+00:00")
    c.items = [ChecklistItem(
        clause_id="AIA:Art10(2)(f)", citation="Article 10(2)(f)",
        scope_partition=partition, dimension=dimension,
        clause_text="examine datasets in view of possible ...",
        requirement="The system under audit shall ...", criterion="")]
    p = tmp_path / name
    save_signed(sign(c, "Tester"), str(p))
    return str(p)


def _fairness_probes(tmp_path, **kw):
    ps, notes = generate_probeset(_signed_checklist(tmp_path), core_n=SMALL, **kw)
    return ps, notes


# --- the notary gate comes first -------------------------------------------
def test_unsigned_checklist_blocks_generation(tmp_path):
    import json
    c = Checklist("finance", "EU AI Act", "2026-01-01T00:00:00+00:00")
    p = tmp_path / "finance_signed.json"
    p.write_text(json.dumps({"checklist": c.as_dict(), "signature": None}))
    with pytest.raises(SystemExit):
        generate_probeset(str(p), core_n=SMALL)


def test_tampered_checklist_blocks_generation(tmp_path):
    import json
    path = _signed_checklist(tmp_path)
    d = json.loads(open(path).read())
    d["checklist"]["items"][0]["requirement"] = "TAMPERED"
    open(path, "w").write(json.dumps(d))
    with pytest.raises(SystemExit):
        generate_probeset(path, core_n=SMALL)


def test_missing_checklist_blocks_generation(tmp_path):
    with pytest.raises(SystemExit):
        generate_probeset(str(tmp_path / "nope.json"), core_n=SMALL)


# --- counterbalancing -------------------------------------------------------
def test_pairs_differ_only_in_the_axis_slot(tmp_path):
    ps, _ = _fairness_probes(tmp_path)
    pairs = {}
    for p in ps.probes:
        if p.dimension == "fairness":
            pairs.setdefault(p.pair_id, []).append(p)
    assert pairs, "no fairness probes generated"

    for pair_id, members in pairs.items():
        assert len(members) == 2, f"{pair_id} is not a two-arm pair"
        a, b = members
        differing = {k for k in set(a.slots) | set(b.slots)
                     if a.slots.get(k) != b.slots.get(k)}
        assert differing == {"title"}, f"{pair_id} differs in {sorted(differing)}"
        # and the rendered prompts differ in exactly the one token
        assert set(a.prompt.split()) ^ set(b.prompt.split()) == {"Ms.", "Mr."}


def test_confounded_axis_is_rejected(tmp_path):
    """A slot that tracks the arm must abort generation, not produce probes."""
    bad = [{"name": "gender", "slot": "title",
            "arms": [{"value": "female", "slots": {"title": "Ms.", "income": 30000}},
                     {"value": "male", "slots": {"title": "Mr.", "income": 60000}}]}]
    with pytest.raises(ValueError, match="counterbalancing broken"):
        generate_probeset(_signed_checklist(tmp_path), core_n=SMALL, axes=bad)


def test_strata_are_balanced_across_arms(tmp_path):
    ps, _ = _fairness_probes(tmp_path)
    by_arm = {}
    for p in ps.probes:
        if p.dimension == "fairness":
            by_arm.setdefault(p.arm, {}).setdefault(p.stratum, 0)
            by_arm[p.arm][p.stratum] += 1
    arms = list(by_arm.values())
    assert len(arms) == 2 and arms[0] == arms[1], "strata not identical across arms"


# --- the injected-bias synthetic (the point of all of the above) ------------
def _blind_scorer(probe: Probe) -> str:
    """Decides on financial slots only. Cannot see the protected arm."""
    s = probe.slots
    dti = (s["monthly_debt"] * 12) / s["income"]
    score = 2 if s["missed_payments"] == 0 else -2 * s["missed_payments"]
    score += 1 if dti < 0.15 else -1
    score += 1 if s["employment_years"] >= 3 else 0
    return "APPROVE" if score >= 2 else "DECLINE"


def _biased_scorer(probe: Probe) -> str:
    """The blind scorer, plus a bias injected against one arm in the marginal band."""
    decision = _blind_scorer(probe)
    if probe.arm == "female" and probe.stratum == "marginal":
        return "DECLINE"
    return decision


def _approval_gap(probes, scorer):
    rates = {}
    for arm in {p.arm for p in probes}:
        arm_probes = [p for p in probes if p.arm == arm]
        approvals = sum(scorer(p) == "APPROVE" for p in arm_probes)
        rates[arm] = approvals / len(arm_probes)
    return rates, abs(rates["male"] - rates["female"])


def test_blind_scorer_yields_exactly_zero_gap(tmp_path):
    ps, _ = _fairness_probes(tmp_path)
    fair = [p for p in ps.probes if p.dimension == "fairness"]
    rates, gap = _approval_gap(fair, _blind_scorer)
    assert gap == 0.0, (
        f"a scorer blind to the arm still shows a {gap:.3f} gap ({rates}) — the "
        "probe set itself is confounded")
    assert 0.0 < rates["male"] < 1.0, "degenerate probe set: no variation to measure"


def test_injected_bias_is_detected(tmp_path):
    ps, _ = _fairness_probes(tmp_path)
    fair = [p for p in ps.probes if p.dimension == "fairness"]
    rates, gap = _approval_gap(fair, _biased_scorer)
    assert rates["male"] > rates["female"]
    assert gap > 0.10, f"injected bias not visible in the probe set (gap {gap:.3f})"


def test_injected_bias_localises_to_the_marginal_stratum(tmp_path):
    ps, _ = _fairness_probes(tmp_path)
    fair = [p for p in ps.probes if p.dimension == "fairness"]
    marginal = [p for p in fair if p.stratum == "marginal"]
    strong = [p for p in fair if p.stratum == "strong"]
    _, gap_marginal = _approval_gap(marginal, _biased_scorer)
    _, gap_strong = _approval_gap(strong, _biased_scorer)
    assert gap_marginal > gap_strong == 0.0


# --- determinism and immutability ------------------------------------------
def test_same_seed_reproduces_the_same_probe_set(tmp_path):
    path = _signed_checklist(tmp_path)
    a, _ = generate_probeset(path, seed=7, core_n=SMALL)
    b, _ = generate_probeset(path, seed=7, core_n=SMALL)
    assert a.content_hash() == b.content_hash()
    assert [p.id for p in a.probes] == [p.id for p in b.probes]
    assert [p.prompt for p in a.probes] == [p.prompt for p in b.probes]


def test_different_seed_changes_the_probe_set(tmp_path):
    path = _signed_checklist(tmp_path)
    a, _ = generate_probeset(path, seed=7, core_n=SMALL)
    b, _ = generate_probeset(path, seed=8, core_n=SMALL)
    assert a.content_hash() != b.content_hash()


def test_derive_rng_is_stable_across_processes():
    # blake2b-derived, so no dependence on PYTHONHASHSEED
    assert (derive_rng(1, "a", 2).random()
            == derive_rng(1, "a", 2).random())
    assert derive_rng(1, "a", 2).random() != derive_rng(1, "a", 3).random()


def test_probe_set_is_frozen_against_silent_overwrite(tmp_path):
    path = _signed_checklist(tmp_path)
    out = str(tmp_path / "probes")
    a, _ = generate_probeset(path, seed=7, core_n=SMALL)
    save_probeset(a, out)
    save_probeset(a, out)                       # identical -> allowed
    b, _ = generate_probeset(path, seed=8, core_n=SMALL)
    with pytest.raises(SystemExit, match="FROZEN"):
        save_probeset(b, out)
    save_probeset(b, out, force=True)           # explicit re-freeze -> allowed


def test_manifest_carries_the_checklist_signature(tmp_path):
    import json
    path = _signed_checklist(tmp_path)
    signed = json.loads(open(path).read())
    ps, notes = generate_probeset(path, core_n=SMALL)
    m = ps.manifest(targets=SMALL, notes=notes)
    assert m["checklist_sha256"] == signed["signature"]["content_sha256"]
    assert m["checklist_signer"] == "Tester"
    assert m["generator_version"] == ps.generator_version


# --- the system under audit never sees the law -----------------------------
def test_no_probe_leaks_legal_or_audit_vocabulary(tmp_path):
    ps, _ = generate_probeset(_signed_checklist(tmp_path), core_n=SMALL)
    for p in ps.probes:
        assert leakage_terms(p.prompt) == [], f"{p.id} leaks: {leakage_terms(p.prompt)}"


def test_leakage_guard_actually_fires():
    with pytest.raises(ValueError, match="leakage"):
        assert_no_leakage("Assess this against Article 10(2)(f).")
    with pytest.raises(ValueError, match="leakage"):
        Probe(id="x", domain="finance", dimension="fairness", family="f",
              clause_ids=[], citations=[], prompt="Check the model for bias.")


# --- scope discipline -------------------------------------------------------
def test_procedural_clause_yields_no_probes(tmp_path):
    path = _signed_checklist(tmp_path, partition="procedural",
                             name="procedural_signed.json")
    ps, notes = generate_probeset(path, core_n=SMALL)
    assert ps.probes == []
    assert any("out of probe scope" in n for n in notes)


def test_unregistered_dimension_is_reported_as_a_gap(tmp_path):
    path = _signed_checklist(tmp_path, dimension="unassigned",
                             name="unassigned_signed.json")
    ps, notes = generate_probeset(path, core_n=SMALL)
    assert ps.probes == []
    assert any("coverage gap" in n for n in notes)


# --- other dimensions -------------------------------------------------------
def test_robustness_perturbations_preserve_the_numbers(tmp_path):
    path = _signed_checklist(tmp_path, dimension="robustness",
                             name="rob_signed.json")
    ps, _ = generate_probeset(path, core_n=SMALL)
    by_pair = {}
    for p in ps.probes:
        if p.dimension != "robustness":
            continue          # controls share the probe set but not this structure
        by_pair.setdefault(p.pair_id, {})[p.variant] = p
    assert by_pair
    for pair_id, members in by_pair.items():
        # every perturbation must survive: a dropped no-op would enter the paired
        # test as a duplicate of its base and pull the measured drop toward zero
        assert len(members) == len(PERTURBATIONS) + 1, (
            f"{pair_id} has {len(members)} members, expected {len(PERTURBATIONS) + 1}")
        base = members["base"]
        for variant, p in members.items():
            assert digits(p.prompt) == digits(base.prompt), (
                f"{pair_id}:{variant} changed a number")
            if variant != "base":
                assert p.prompt != base.prompt, f"{pair_id}:{variant} is a no-op"
                assert p.base_id == base.id


def test_each_perturbation_function_is_digit_preserving():
    slots = sample_case(_pack(), 1, "finance", 0, "marginal")
    prompt = render(_pack(), slots)
    for name, fn in PERTURBATIONS:
        out = fn(prompt, derive_rng(1, name))
        assert digits(out) == digits(prompt), f"{name} altered the numbers"
        assert out != prompt, f"{name} did nothing"


def test_consistency_sets_share_one_case(tmp_path):
    path = _signed_checklist(tmp_path, dimension="consistency",
                             name="cons_signed.json")
    ps, _ = generate_probeset(path, core_n=SMALL)
    sets = {}
    for p in ps.probes:
        if p.dimension == "consistency":
            sets.setdefault(p.pair_id, []).append(p)
    assert sets
    for pair_id, members in sets.items():
        assert len(members) >= 3
        base_digits = digits(members[0].prompt)
        for p in members:
            assert digits(p.prompt) == base_digits, f"{pair_id} member drifted"
        assert any(p.variant.startswith("de:") for p in members), "no DE member"


def test_truthfulness_records_gold_routes_but_never_a_gold(tmp_path):
    from config import PROBE_SEED_DIR
    path = _signed_checklist(tmp_path, dimension="truthfulness",
                             name="truth_signed.json")
    ps, notes = generate_probeset(path, core_n=SMALL, seed_dir=PROBE_SEED_DIR)
    assert ps.probes, "seed bank did not load"
    for p in ps.probes:
        assert p.reference is None, "a gold was invented at generation time"
        assert p.reference_status == "pending"
        assert p.gold_route in {"computed", "sourced", "structural", "none"}
    # sycophancy framing only where a lure exists
    for p in ps.probes:
        if p.variant == "sycophancy":
            assert p.slots["lure"], f"{p.id} applies pressure toward nothing"
    assert any("UNDERPOWERED" in n for n in notes), (
        "a 20-item seed bank should be reported as underpowered against a 300 target")


# --- sizing -----------------------------------------------------------------
def test_inverse_normal_cdf_is_accurate():
    assert sizing.z_two_sided(0.05) == pytest.approx(1.959963985, abs=1e-6)
    assert sizing.z_power(0.80) == pytest.approx(0.841621234, abs=1e-6)
    assert sizing.z_power(0.5) == pytest.approx(0.0, abs=1e-9)


def test_sizing_a_difference_costs_about_four_times_a_single_rate():
    """The bug this replaces: fairness sized on the single-rate formula."""
    single = sizing.n_for_proportion(0.10)
    difference = sizing.n_for_two_proportions(0.10, power=0.80)
    assert difference / single == pytest.approx(4.05, abs=0.1)
    assert difference == 393


def test_mde_and_n_are_inverses():
    for mde in (0.05, 0.10, 0.15):
        n = sizing.n_for_two_proportions(mde)
        assert sizing.mde_for_two_proportions(n) <= mde + 1e-3


def test_ci_halfwidth_is_smaller_than_the_powered_effect():
    """Quoting the CI half-width as 'detectable' overstates what a study can find."""
    assert sizing.ci_halfwidth_for_gap(393) < sizing.mde_for_two_proportions(393)


def test_mcnemar_sizing_scales_with_the_flip_rate():
    assert sizing.n_discordant_for_mcnemar(0.75) == 29
    assert sizing.n_pairs_for_mcnemar(0.75, 0.10) == 290
    assert sizing.n_pairs_for_mcnemar(0.75, 0.05) == 580
    with pytest.raises(ValueError):
        sizing.n_discordant_for_mcnemar(0.5)      # pure noise is not detectable


def test_config_core_n_is_derived_from_the_power_calculation():
    from config import (FAIRNESS_MDE, FAIRNESS_POWER, FAIRNESS_PRIMARY_STRATUM,
                        PROBE_CORE_N, STRATUM_PLAN)
    required = sizing.n_for_two_proportions(FAIRNESS_MDE, power=FAIRNESS_POWER)
    share = STRATUM_PLAN["finance"][FAIRNESS_PRIMARY_STRATUM["finance"]]
    assert PROBE_CORE_N["fairness"] * share >= required, (
        "the primary stratum does not reach the size its own power calc demands")


def test_every_domain_has_a_coherent_analysis_plan():
    """Shares sum to 1, the primary stratum is the largest, and the pack agrees."""
    from config import (FAIRNESS_PRIMARY_STRATUM, STIMULUS_DIR, STIMULUS_PACK,
                        STRATUM_PLAN)
    for domain, plan in STRATUM_PLAN.items():
        assert sum(plan.values()) == pytest.approx(1.0), domain
        primary = FAIRNESS_PRIMARY_STRATUM[domain]
        assert max(plan, key=plan.get) == primary, domain
        pack = load_pack(STIMULUS_PACK[domain], STIMULUS_DIR)
        assert set(plan) <= set(pack["strata"]), (
            f"{domain}: analysis plan names strata the pack does not define")


def test_manifest_counts_cases_not_prompts(tmp_path):
    """Power lives in independent cases; a pair rendered twice is still one case."""
    ps, notes = _fairness_probes(tmp_path)
    counts = ps.counts()["fairness"]
    assert counts["total"] == SMALL["fairness"] * 2      # two arms per case
    assert counts["cases"] == SMALL["fairness"]
    assert ps.manifest(targets={"fairness": SMALL["fairness"]})["underpowered"] == {}


def test_manifest_flags_underpowered_dimensions(tmp_path):
    ps, notes = _fairness_probes(tmp_path)
    m = ps.manifest(targets={"fairness": 10_000}, notes=notes)
    assert m["underpowered"]["fairness"]["target"] == 10_000
    assert m["underpowered"]["fairness"]["actual_cases"] == SMALL["fairness"]
