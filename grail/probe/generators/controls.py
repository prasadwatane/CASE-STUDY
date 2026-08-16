"""Positive controls — probes whose correct answer is already known.

Every other probe in this repo is a *comparison*: two arms, or a prompt and its
reworded twin. That is the right design for measuring bias, and it has one blind
spot. If the full run comes back showing no approval gap, two explanations fit
equally well: the system under audit is even-handed, or the measurement chain is
broken — an unparseable response format, a silent refusal, arms crossed during
aggregation. A comparison probe cannot tell those apart. A control can.

Three families, all declared by the stimulus pack:

* **known_effect** — a pair differing in one *legitimate* decision-relevant
  field (missed payments in credit, recent claims in insurance) rather than a
  protected one. Any competent system should treat the worse case less
  favourably. If the pipeline cannot detect *that*, it cannot detect anything,
  and the finding is about the pipeline rather than the model.
* **extremes** — cases so lopsided the answer is not in doubt. These test that
  the system is engaging with the task at all and that responses parse.
* **axis_planted** — the control `known_effect` cannot be. It plants an effect
  on the *protected axis itself*, by rendering an ordinary counterbalanced pair
  under a policy instruction that makes the axis token decision-relevant.

The third family exists because of a gap the first two leave open, and the gap
is not hypothetical: this repo's first full run found the audited model gave a
different decision under a gender swap in 1.0% of 393 matched pairs, while
`known_effect` fired cleanly at p = 0.002. Those two facts are compatible with
the model being near-invariant to the token, and equally compatible with the
token never reaching the decision at all — a `Ms.`/`Mr.` prefix is a much
weaker signal than a payment-history field, and a control on the latter says
nothing about the former. `known_effect` licenses "the pipeline detects
decision-relevant differences"; only `axis_planted` licenses "the pipeline
detects differences *on this axis*", which is the claim a null fairness result
actually rests on.

Both arms receive the identical instruction; only the axis slot differs, under
the same `assert_counterbalanced` invariant as the fairness probes themselves.
A refusal on the arm the policy names is not a failure of this control — it is
the token demonstrably reaching the decision, which is what the control asks.

Controls are stamped `sample_kind = CONTROL` and carry no clause ids: they are
instrument checks, not requirements derived from the law. Because headline
statistics may only use CORE probes, a control can never leak into a reported
number — the exclusion is structural rather than a rule someone has to remember.
"""
from __future__ import annotations

from grail.probe.generators._common import assert_counterbalanced
from grail.probe.schema import CONTROL, GOLD_NONE, Probe
from grail.probe.templates import render, sample_case

KNOWN_EFFECT_FAMILY = "control_known_effect"
EXTREME_FAMILY = "control_extreme"
AXIS_PLANTED_FAMILY = "control_axis_planted"


def generate(ctx, n_pairs: int = 15, n_extremes: int = 4,
             n_axis_pairs: int = 40) -> list[Probe]:
    """15 pairs is enough for the sign test to reach significance if the effect is
    real (12 of 12 one-way gives p < 0.001, 6 of 6 gives p = 0.03) while staying
    cheap enough to run in full on every pilot.

    The planted-axis control gets more (40) because it is measuring a *rate*,
    not just a direction: it has to distinguish "the token moves the decision
    often" from "the token moves it about as rarely as the real probes show".
    An exact two-sided sign test cannot reach 0.05 below six discordant pairs
    no matter how one-sided they are, so a control sized like `known_effect`
    could plausibly land under its own floor and report nothing.
    """
    spec = (ctx.pack.get("controls") or {})
    probes: list[Probe] = []

    if not spec:
        ctx.notes.append(
            f"controls: pack '{ctx.pack.get('name')}' declares none — a null result "
            "from this run will not be distinguishable from a broken pipeline")
        return probes

    probes.extend(_known_effect(ctx, spec.get("known_effect"), n_pairs))
    probes.extend(_extremes(ctx, spec.get("extremes"), n_extremes))
    probes.extend(_axis_planted(ctx, spec.get("axis_planted"), n_axis_pairs))

    if not spec.get("axis_planted") and (ctx.axes or []):
        ctx.notes.append(
            f"controls: pack '{ctx.pack.get('name')}' declares no planted-axis "
            "control, so nothing in this run shows the pipeline can detect an "
            "effect on a protected axis — a null fairness result will not be "
            "separable from an axis the model never read")
    return probes


def _axis_planted(ctx, spec: dict | None, n_pairs: int) -> list[Probe]:
    """A counterbalanced pair under an instruction that makes the axis matter.

    The instruction is pack data, never code: what counts as a decision-relevant
    policy is a property of the sub-domain, and it has to survive the leakage
    guard, so it is written and reviewed alongside the rest of the stimulus.
    """
    if not spec:
        return []

    axes = {a["name"]: a for a in (ctx.axes or [])}
    axis = axes.get(spec.get("axis"))
    if axis is None:
        ctx.notes.append(
            f"controls: pack declares a planted control on axis "
            f"'{spec.get('axis')}', which domain '{ctx.domain}' does not "
            "configure — skipped (see config.PROTECTED_AXES)")
        return []

    arms = {a["value"]: a for a in axis["arms"]}
    target = spec.get("target_arm")
    if target not in arms:
        raise SystemExit(
            f"pack '{ctx.pack['name']}': planted control names target arm "
            f"'{target}', but axis '{axis['name']}' has {sorted(arms)}")

    stratum = spec.get("stratum") or sorted(ctx.pack["strata"])[0]
    text = spec["instruction"]
    probes: list[Probe] = []

    for idx in range(n_pairs):
        base = sample_case(ctx.pack, ctx.seed, ctx.domain, idx, stratum,
                           ns=f"controls/axis_planted/{axis['name']}")
        pair_id = f"{ctx.domain}:control:axis_planted:{axis['name']}:{idx:04d}"

        rendered = []
        for value in sorted(arms):
            slots = dict(base)
            slots.update(arms[value]["slots"])
            rendered.append((value, slots))
        for _, slots in rendered[1:]:
            assert_counterbalanced(rendered[0][1], slots, axis["slot"], pair_id)

        for value, slots in rendered:
            probes.append(Probe(
                id=f"{pair_id}:{value}", domain=ctx.domain, dimension="control",
                family=AXIS_PLANTED_FAMILY, clause_ids=[], citations=[],
                prompt=render(ctx.pack, slots, instruction=text),
                sample_kind=CONTROL, stratum=stratum, pair_id=pair_id,
                variant=f"{axis['name']}={value}", axis=axis["name"], arm=value,
                gold_route=GOLD_NONE, outcome_type=ctx.outcome_type,
                expected_behavior=spec.get("expect", ""),
                slots=dict(slots, planted_target_arm=target), seed=ctx.seed))
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
