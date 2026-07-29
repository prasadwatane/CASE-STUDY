"""Fairness probes — counterbalanced credit applications, stratified by strength.

The design in one sentence: sample an applicant profile once, render it once per
arm of a protected axis, and let nothing else differ.

That is the whole measurement. If any other slot co-varies with the arm — the
classic slot-to-group mapping bug, where the profile RNG is advanced by the arm
assignment and the two arms silently drift apart — then a group gap measured
later is a property of the probe set, not of the system under audit. Two defences:

* the profile RNG is derived from the case key only and never from the arm, and
* `_assert_counterbalanced` re-checks every emitted pair and raises if more than
  the axis slot differs. It is a runtime invariant, not just a test.

Stratification by credit strength matters because a gap concentrated in the
marginal band is the realistic failure mode: strong applications are approved
and weak ones declined almost regardless of the arm, so pooling the strata dilutes
exactly the signal worth reporting. The strata are fixed in config, i.e.
pre-registered, so the split cannot be chosen after seeing results.
"""
from __future__ import annotations

from grail.probe.generators._common import clause_refs, stratum_plan
from grail.probe.schema import CORE, GOLD_NONE, Probe
from grail.probe.templates import case_family, render, sample_case


def _assert_counterbalanced(a: dict, b: dict, axis_slot: str, pair_id: str) -> None:
    differing = {k for k in set(a) | set(b) if a.get(k) != b.get(k)}
    if differing != {axis_slot}:
        raise ValueError(
            f"counterbalancing broken for {pair_id}: arms differ in {sorted(differing)}, "
            f"expected only {{'{axis_slot}'}}. A profile slot is tracking the "
            "protected arm — the group gap would be an artefact of the probe set.")


def generate(ctx, items: list) -> list[Probe]:
    clause_ids, citations = clause_refs(items)
    n_pairs = ctx.n("fairness", 300)
    axes = ctx.axes or []
    probes: list[Probe] = []

    if not axes:
        ctx.notes.append(
            "fairness: no protected axis configured for this domain — no fairness "
            "probes generated (see config.PROTECTED_AXES)")
        return probes

    for axis in axes:
        axis_name = axis["name"]
        axis_slot = axis["slot"]
        arms = axis["arms"]
        if len(arms) < 2:
            ctx.notes.append(f"fairness: axis '{axis_name}' has fewer than two arms — skipped")
            continue

        plan = stratum_plan(n_pairs, ctx.strata)
        for idx, stratum in enumerate(plan):
            base = sample_case(ctx.pack, ctx.seed, ctx.domain, idx, stratum,
                               ns=f"fairness/{axis_name}")
            pair_id = f"{ctx.domain}:fairness:{axis_name}:{idx:04d}"

            rendered = []
            for arm in arms:
                slots = dict(base)
                slots.update(arm["slots"])
                rendered.append((arm, slots))

            # every arm must match the first in all but the axis slot
            for _, slots in rendered[1:]:
                _assert_counterbalanced(rendered[0][1], slots, axis_slot, pair_id)

            for arm, slots in rendered:
                probes.append(Probe(
                    id=f"{pair_id}:{arm['value']}",
                    domain=ctx.domain,
                    dimension="fairness",
                    family=case_family(ctx.pack),
                    clause_ids=clause_ids,
                    citations=citations,
                    prompt=render(ctx.pack, slots),
                    sample_kind=CORE,
                    stratum=stratum,
                    pair_id=pair_id,
                    variant=f"{axis_name}={arm['value']}",
                    axis=axis_name,
                    arm=arm["value"],
                    gold_route=GOLD_NONE,   # scored by comparing arms, not against a key
                    outcome_type=ctx.outcome_type,
                    expected_behavior="outcome invariant to the axis arm",
                    slots=slots,
                    seed=ctx.seed,
                ))

    return probes
