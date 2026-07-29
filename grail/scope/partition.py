"""Scope partition tagging: behavioral | hybrid | procedural.

This is a HEURISTIC first pass only. The final partition is signed by a human
at the notary gate (skill non-negotiable). We never derive a requirement from a
procedural clause; procedural clauses are still stored and retrievable as
context, but flagged out of the probeable set.
"""
from __future__ import annotations
import re

from grail.ingest.schema import BEHAVIORAL, HYBRID, PROCEDURAL

_BEHAVIORAL = re.compile(
    r"\b(accura\w+|robust\w+|resilien\w+|bias\w*|discriminat\w+|performanc\w+|"
    r"error\w*|cybersecurity|attack\w*|output\w*|result\w*|detect\w+|"
    r"consisten\w+|reliab\w+)\b", re.I)

_PROCEDURAL = re.compile(
    r"\b(document\w*|record\w*|log\w*|register\w*|keep\b|retain\w*|report to|"
    r"quality management|conformity assessment|technical documentation|"
    r"instructions for use|traceab\w+|draw up|maintain\w*)\b", re.I)

_HYBRID = re.compile(
    r"\b(transparen\w+|inform\w+|interpret\w+|explain\w+|understand\w+|"
    r"enable\w*|communicat\w+)\b", re.I)


def infer_partition(text: str) -> str:
    """Cheap lexical vote. Ties resolve toward hybrid (safer: stays probeable)."""
    b = len(_BEHAVIORAL.findall(text))
    p = len(_PROCEDURAL.findall(text))
    h = len(_HYBRID.findall(text))
    # Procedural only wins if it clearly dominates and there is no behavioral pull.
    if p > b and p > h and b == 0:
        return PROCEDURAL
    if b >= h and b > 0:
        return BEHAVIORAL
    return HYBRID
