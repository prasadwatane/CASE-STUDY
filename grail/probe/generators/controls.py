"""Positive controls — probes whose correct answer is already known.

Every other probe in this repo is a *comparison*: two arms, or a prompt and its
reworded twin. That is the right design for measuring bias, and it has one blind
spot. If the full run comes back showing no approval gap, two explanations fit
equally well: the system under audit is even-handed, or the measurement chain is
broken — an unparseable response format, a silent refusal, arms crossed during
aggregation. A comparison probe cannot tell those apart. A control can.

Two families, both declared by the stimulus pack:

* **known_effect** — a pair differing in one *legitimate* decision-relevant
  field (missed payments in credit, recent claims in insurance) rather than a
  protected one. Any competent system should treat the worse case less
  favourably. If the pipeline cannot detect *that*, it cannot detect anything,
  and the finding is about the pipeline rather than the model.
* **extremes** — cases so lopsided the answer is not in doubt. These test that
  the system is engaging with the task at all and that responses parse.

Controls are stamped `sample_kind = CONTROL` and carry no clause ids: they are
instrument checks, not requirements derived from the law. Because headline
statistics may only use CORE probes, a control can never leak into a reported
number — the exclusion is structural rather than a rule someone has to remember.
"""
from __future__ import annotations

from grail.probe.schema import CONTROL, GOLD_NONE, Probe
from grail.probe.templates import render, sample_case

KNOWN_EFFECT_FAMILY = "control_known_effect"
EXTREME_FAMILY = "control_extreme"


def generate(ctx, n_pairs: int = 15, n_extremes: int = 4) -> list[Probe]:
    """15 pairs is enough for the sign test to reach significance if the effect is
    real (12 of 12 one-way gives p < 0.001, 6 of 6 gives p = 0.03) while staying
    cheap enough to run in full on every pilot."""
    spec = (ctx.pack.get("controls") or {})
    probes: list[Probe] = []

    if not spec:
        ctx.notes.append(
            f"controls: pack '{ctx.pack.get('name')}' declares none — a null result "
            "from this run will not be distinguishable from a broken pipeline")
        return probes

    probes.extend(_known_effect(ctx, spec.get("known_effect"), n_pairs))
    probes.extend(_extremes(ctx, spec.get("extremes"), n_extremes))
    return probes


def _known_effect(ctx, spec: dict | None, n_pairs: int) -> list[Probe]:
    if not spec:
        return []
    field, good, bad = spec["field"], spec["good"], spec["bad"]
    stratum = spec.get("stratum") or sorted(ctx.pack["strata"])[0]
    probes: list[Probe] = []

    for idx in range(n_pairs):
        base = sample_case(ctx.pack, ctx.seed, ctx.domain, idx, stratum,
                           ns="controls/known_effect")
        pair_id = f"{ctx.domain}:control:known_effect:{idx:04d}"
        for arm, value in (("good", good), ("bad", bad)):
            slots = dict(base)
            slots[field] = value
            probes.append(Probe(
                id=f"{pair_id}:{arm}", domain=ctx.domain, dimension="control",
                family=KNOWN_EFFECT_FAMILY, clause_ids=[], citations=[],
                prompt=render(ctx.pack, slots), sample_kind=CONTROL,
                stratum=stratum, pair_id=pair_id, variant=f"{field}={arm}",
                arm=arm, gold_route=GOLD_NONE, outcome_type=ctx.outcome_type,
                expected_behavior=spec.get("expect", ""),
                slots=dict(slots, control_field=field), seed=ctx.seed))
    return probes


def _extremes(ctx, spec: dict | None, n_each: int) -> list[Probe]:
    if not spec:
        return []
    stratum = sorted(ctx.pack["strata"])[0]
    probes: list[Probe] = []

    for arm in ("best", "worst"):
        overrides = spec.get(arm)
        if not overrides:
            continue
        for idx in range(n_each):
            slots = sample_case(ctx.pack, ctx.seed, ctx.domain, idx, stratum,
                                ns=f"controls/extreme/{arm}")
            unknown = set(overrides) - set(slots)
            if unknown:
                raise SystemExit(
                    f"pack '{ctx.pack['name']}': control override names fields the "
                    f"pack does not sample: {sorted(unknown)}")
            slots.update(overrides)
            probes.append(Probe(
                id=f"{ctx.domain}:control:extreme:{arm}:{idx:02d}",
                domain=ctx.domain, dimension="control", family=EXTREME_FAMILY,
                clause_ids=[], citations=[], prompt=render(ctx.pack, slots),
                sample_kind=CONTROL, stratum=stratum, variant=arm, arm=arm,
                gold_route=GOLD_NONE, outcome_type=ctx.outcome_type,
                expected_behavior=("an obviously acceptable case" if arm == "best"
                                   else "an obviously unacceptable case"),
                slots=slots, seed=ctx.seed))
    return probes
