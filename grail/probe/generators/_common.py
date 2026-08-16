"""Shared helpers for the generator library."""
from __future__ import annotations


def clause_refs(items: list) -> tuple[list[str], list[str]]:
    """(clause_ids, citations) for the checklist items backing a dimension."""
    return ([it["clause_id"] for it in items], [it["citation"] for it in items])


def assert_counterbalanced(a: dict, b: dict, axis_slot: str, pair_id: str) -> None:
    """Two arms of a pair may differ in the axis slot and in nothing else.

    Shared by the fairness generator and the planted-axis control, deliberately:
    a control only licenses a claim about the measurement if it travels through
    the same machinery, under the same invariant, as the thing it validates.
    """
    differing = {k for k in set(a) | set(b) if a.get(k) != b.get(k)}
    if differing != {axis_slot}:
        raise ValueError(
            f"counterbalancing broken for {pair_id}: arms differ in {sorted(differing)}, "
            f"expected only {{'{axis_slot}'}}. A profile slot is tracking the "
            "protected arm — the group gap would be an artefact of the probe set.")


def allocate(total: int, proportions: dict) -> dict:
    """Split `total` across strata by proportion, largest-remainder, exact sum.

    Deterministic: ties are broken by stratum name, so the allocation is part of
    the pre-registration rather than an artefact of dict ordering.
    """
    if not proportions:
        return {}
    raw = {k: total * v for k, v in proportions.items()}
    base = {k: int(v) for k, v in raw.items()}
    remainder = total - sum(base.values())
    order = sorted(raw, key=lambda k: (-(raw[k] - base[k]), k))
    for k in order[:remainder]:
        base[k] += 1
    return base


def stratum_plan(total: int, strata: dict) -> list[str]:
    """A flat, deterministic list of strata labels of length `total`.

    PREFIX-STABLE by construction: the label at index `i` depends only on the
    labels before it, never on `total`. Growing a probe set therefore *extends*
    it — case 0 stays case 0, keeps its stratum, keeps its content hash, and
    keeps cache-hitting against responses already paid for.

    This is not a micro-optimisation. Sizing in this repo is pilot-informed: the
    flip rate and the discordance rate are measured, then N is raised to match.
    With the obvious implementation — allocate totals, then emit sorted blocks —
    raising N remaps almost every index to a different stratum, changes every
    prompt, and silently orphans the entire response log. The one artefact that
    cannot be regenerated would be thrown away by a config edit.

    The rule is sequential apportionment (Sainte-Laguë): at each step give the
    next slot to whichever stratum is furthest behind its share, measured as
    (count + 0.5) / share. Ties break by name, so the sequence is part of the
    pre-registration rather than an artefact of dict ordering. Any prefix stays
    within one case of the exact largest-remainder allocation for its length.
    """
    if not strata or total <= 0:
        return []
    counts = {k: 0 for k in strata}
    plan: list[str] = []
    for _ in range(total):
        pick = min(sorted(counts),
                   key=lambda k: (counts[k] + 0.5) / strata[k] if strata[k] > 0
                   else float("inf"))
        counts[pick] += 1
        plan.append(pick)
    return plan
