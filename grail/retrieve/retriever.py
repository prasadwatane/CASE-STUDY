"""Evaluation-time retrieval — THIS is where RAG is used.

Given a target document (a snippet of the model-under-audit's output, or a
compliance question), retrieve the relevant OBLIGATIONS, then expand each with
its DEFINITIONS and EXCEPTIONS and parent chapeau. Clause extraction already
happened deterministically upstream; here we only *retrieve* and *assemble*.

Only probeable partitions (behavioral, hybrid) are eligible as primary hits;
procedural clauses are never returned as obligations but may appear as context.
"""
from __future__ import annotations
from dataclasses import dataclass

from config import TOP_K, PROBEABLE_PARTITIONS
from grail.ingest.schema import (
    LegalUnit, OBLIGATION, DEFINITION, EXCEPTION, SCOPE, CHAPEAU,
)
from grail.index.hybrid_index import HybridIndex


@dataclass
class RetrievedObligation:
    obligation: LegalUnit
    chapeau: LegalUnit | None
    definitions: list[LegalUnit]
    exceptions: list[LegalUnit]
    score: float

    def as_dict(self) -> dict:
        return {
            "citation": self.obligation.citation,
            "id": self.obligation.id,
            "scope_partition": self.obligation.scope_partition,
            "text": self.obligation.text,
            "score": round(self.score, 5),
            "chapeau": self.chapeau.text if self.chapeau else None,
            "definitions": [
                {"citation": d.citation, "term": d.defined_term, "text": d.text}
                for d in self.definitions],
            "exceptions": [
                {"citation": e.citation, "text": e.text} for e in self.exceptions],
        }


class Retriever:
    def __init__(self, index: HybridIndex):
        self.index = index
        self.by_id = {u.id: u for u in index.units}
        # obligations in the probeable partitions are the only primary targets
        self.eligible = {
            i for i, u in enumerate(index.units)
            if u.unit_type == OBLIGATION
            and u.scope_partition in PROBEABLE_PARTITIONS
        }

    def _unit(self, uid: str) -> LegalUnit | None:
        return self.by_id.get(uid)

    def retrieve(self, target_document: str, top_k: int = TOP_K
                 ) -> list[RetrievedObligation]:
        hits = self.index.search(target_document, allowed_idx=self.eligible)
        out: list[RetrievedObligation] = []
        for idx, score in hits[:top_k]:
            ob = self.index.units[idx]
            chapeau = self._unit(ob.parent_id) if ob.parent_id else None
            defs, exs = [], []
            for rid in ob.related:
                r = self._unit(rid)
                if r is None:
                    continue
                if r.unit_type == DEFINITION:
                    defs.append(r)
                elif r.unit_type in (EXCEPTION, SCOPE):
                    exs.append(r)
            out.append(RetrievedObligation(ob, chapeau, defs, exs, score))
        return out
