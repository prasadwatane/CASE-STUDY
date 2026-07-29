"""Apply curated scope-partition overrides from config (human-signed values)."""
from __future__ import annotations

from config import SCOPE_OVERRIDES
from grail.ingest.schema import LegalUnit


def apply_scope_overrides(units: list[LegalUnit]) -> None:
    for u in units:
        if u.id in SCOPE_OVERRIDES:
            u.scope_partition = SCOPE_OVERRIDES[u.id]
