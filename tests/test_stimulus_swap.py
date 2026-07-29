"""Swapping the sub-domain must be a data change, not a code change.

The claim this file exists to test is that the audit machinery is sub-domain
independent: point the pipeline at the insurance pack and every invariant the
credit pack satisfies still holds, with no branch anywhere on which sub-domain is
running. The failure mode being guarded against is silent — a hard-coded credit
template would emit insurance-labelled loan applications without raising
anything, producing a clean-looking probe set for the wrong experiment.

So the tests come in pairs: the same property, asserted for both packs, plus a
cross-contamination check that insurance probes contain no credit vocabulary at
all.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from config import STIMULUS_DIR, STIMULUS_PACK, STRATUM_PLAN
from grail.ground.checklist import Checklist, ChecklistItem
from grail.ground.notary import save_signed, sign
from grail.probe.generate import generate_probeset
from grail.probe.schema import digits, leakage_terms
from grail.probe.templates import load_pack, render, sample_case

PACKS = sorted(STIMULUS_PACK.values())
SMALL = {"fairness": 40, "robustness": 6, "consistency": 5, "transparency": 4,
         "truthfulness": 300}

# Terms that belong to one sub-domain and must never appear in the other.
CREDIT_ONLY = ["lending", "loan", "instalment", "creditworthiness", "borrower",
               "APPROVE", "DECLINE", "debt"]
INSURANCE_ONLY = ["premium", "insurer", "excess", "cover", "mileage", "claims"]


def _signed(tmp_path, domain, dimension="fairness", partition="hybrid"):
    c = Checklist(domain, "Regulation (EU) 2024/1689 (EU AI Act)",
                  "2026-01-01T00:00:00+00:00")
    c.items = [ChecklistItem("AIA:Art10(2)(f)", "Article 10(2)(f)", partition,
                             dimension, "clause text", "requirement", "")]
    p = tmp_path / f"{domain}_signed.json"
    save_signed(sign(c, "Tester"), str(p))
    return str(p)


# --- the packs themselves ---------------------------------------------------
@pytest.mark.parametrize("name", PACKS)
def test_pack_loads_and_declares_what_it_must(name):
    pack = load_pack(name, STIMULUS_DIR)
    assert pack["name"] == name
    assert pack["outcome"]["type"] in ("binary", "continuous")
    assert pack["fields"] and pack["strata"] and pack["render"]["en"]


def test_missing_pack_fails_loudly_rather_than_falling_back():
    with pytest.raises(SystemExit, match="No stimulus pack"):
        load_pack("no_such_subdomain", STIMULUS_DIR)


@pytest.mark.parametrize("name", PACKS)
def test_pack_renders_without_legal_vocabulary(name):
    pack = load_pack(name, STIMULUS_DIR)
    for stratum in pack["strata"]:
        slots = sample_case(pack, 1, "d", 0, stratum)
        for lang in pack["render"]:
            prompt = render(pack, slots, lang=lang)
            assert leakage_terms(prompt) == [], f"{name}/{lang}: {leakage_terms(prompt)}"


@pytest.mark.parametrize("name", PACKS)
def test_numbers_render_without_thousands_separators(name):
    """The digit-multiset invariant depends on this; a comma would break it."""
    pack = load_pack(name, STIMULUS_DIR)
    slots = sample_case(pack, 1, "d", 0, sorted(pack["strata"])[0])
    prompt = render(pack, slots)
    assert "," not in prompt.replace(", ", ""), "a thousands separator crept in"


@pytest.mark.parametrize("name", PACKS)
def test_sampling_is_deterministic_and_arm_independent(name):
    pack = load_pack(name, STIMULUS_DIR)
    stratum = sorted(pack["strata"])[0]
    a = sample_case(pack, 7, "d", 3, stratum)
    b = sample_case(pack, 7, "d", 3, stratum)
    assert a == b
    assert sample_case(pack, 8, "d", 3, stratum) != a


@pytest.mark.parametrize("name", PACKS)
def test_every_declared_field_reaches_the_prompt(name):
    """A field sampled but never rendered is dead weight and probably a typo."""
    pack = load_pack(name, STIMULUS_DIR)
    template = pack["render"]["en"]["fields"]
    for field in pack["fields"]:
        composed = any(f"{{{field['name']}}}" in t for t in pack["compose"].values())
        assert f"{{{field['name']}}}" in template or composed, (
            f"{name}: field '{field['name']}' is sampled but never rendered")


# --- the swap ---------------------------------------------------------------
def test_insurance_probes_contain_no_credit_vocabulary(tmp_path):
    ps, _ = generate_probeset(_signed(tmp_path, "insurance"), core_n=SMALL)
    assert ps.probes
    blob = "\n".join(p.prompt for p in ps.probes)
    for term in CREDIT_ONLY:
        assert term not in blob, f"credit term '{term}' leaked into insurance probes"
    assert any(t in blob for t in INSURANCE_ONLY), "these do not look like insurance probes"


def test_credit_probes_contain_no_insurance_vocabulary(tmp_path):
    ps, _ = generate_probeset(_signed(tmp_path, "finance"), core_n=SMALL)
    blob = "\n".join(p.prompt for p in ps.probes)
    for term in ("premium", "insurer", "mileage"):
        assert term not in blob, f"insurance term '{term}' leaked into credit probes"


@pytest.mark.parametrize("domain", sorted(STRATUM_PLAN))
def test_counterbalancing_holds_for_every_sub_domain(tmp_path, domain):
    """The invariant that makes fairness measurable must not be credit-specific."""
    ps, _ = generate_probeset(_signed(tmp_path, domain), core_n=SMALL)
    pairs = {}
    for p in ps.probes:
        if p.dimension == "fairness":
            pairs.setdefault(p.pair_id, []).append(p)
    assert len(pairs) == SMALL["fairness"]
    for pair_id, (a, b) in pairs.items():
        differing = {k for k in set(a.slots) | set(b.slots)
                     if a.slots.get(k) != b.slots.get(k)}
        assert differing == {"title"}, f"{pair_id} differs in {sorted(differing)}"
        assert set(a.prompt.split()) ^ set(b.prompt.split()) == {"Ms.", "Mr."}


@pytest.mark.parametrize("domain", sorted(STRATUM_PLAN))
def test_perturbations_preserve_numbers_for_every_sub_domain(tmp_path, domain):
    from grail.probe.templates import PERTURBATIONS
    ps, _ = generate_probeset(_signed(tmp_path, domain, dimension="robustness"),
                              core_n=SMALL)
    by_pair = {}
    for p in ps.probes:
        by_pair.setdefault(p.pair_id, {})[p.variant] = p
    assert by_pair
    for pair_id, members in by_pair.items():
        assert len(members) == len(PERTURBATIONS) + 1
        base = members["base"]
        for variant, p in members.items():
            assert digits(p.prompt) == digits(base.prompt), f"{pair_id}:{variant}"


@pytest.mark.parametrize("domain", sorted(STRATUM_PLAN))
def test_stratum_plan_and_pack_agree(tmp_path, domain):
    ps, notes = generate_probeset(_signed(tmp_path, domain), core_n=SMALL)
    got = {p.stratum for p in ps.probes}
    assert got == set(STRATUM_PLAN[domain])
    assert any("stimulus pack" in n for n in notes)


def test_a_plan_naming_an_unknown_stratum_is_refused(tmp_path):
    with pytest.raises(SystemExit, match="must agree on the strata"):
        generate_probeset(_signed(tmp_path, "finance"), core_n=SMALL,
                          strata={"nonexistent": 1.0})


def test_a_domain_with_no_pack_is_refused(tmp_path):
    with pytest.raises(SystemExit, match="No stimulus pack configured"):
        generate_probeset(_signed(tmp_path, "healthcare"), core_n=SMALL)


# --- the outcome type is what stops the binary assumption spreading ---------
def test_outcome_type_travels_onto_every_probe(tmp_path):
    """The jury needs a different route for a price than for a yes/no."""
    credit, _ = generate_probeset(_signed(tmp_path, "finance"), core_n=SMALL)
    insurance, _ = generate_probeset(_signed(tmp_path, "insurance"), core_n=SMALL)
    assert {p.outcome_type for p in credit.probes} == {"binary"}
    assert {p.outcome_type for p in insurance.probes} == {"continuous"}


def test_insurance_asks_for_a_number_and_credit_asks_for_a_word(tmp_path):
    credit, _ = generate_probeset(_signed(tmp_path, "finance"), core_n=SMALL)
    insurance, _ = generate_probeset(_signed(tmp_path, "insurance"), core_n=SMALL)
    assert "APPROVE or DECLINE" in credit.probes[0].prompt
    assert "single number" in insurance.probes[0].prompt
    assert "APPROVE" not in insurance.probes[0].prompt


# --- a pack passed directly, without touching config ------------------------
def test_a_pack_can_be_supplied_inline(tmp_path):
    """Swapping does not require editing config — useful for a one-off run."""
    pack = load_pack("insurance", STIMULUS_DIR)
    ps, notes = generate_probeset(_signed(tmp_path, "finance"), core_n=SMALL,
                                  pack=pack, strata=STRATUM_PLAN["insurance"])
    assert {p.outcome_type for p in ps.probes} == {"continuous"}
    assert "premium" in ps.probes[0].prompt
