"""Transparency probes — can a deployer actually interpret and use the output?

Article 13(1) is a hybrid clause: part of it is documentation the provider ships
(procedural, out of probe scope) and part is a property of the system's output
that a deployer has to be able to work with. Only the latter is probed here, in
two families:

* `explanation_request` — decide, then name the details that weighed most and
  state a confidence. Tests whether the stated reasons are usable and whether
  confidence is expressed at all.
* `counterfactual_request` — decide, then say what would have had to differ for a
  different outcome. Tests whether a front-line officer could act on the output.

Both instructions come from the stimulus pack, so the sub-domain decides what
"explain your decision" concretely asks for — a lending rationale in credit, a
rating rationale in insurance.

Both are qualitative, so they are scored by the gated judge rather than the jury,
and the probe records nothing about how to score them — the rubric is built later
from the frozen clause text plus its operationalized criterion.
"""
from __future__ import annotations

from grail.probe.generators._common import clause_refs, stratum_plan
from grail.probe.schema import CORE, GOLD_NONE, Probe
from grail.probe.templates import instruction, render, sample_case

FAMILIES = [("explanation_request", "explain",
             "states the decisive details and a confidence value"),
            ("counterfactual_request", "counterfactual",
             "states what would have to change for a different outcome")]


def generate(ctx, items: list) -> list[Probe]:
    clause_ids, citations = clause_refs(items)
    n_total = ctx.n("transparency", 150)
    # round UP per family: falling one case short of the pre-registered size to
    # keep the families even would be the wrong trade
    per_family = -(-n_total // len(FAMILIES))
    probes: list[Probe] = []

    for family, instr_key, expectation in FAMILIES:
        instr = instruction(ctx.pack, instr_key)
        plan = stratum_plan(per_family, ctx.strata)
        for idx, stratum in enumerate(plan):
            slots = sample_case(ctx.pack, ctx.seed, ctx.domain, idx, stratum,
                                ns=f"transparency/{family}")
            probes.append(Probe(
                id=f"{ctx.domain}:transparency:{family}:{idx:04d}",
                domain=ctx.domain, dimension="transparency", family=family,
                clause_ids=clause_ids, citations=citations,
                prompt=render(ctx.pack, slots, instruction=instr),
                sample_kind=CORE, stratum=stratum, variant=family,
                gold_route=GOLD_NONE, outcome_type=ctx.outcome_type,
                expected_behavior=expectation, slots=slots, seed=ctx.seed))

    if per_family * len(FAMILIES) != n_total:
        ctx.notes.append(
            f"transparency: {n_total} requested, {per_family * len(FAMILIES)} emitted "
            f"({per_family} per family across {len(FAMILIES)} families)")
    return probes
