"""Shared helpers for the generator library."""
from __future__ import annotations


def clause_refs(items: list) -> tuple[list[str], list[str]]:
    """(clause_ids, citations) for the checklist items backing a dimension."""
    return ([it["clause_id"] for it in items], [it["citation"] for it in items])


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
    """A flat, deterministic list of strata labels of length `total`."""
    alloc = allocate(total, strata)
    plan: list[str] = []
    for name in sorted(alloc):
        plan.extend([name] * alloc[name])
    return plan
