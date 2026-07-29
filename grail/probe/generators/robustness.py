"""Robustness probes — meaning-preserving perturbations of a base application.

Each base case yields one unperturbed probe plus one probe per perturbation, all
sharing a `pair_id`, so the jury can later compute a paired accuracy drop and run
McNemar on the discordant pairs.

"Meaning-preserving" is enforced, not asserted in prose: a perturbation may
reflow, re-case, mis-spell or reorder text, but the digit multiset of the prompt
must be identical to the base. A perturbation that quietly changed a number would
turn a robustness result into a garbage-in result, so such a probe cannot be
emitted at all.
"""
from __future__ import annotations

from grail.probe.generators._common import clause_refs, stratum_plan
from grail.probe.schema import CORE, GOLD_NONE, Probe, derive_rng, digits
from grail.probe.templates import PERTURBATIONS, render, sample_case

FAMILY = "perturbed_application"


def generate(ctx, items: list) -> list[Probe]:
    clause_ids, citations = clause_refs(items)
    n_base = ctx.n("robustness", 300)
    probes: list[Probe] = []

    no_ops: dict[str, int] = {}
    plan = stratum_plan(n_base, ctx.strata)
    for idx, stratum in enumerate(plan):
        slots = sample_case(ctx.pack, ctx.seed, ctx.domain, idx, stratum,
                            ns="robustness")
        base_prompt = render(ctx.pack, slots)
        pair_id = f"{ctx.domain}:robustness:{idx:04d}"
        base_id = f"{pair_id}:base"
        base_digits = digits(base_prompt)

        probes.append(Probe(
            id=base_id, domain=ctx.domain, dimension="robustness", family=FAMILY,
            clause_ids=clause_ids, citations=citations, prompt=base_prompt,
            sample_kind=CORE, stratum=stratum, pair_id=pair_id, variant="base",
            gold_route=GOLD_NONE, outcome_type=ctx.outcome_type,
            expected_behavior="outcome invariant to meaning-preserving rewording",
            slots=slots, seed=ctx.seed))

        for name, fn in PERTURBATIONS:
            r = derive_rng(ctx.seed, ctx.domain, "robustness", idx, name)
            prompt = fn(base_prompt, r)
            if digits(prompt) != base_digits:
                raise ValueError(
                    f"perturbation '{name}' altered the numbers in {base_id} — "
                    "a robustness probe must be meaning-preserving")
            if prompt == base_prompt:
                # A perturbation that changed nothing would enter the paired test
                # as a duplicate of its own base and bias the drop toward zero.
                no_ops[name] = no_ops.get(name, 0) + 1
                continue
            probes.append(Probe(
                id=f"{pair_id}:{name}", domain=ctx.domain, dimension="robustness",
                family=FAMILY, clause_ids=clause_ids, citations=citations,
                prompt=prompt, sample_kind=CORE, stratum=stratum, pair_id=pair_id,
                variant=name, base_id=base_id, gold_route=GOLD_NONE,
                outcome_type=ctx.outcome_type,
                expected_behavior="outcome invariant to meaning-preserving rewording",
                slots=slots, seed=ctx.seed))

    for name, count in sorted(no_ops.items()):
        ctx.notes.append(
            f"robustness: perturbation '{name}' left {count}/{n_base} base cases "
            "unchanged and those probes were dropped")
    return probes
