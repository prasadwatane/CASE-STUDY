"""Employment (Annex III 4(a)) — the second sector, as data.

What must hold for the transfer to be evidence rather than a demo:
  * the probes are about hiring and nothing else (no credit / insurance leakage,
    in prompts or in metadata);
  * the jury reads the favourable outcome from the pack, so SHORTLIST counts as
    favourable and a stray credit token does not;
  * the criteria are the finance criteria, unchanged.
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

import config
from config import CRITERIA_DIR, STIMULUS_DIR
from grail.jury.verdict import _favourable
from grail.probe import outcome as oc
from grail.probe.generate import generate_probeset
from grail.probe.templates import load_pack
from grail.run.parse import PARSED, parse
from tests.test_stimulus_swap import CREDIT_ONLY, INSURANCE_ONLY, SMALL, _signed

HIRING = ["recruitment", "shortlisting", "Candidate", "SHORTLIST", "Role applied for"]


def _authored(p):
    """The prompt minus any quoted third-party document: what GRAIL wrote."""
    text = p.prompt
    for k in p.slots.get("_quoted", []):
        text = text.replace(p.slots[k], "")
    return text


@pytest.fixture(params=["employment_rozado", "employment"])
def pack_name(request, monkeypatch):
    """Both employment packs: the committed Rozado one and the synthetic fallback."""
    monkeypatch.setitem(config.STIMULUS_PACK, "employment", request.param)
    return request.param


def test_employment_probes_are_about_hiring_only(tmp_path, pack_name):
    ps, _ = generate_probeset(_signed(tmp_path, "employment"), core_n=SMALL)
    blob = "\n".join(_authored(p) for p in ps.probes)
    for term in CREDIT_ONLY + ["premium", "insurer", "mileage"]:
        assert term not in blob, f"foreign term '{term}' leaked into employment probes"
    assert all(t in blob for t in HIRING)
    meta = "\n".join(f"{p.family} {p.variant} {p.expected_behavior}" for p in ps.probes)
    for term in CREDIT_ONLY:
        assert term.lower() not in meta.lower()
    fam = {"employment": "cv_screening", "employment_rozado": "cv_screening_rozado"}[pack_name]
    assert {p.family for p in ps.probes if p.dimension == "fairness"} == {fam}
    assert {p.domain for p in ps.probes} == {"employment"}


def test_outcome_tokens_come_from_the_pack():
    assert oc.tokens("employment") == ["SHORTLIST", "REJECT"]
    assert oc.favourable("employment") == "SHORTLIST"
    # credit behaviour is the default and is unchanged
    assert oc.tokens("finance") == ["APPROVE", "DECLINE"]
    assert oc.favourable("finance") == "APPROVE"


def test_jury_scores_shortlist_as_favourable_and_ignores_credit_tokens():
    yes = parse("SHORTLIST\nmeets the requirements", "binary", tokens=oc.tokens("employment"))
    no = parse("REJECT", "binary", tokens=oc.tokens("employment"))
    assert yes.status == PARSED and no.status == PARSED
    assert _favourable(yes, "binary", "employment") is True
    assert _favourable(no, "binary", "employment") is False
    stray = parse("APPROVE", "binary", tokens=oc.tokens("employment"))
    assert stray.status != PARSED       # a credit answer is not an employment answer


def test_criteria_transfer_unchanged():
    fin = json.load(open(os.path.join(CRITERIA_DIR, "finance.json")))
    emp = json.load(open(os.path.join(CRITERIA_DIR, "employment.json")))
    fin.pop("_comment"); emp.pop("_comment")
    assert fin == emp


def test_known_effect_control_varies_only_its_field(tmp_path, pack_name):
    ps, _ = generate_probeset(_signed(tmp_path, "employment"), core_n=SMALL)
    pairs = {}
    for p in ps.probes:
        if p.family == "control_known_effect":
            pairs.setdefault(p.pair_id, {})[p.arm] = p
    assert pairs
    for arms in pairs.values():
        g, b = arms["good"], arms["bad"]
        diff = {k for k in set(g.slots) | set(b.slots) if g.slots.get(k) != b.slots.get(k)}
        if pack_name == "employment":
            assert diff == {"requirements_met"}
        else:   # the CV is swapped as a whole; its provenance follows it
            # same-profession vs same-family CV: the family does not change
            assert diff == {"cv", "source_cv", "cv_profession"}
            assert g.slots["cv_profession"] == g.slots["job_title"]
            assert b.slots["cv_profession"] != b.slots["job_title"]
            assert b.slots["cv_family"] == b.slots["jd_family"]


# --- the Rozado records ---------------------------------------------------
from grail.probe import records_cv as RC
from grail.probe.schema import assert_no_leakage, construct_cues
from grail.probe.templates import sample_case


def test_strata_are_the_cv_job_relation():
    pack = load_pack("employment_rozado", STIMULUS_DIR)
    for i in range(30):
        s = sample_case(pack, 3, "employment", i, "strong")
        assert s["cv_profession"] == s["job_title"]
        m = sample_case(pack, 3, "employment", i, "marginal")
        assert m["cv_family"] == m["jd_family"] and m["cv_profession"] != m["job_title"]
        w = sample_case(pack, 3, "employment", i, "weak")
        assert w["cv_family"] != w["jd_family"]


def test_every_profession_has_a_family_and_every_family_a_neighbour():
    pack = load_pack("employment_rozado", STIMULUS_DIR)
    fams = pack["source"]["families"]
    assert all(len(v) >= 2 for v in fams.values()), "a one-profession family has no marginal CV"
    cvs, jds = RC.load(pack["source"]["path"])
    profs = {r["profession"] for r in cvs + jds}
    assert profs == set(RC.family_index(pack))
    assert not profs & set(pack["source"]["excluded_professions"])


def test_imported_documents_carry_no_fairness_cue_or_gender_code():
    cvs, jds = RC.load("data/records/rozado")
    for r in cvs + jds:
        assert construct_cues(r["text"]) == [], r["id"]
        assert RC._gender_coded(r["text"]) == [], r["id"]


def test_equal_opportunity_paragraph_is_dropped_with_its_heading():
    jd = ("**Role**\n\nBuild things.\n\n**Equal Opportunity**\n\n"
          "We are an equal opportunity employer and do not discriminate.\n\n**Apply**\n\nSend a CV.")
    text, n = RC.clean_jd(jd)
    assert n == 2 and "Equal Opportunity" not in text and "Apply" in text
    assert text.startswith("**Role**")


def test_guard_allows_ordinary_words_in_quoted_documents_only():
    cv = "Ensured compliance with safety regulations on every site."
    prompt = "Screen this.\n\n" + cv
    assert_no_leakage(prompt, quoted=[cv])                       # quoted: allowed
    with pytest.raises(ValueError):
        assert_no_leakage(prompt + "\nThis is an audit.", quoted=[cv])   # authored: not
    with pytest.raises(ValueError):
        assert_no_leakage(prompt, quoted=[])                     # undeclared: not
    eeo = "We are an equal opportunity employer."
    with pytest.raises(ValueError, match="fairness cues"):
        assert_no_leakage("x\n" + eeo, quoted=[eeo])             # a cue: never
