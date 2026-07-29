"""Link obligations to the definitions and exceptions they depend on.

Done once at build time and stored in `related`. Retrieval uses these links to
return an obligation together with its context (skill: an obligation is only
meaningful with its defined terms and any carve-out that limits it).
"""
from __future__ import annotations
import re

from grail.ingest.schema import LegalUnit, DEFINITION, EXCEPTION, OBLIGATION, SCOPE
from grail.config_overrides import apply_scope_overrides


def _term_pattern(term: str) -> re.Pattern:
    # whole-word, case-insensitive; tolerate plural 's'
    return re.compile(rf"\b{re.escape(term)}s?\b", re.I)


def link_units(units: list[LegalUnit]) -> list[LegalUnit]:
    defs = [u for u in units if u.unit_type == DEFINITION and u.defined_term]
    by_container_exceptions: dict[str, list[str]] = {}
    for u in units:
        if u.unit_type in (EXCEPTION, SCOPE):
            by_container_exceptions.setdefault(u.container, []).append(u.id)

    for u in units:
        if u.unit_type not in (OBLIGATION,):
            continue
        related: list[str] = []
        # definitions whose term appears in the obligation text
        for d in defs:
            if _term_pattern(d.defined_term).search(u.text):
                related.append(d.id)
        # exceptions / scope carve-outs in the same container
        related.extend(by_container_exceptions.get(u.container, []))
        # de-dup, drop self
        u.related = [r for r in dict.fromkeys(related) if r != u.id]

    apply_scope_overrides(units)
    return units
