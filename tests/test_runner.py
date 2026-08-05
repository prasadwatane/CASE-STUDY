"""Tests for the runner, the parser and the positive controls.

The parser tests carry most of the weight. Every downstream statistic is
computed on parsed outcomes, so a parser that quietly turns a refusal into a
DECLINE would bias the whole audit toward the system looking harsher than it is,
and nothing further down would notice.

The control tests do the thing the controls exist for, one level up: a model that
reacts to the known-effect field must make the control fire, and a model that
ignores it must not. A control that always fires proves nothing.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from config import STIMULUS_DIR, STRATUM_PLAN
from grail.ground.checklist import Checklist, ChecklistItem
from grail.ground.notary import save_signed, sign
from grail.probe.generate import generate_probeset
from grail.probe.schema import CONTROL, CORE
from grail.run import store
from grail.run.client import StubModel, field_sensitive_rule, hash_rule, params_hash
from grail.run.parse import (PARSED, REFUSED, UNPARSEABLE, parse_binary,
                             parse_continuous)
from grail.run.pilot import report
from grail.run.runner import run, select

SMALL = {"fairness": 20, "robustness": 6, "consistency": 4, "transparency": 4,
         "truthfulness": 300}


def _probes(tmp_path, domain="finance", dimension="fairness", pack=None):
    # Pinned to the synthetic pack by default: the control tests drive a stub
    # that reads a named field out of the prompt, so they must not follow
    # whichever pack config commits. Pass pack= to exercise another.
    if pack is None and domain == "finance":
        pack = "credit"
    c = Checklist(domain, "EU AI Act", "2026-01-01T00:00:00+00:00")
    c.items = [ChecklistItem("AIA:Art10(2)(f)", "Article 10(2)(f)", "hybrid",
                             dimension, "text", "req", "")]
    p = tmp_path / f"{domain}_{dimension}_signed.json"
    save_signed(sign(c, "Tester"), str(p))
    ps, _ = generate_probeset(str(p), core_n=SMALL, pack=pack)
    return ps.probes


# --- parsing ----------------------------------------------------------------
@pytest.mark.parametrize("text,expected", [
    ("APPROVE", "APPROVE"),
    ("DECLINE\nThe applicant has missed payments.", "DECLINE"),
    ("  approve  ", "APPROVE"),
    ("**APPROVE**", "APPROVE"),
    ("APPROVE.", "APPROVE"),
    ("Decision: DECLINE", "DECLINE"),
])
def test_binary_parsing_handles_ordinary_formatting(text, expected):
    out = parse_binary(text, ["APPROVE", "DECLINE"])
    assert out.status == PARSED and out.value == expected


def test_a_verdict_below_a_preamble_is_still_found():
    out = parse_binary("Let me consider this.\n\nAPPROVE", ["APPROVE", "DECLINE"])
    assert out.status == PARSED and out.value == "APPROVE"
    assert "below the first line" in out.note


def test_refusals_are_not_silently_scored_as_declines():
    """The failure that would bias every downstream rate."""
    for text in ("I'm not able to make lending decisions.",
                 "I cannot provide a decision on this application.",
                 "As an AI, I would not feel comfortable deciding this."):
        out = parse_binary(text, ["APPROVE", "DECLINE"])
        assert out.status == REFUSED, f"refusal misparsed: {text!r} -> {out}"
        assert out.value is None


def test_ambiguous_and_empty_responses_are_flagged():
    assert parse_binary("APPROVE or DECLINE?", ["APPROVE", "DECLINE"]).status == UNPARSEABLE
    assert parse_binary("", ["APPROVE", "DECLINE"]).status == UNPARSEABLE
    assert parse_binary("Hmm.", ["APPROVE", "DECLINE"]).status == UNPARSEABLE


@pytest.mark.parametrize("text,expected", [
    ("842", 842.0), ("EUR 1290.50", 1290.5), ("1 240", 1240.0),
    ("The premium is 655 EUR per year.", 655.0),
])
def test_continuous_parsing(text, expected):
    out = parse_continuous(text)
    assert out.status == PARSED and out.value == pytest.approx(expected)


def test_continuous_refusal_and_junk():
    assert parse_continuous("I'm unable to quote a premium.").status == REFUSED
    assert parse_continuous("no idea").status == UNPARSEABLE


# --- the log ----------------------------------------------------------------
def test_runner_refuses_a_stub_by_default(tmp_path):
    probes = _probes(tmp_path)
    with pytest.raises(SystemExit, match="not evidence"):
        run(probes, StubModel(), str(tmp_path / "r.jsonl"), limit=3)


def test_responses_are_logged_hash_chained_and_cached(tmp_path):
    probes = _probes(tmp_path)
    log = str(tmp_path / "responses.jsonl")

    _, first = run(probes, StubModel(), log, limit=10, allow_stub=True)
    assert first.called == first.requested and first.cached == 0
    assert store.verify_chain(store.load(log))[0]

    _, second = run(probes, StubModel(), log, limit=10, allow_stub=True)
    assert second.called == 0 and second.cached == first.requested, "re-run paid twice"


def test_a_changed_probe_is_not_served_from_cache(tmp_path):
    """Records key on probe CONTENT, so an edited probe is a different question."""
    probes = _probes(tmp_path)
    log = str(tmp_path / "responses.jsonl")
    run(probes[:5], StubModel(), log, limit=5, allow_stub=True)

    edited = probes[0]
    edited.prompt += "\n\nPlease be brief."
    edited.content_sha256 = edited.compute_hash()
    _, summary = run([edited], StubModel(), log, limit=1, allow_stub=True)
    assert summary.called == 1 and summary.cached == 0


def test_different_temperature_is_a_different_record(tmp_path):
    probes = _probes(tmp_path)
    log = str(tmp_path / "responses.jsonl")
    run(probes[:4], StubModel(), log, params={"temperature": 0.0}, limit=4, allow_stub=True)
    _, s = run(probes[:4], StubModel(), log, params={"temperature": 0.7}, limit=4,
               allow_stub=True)
    assert s.called == 4
    assert params_hash({"temperature": 0.0}) != params_hash({"temperature": 0.7})


def test_a_failing_model_is_recorded_not_raised(tmp_path):
    class Broken(StubModel):
        def generate(self, prompt, **params):
            raise RuntimeError("upstream 503")

    probes = _probes(tmp_path)
    log = str(tmp_path / "responses.jsonl")
    fresh, summary = run(probes, Broken(), log, limit=3, allow_stub=True)
    assert summary.errors == summary.called > 0
    assert all("upstream 503" in r.error for r in fresh)
    assert store.verify_chain(store.load(log))[0]


def test_a_batching_model_is_used_in_one_call(tmp_path):
    """Local engines batch; the runner must not feed them one prompt at a time."""
    calls = {"batch": 0, "single": 0}

    class Batching(StubModel):
        def generate_batch(self, prompts, **params):
            calls["batch"] += 1
            return [hash_rule(p) for p in prompts]

        def generate(self, prompt, **params):
            calls["single"] += 1
            return hash_rule(prompt)

    probes = _probes(tmp_path)
    log = str(tmp_path / "r.jsonl")
    fresh, summary = run(probes, Batching(), log, limit=None, allow_stub=True)
    assert calls["batch"] == 1 and calls["single"] == 0
    assert len(fresh) == summary.called == len(probes)
    assert store.verify_chain(store.load(log))[0]


def test_a_misaligned_batch_is_rejected_rather_than_recorded(tmp_path):
    """Dropping a response would silently pair every later probe with the wrong text."""
    class Short(StubModel):
        def generate_batch(self, prompts, **params):
            return [hash_rule(p) for p in prompts[:-1]]        # one too few

    probes = _probes(tmp_path)
    log = str(tmp_path / "r.jsonl")
    fresh, summary = run(probes, Short(), log, limit=None, allow_stub=True)
    assert summary.errors == len(fresh) > 0
    assert all("misaligned" in r.error for r in fresh)
    assert all(r.response == "" for r in fresh), "a misaligned batch was kept"


def test_batching_still_honours_the_cache(tmp_path):
    class Batching(StubModel):
        def generate_batch(self, prompts, **params):
            return [hash_rule(p) for p in prompts]

    probes = _probes(tmp_path)
    log = str(tmp_path / "r.jsonl")
    run(probes, Batching(), log, limit=None, allow_stub=True)
    _, second = run(probes, Batching(), log, limit=None, allow_stub=True)
    assert second.called == 0 and second.cached == len(probes)


def test_truncating_the_response_log_is_detected(tmp_path):
    probes = _probes(tmp_path)
    log = str(tmp_path / "responses.jsonl")
    run(probes, StubModel(), log, limit=6, allow_stub=True)
    lines = open(log).read().strip().split("\n")
    open(log, "w").write("\n".join(lines[:3]) + "\n")
    with pytest.raises(SystemExit, match="Rows were removed"):
        store.append(log, [])


# --- selection --------------------------------------------------------------
def test_pilot_selection_is_seeded_and_spread_across_dimensions(tmp_path):
    c = Checklist("finance", "EU AI Act", "2026-01-01T00:00:00+00:00")
    c.items = [ChecklistItem("AIA:Art10(2)(f)", "Article 10(2)(f)", "hybrid",
                             "fairness", "t", "r", ""),
               ChecklistItem("AIA:Art15(1)", "Article 15(1)", "behavioral",
                             "robustness", "t", "r", "")]
    p = tmp_path / "multi_signed.json"
    save_signed(sign(c, "Tester"), str(p))
    ps, _ = generate_probeset(str(p), core_n=SMALL, pack="credit")

    a = select(ps.probes, 30, seed=1)
    b = select(ps.probes, 30, seed=1)
    assert [x.id for x in a] == [x.id for x in b], "selection is not reproducible"
    assert select(ps.probes, 30, seed=2) != a
    assert len({x.dimension for x in a}) > 1, "a pilot drew from one dimension only"

    # every control runs, always — a proportional sample of them is worse than none
    all_controls = {x.id for x in ps.probes if x.sample_kind == CONTROL}
    assert all_controls <= {x.id for x in a}, "controls were sampled rather than run in full"

    # pairs are indivisible: a variant without its base is an unusable observation
    chosen = {x.id for x in a}
    for probe in a:
        if probe.base_id:
            assert probe.base_id in chosen, (
                f"{probe.id} was selected without its base — the comparison is lost")


def test_a_pilot_can_actually_answer_its_four_questions(tmp_path):
    """The dry run that motivated the pairing rules: 50 probes, 1 control, 0 pairs."""
    c = Checklist("finance", "EU AI Act", "2026-01-01T00:00:00+00:00")
    c.items = [ChecklistItem("AIA:Art10(2)(f)", "Article 10(2)(f)", "hybrid",
                             "fairness", "t", "r", ""),
               ChecklistItem("AIA:Art15(1)", "Article 15(1)", "behavioral",
                             "robustness", "t", "r", "")]
    p = tmp_path / "four_signed.json"
    save_signed(sign(c, "Tester"), str(p))
    ps, _ = generate_probeset(str(p), core_n={"fairness": 40, "robustness": 20},
                              pack="credit")

    log = str(tmp_path / "r.jsonl")
    run(ps.probes, StubModel(), log, limit=50, seed=3, allow_stub=True)
    rep = report(ps.probes, store.load(log))

    assert rep["parse_rate"] > 0, "question 1 unanswered"
    assert rep["base_rate"] is not None, "question 2 unanswered"
    assert rep["flip_rate"] is not None, "question 3 unanswered: no complete pairs"
    assert rep["controls"].get("known_effect"), "question 4 unanswered: no controls run"


# --- positive controls ------------------------------------------------------
def test_controls_are_generated_and_never_count_as_core(tmp_path):
    probes = _probes(tmp_path)
    controls = [p for p in probes if p.sample_kind == CONTROL]
    assert controls, "no positive controls generated"
    assert all(p.clause_ids == [] for p in controls), (
        "a control is an instrument check, not a requirement derived from a clause")
    assert all(p.sample_kind == CORE for p in probes if p.dimension == "fairness")


def test_known_effect_pairs_differ_in_exactly_the_declared_field(tmp_path):
    probes = _probes(tmp_path)
    pairs = {}
    for p in probes:
        if p.family == "control_known_effect":
            pairs.setdefault(p.pair_id, []).append(p)
    assert pairs
    for pair_id, (a, b) in pairs.items():
        field = a.slots["control_field"]
        differing = {k for k in set(a.slots) | set(b.slots)
                     if a.slots.get(k) != b.slots.get(k)}
        assert differing == {field}, f"{pair_id} differs in {sorted(differing)}"


def test_a_control_fires_for_a_sensitive_model_and_not_for_a_blind_one(tmp_path):
    """The control must be capable of both answers, or it measures nothing."""
    probes = _probes(tmp_path)
    sensitive = StubModel(rule=field_sensitive_rule(
        "Payments missed in the last 24 months", 1.0), model_id="stub/sensitive")
    blind = StubModel(rule=hash_rule, model_id="stub/blind")

    results = []
    for model in (sensitive, blind):
        log = str(tmp_path / f"{model.id.replace('/', '_')}.jsonl")
        run(probes, model, log, limit=None, allow_stub=True)
        results.append(report(probes, store.load(log))["controls"]["known_effect"])

    sens, rand = results
    assert sens["fired"], f"a model that reads the field did not trip the control: {sens}"
    assert sens["good_favoured"] > sens["bad_favoured"]
    assert not rand["fired"], (
        f"a model blind to the field tripped it anyway — the control is vacuous: {rand}")


def test_a_control_needs_DIRECTION_not_just_disagreement():
    """Half the pairs differing is what random answering looks like."""
    from grail.run.pilot import sign_test
    assert sign_test(10, 20) == pytest.approx(1.0)      # perfectly split: no signal
    assert sign_test(20, 20) < 0.001                     # all one way: signal
    assert sign_test(0, 0) is None                       # nothing discordant


# --- the pilot report -------------------------------------------------------
def test_report_flags_refusals_and_a_dead_control(tmp_path):
    probes = _probes(tmp_path)
    log = str(tmp_path / "r.jsonl")
    run(probes, StubModel(refusal_rate=0.5), log, limit=None, allow_stub=True)
    rep = report(probes, store.load(log))
    assert rep["refusal_rate"] > 0.05
    assert any("REFUSAL RATE" in v for v in rep["verdicts"])
    assert any("POSITIVE CONTROL DID NOT FIRE" in v for v in rep["verdicts"])


def test_report_measures_the_flip_rate_against_the_assumption(tmp_path):
    probes = _probes(tmp_path, dimension="robustness")
    log = str(tmp_path / "r.jsonl")
    run(probes, StubModel(), log, limit=None, allow_stub=True)
    rep = report(probes, store.load(log), assumed_flip_rate=0.10)
    assert rep["flip_rate"] is not None
    assert rep["flip_rate"]["comparisons"] > 0


def test_report_recomputes_power_at_the_measured_base_rate(tmp_path):
    probes = _probes(tmp_path)
    log = str(tmp_path / "r.jsonl")
    run(probes, StubModel(), log, limit=None, allow_stub=True)
    rep = report(probes, store.load(log))
    assert rep["base_rate"]["sizing_assumed"] == 0.5
    assert rep["effective_power"]["gap_detectable_at_n393"] > 0


@pytest.mark.parametrize("domain", sorted(STRATUM_PLAN))
def test_controls_exist_for_every_sub_domain(tmp_path, domain):
    probes = _probes(tmp_path, domain=domain)
    controls = [p for p in probes if p.sample_kind == CONTROL]
    assert controls, f"{domain} has no positive controls"
    assert {p.outcome_type for p in controls} == {
        "continuous" if domain == "insurance" else "binary"}
