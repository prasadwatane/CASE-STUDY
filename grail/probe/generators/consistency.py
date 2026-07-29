"""Consistency probes — paraphrase sets plus a DE/EN pair over one case.

A consistency set holds the *same* application, presented with reworded
instructions and once in German. The field block is byte-identical across the
English members and numerically identical in the German member, so disagreement
within a set is sensitivity to wording or language and nothing else. The jury
later scores modal-agreement rate with a Wilson interval.

The German member is a hand-written rendering, not a translation produced at
generation time: a model in the generation path would make the probe set
non-reproducible and would put a model between the standard and the stimulus.
"""
from __future__ import annotations

from grail.probe.generators._common import clause_refs, stratum_plan
from grail.probe.schema import CORE, GOLD_NONE, Probe, digits
from grail.probe.templates import (DECIDE_INSTRUCTION_DE, N_PARAPHRASES,
                                   decide_instruction, render_application,
                                   sample_case)

FAMILY = "paraphrase_set"
N_EN_PARAPHRASES = min(3, N_PARAPHRASES)


def generate(ctx, items: list) -> list[Probe]:
    clause_ids, citations = clause_refs(items)
    n_base = ctx.n("consistency", 150)
    probes: list[Probe] = []

    plan = stratum_plan(n_base, ctx.strata)
    for idx, stratum in enumerate(plan):
        slots = sample_case(ctx.seed, ctx.domain, idx, stratum, ns="consistency")
        pair_id = f"{ctx.domain}:consistency:{idx:04d}"
        base_id = f"{pair_id}:en0"

        members = [(f"en{i}", "en", decide_instruction(i)) for i in range(N_EN_PARAPHRASES)]
        members.append(("de0", "de", DECIDE_INSTRUCTION_DE))

        base_digits = None
        for variant, lang, instruction in members:
            prompt = render_application(slots, instruction=instruction, lang=lang)
            if base_digits is None:
                base_digits = digits(prompt)
            elif digits(prompt) != base_digits:
                raise ValueError(
                    f"consistency member {pair_id}:{variant} does not carry the same "
                    "numbers as the rest of its set — the set would not be comparable")
            probes.append(Probe(
                id=f"{pair_id}:{variant}", domain=ctx.domain, dimension="consistency",
                family=FAMILY, clause_ids=clause_ids, citations=citations,
                prompt=prompt, sample_kind=CORE, stratum=stratum, pair_id=pair_id,
                variant=f"{lang}:{variant}",
                base_id=None if variant == "en0" else base_id,
                gold_route=GOLD_NONE,
                expected_behavior="same decision across every member of the set",
                slots=dict(slots, lang=lang), seed=ctx.seed))

    return probes
