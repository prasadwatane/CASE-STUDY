"""The audit checklist: requirements derived from clauses, awaiting a human sign.

A checklist item pairs a probeable clause with a derived requirement and the
dimension it feeds. The item text is a COPY of the clause as reviewed, so the
signature freezes exactly what the human saw — later corpus changes cannot
silently alter a signed requirement (they force a re-sign).
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
import json

from grail.ingest.schema import LegalUnit


@dataclass
class ChecklistItem:
    clause_id: str
    citation: str
    scope_partition: str
    dimension: str
    clause_text: str          # frozen copy of what the human reviewed
    requirement: str          # auto-suggested; human edits before signing
    criterion: str = ""       # measurable operationalization (filled later)

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass
class Checklist:
    domain: str
    instrument: str
    created_utc: str
    items: list[ChecklistItem] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "domain": self.domain,
            "instrument": self.instrument,
            "created_utc": self.created_utc,
            "items": [i.as_dict() for i in self.items],
        }

    def save(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(self.as_dict(), fh, ensure_ascii=False, indent=2)

    @staticmethod
    def load(path: str) -> "Checklist":
        with open(path, encoding="utf-8") as fh:
            d = json.load(fh)
        c = Checklist(d["domain"], d["instrument"], d["created_utc"])
        c.items = [ChecklistItem(**it) for it in d["items"]]
        return c


def _suggest_requirement(u: LegalUnit) -> str:
    """A conservative auto-suggestion. The human rewrites this at the gate."""
    first = u.text.split(". ")[0].strip().rstrip(".;")
    return f"The AI system under audit shall conform to {u.citation}: {first}."


def build_checklist(units: list[LegalUnit], clause_ids: list[str],
                    domain: str, instrument: str,
                    dimension_map: dict[str, str]) -> Checklist:
    by_id = {u.id: u for u in units}
    items: list[ChecklistItem] = []
    missing: list[str] = []
    for cid in clause_ids:
        u = by_id.get(cid)
        if u is None:
            missing.append(cid)
            continue
        items.append(ChecklistItem(
            clause_id=u.id,
            citation=u.citation,
            scope_partition=u.scope_partition,
            dimension=dimension_map.get(u.id, "unassigned"),
            clause_text=u.text,
            requirement=_suggest_requirement(u),
        ))
    if missing:
        raise SystemExit(
            "Committed clauses not found in corpus (rebuild index / check ids): "
            + ", ".join(missing))
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return Checklist(domain, instrument, now, items)
