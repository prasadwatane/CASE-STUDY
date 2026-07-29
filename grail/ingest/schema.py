"""Data model for a single legal unit.

Principle (v3): the smallest legal unit is Article -> Paragraph -> Point.
Obligations are stored at that granularity so later compliance checking is
precise (e.g. `Article 10(2)(b)` rather than a page-sized chunk).

Clauses are produced by DETERMINISTIC STRUCTURAL PARSING, not by RAG.
RAG (see grail/retrieve) is used later, at evaluation time, to fetch the
relevant obligations plus their definitions and exceptions for a target doc.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional
import json

# Scope partition (skill non-negotiable): requirements are derived only from
# BEHAVIORAL and HYBRID clauses; PROCEDURAL clauses are declared out of scope.
BEHAVIORAL = "behavioral"
HYBRID = "hybrid"
PROCEDURAL = "procedural"

# Unit type: what kind of legal statement this is.
OBLIGATION = "obligation"
DEFINITION = "definition"
EXCEPTION = "exception"
SCOPE = "scope"          # classification / applicability text
CHAPEAU = "chapeau"      # introductory text of a paragraph that has points


@dataclass
class LegalUnit:
    # Identity ---------------------------------------------------------------
    id: str                      # e.g. "AIA:Art10(2)(b)"  (stable, citable)
    citation: str                # human form, e.g. "Article 10(2)(b)"
    instrument: str              # e.g. "Regulation (EU) 2024/1689 (EU AI Act)"
    # Structure --------------------------------------------------------------
    container: str               # "Article 10" or "Annex III"
    article: Optional[int] = None
    annex: Optional[str] = None
    paragraph: Optional[str] = None   # "2"
    point: Optional[str] = None       # "b"
    subpoint: Optional[str] = None    # "i"
    heading: Optional[str] = None
    parent_id: Optional[str] = None   # link to the chapeau / paragraph above
    # Content ----------------------------------------------------------------
    text: str = ""
    unit_type: str = OBLIGATION
    defined_term: Optional[str] = None   # set when unit_type == DEFINITION
    # Metadata for filtering + traceability ---------------------------------
    scope_partition: str = HYBRID
    authority: str = "binding"           # binding | guidance | case-law
    tier: int = 1                        # 1 = horizontal AI Act; 2 = domain legal layer
    lang: str = "en"
    related: list = field(default_factory=list)  # ids of linked defs/exceptions

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)

    @staticmethod
    def from_json(line: str) -> "LegalUnit":
        return LegalUnit(**json.loads(line))


def load_units(path: str) -> list[LegalUnit]:
    units = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                units.append(LegalUnit.from_json(line))
    return units


def save_units(units: list[LegalUnit], path: str) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        for u in units:
            fh.write(u.to_json() + "\n")
