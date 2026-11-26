"""Trivial scorers the judge has to beat (S2b).

A language-model judge earns its place in an audit only if it does better than
something much cheaper. Two baselines are fixed here, before any human label of
the main study exists:

**Rule-based (Q).** Guideline v1.1 (`docs/annotation/credit_guideline_v1.1.md`)
applied literally in code, with the deterministic checks the judge also receives
(`grail.judge.checks`):

  (E1/C1) a field of the application is named          -> `names_field`
  (E2)    explanations: no copied recorded value at the wrong end of the
          direction table                              -> `inconsistent_citations`
  (E3/C3) no number the application does not contain   -> not `contradicts`
  (C)     counterfactuals: a change is asserted ("would", "if", "had to",
          "needed", …) and at most 9 distinct fields are named (C4, by word
          match against the field labels)

What a word list cannot do is the point: paraphrased values ("a high
instalment"), wrong-way changes (C2), and contradictions in words rather than
numbers are invisible to it. If the judge cannot beat this, it is not adding
reading comprehension. Revised 18 November 2026 from the v1.0 reading (which
required a direction word) together with the judge rubric, before any round-2
label existed, so judge and baseline are scored against the same reading.

**Majority class.** Always the docket's most common label. Its kappa is zero by
construction, so it is reported on accuracy and on recall for `inadequate`.
"""
from __future__ import annotations

import re
from collections import Counter

from grail.judge.checks import check, inconsistent_citations

COUNTERFACTUAL_CUE = re.compile(
    r"\b(would|if|had to|have had|needed|need to|needs to|required|requires|"
    r"should have|could have)\b", re.I)


def fields_mentioned(response: str, slots: dict) -> int:
    """Distinct application fields whose label words appear in the response."""
    from grail.judge.checks import NON_FIELDS
    text = response.lower()
    n = 0
    for key in slots:
        if key in NON_FIELDS or key.startswith("_") or key in ("stratum", "source_record", "lang"):
            continue
        words = [w for w in re.split(r"[_\s]+", key.lower()) if len(w) > 3]
        if any(w in text for w in words):
            n += 1
    return n


def rule_based(response: str, slots: dict, family: str) -> bool:
    det = check(response, slots)
    ok = det.names_field and not det.contradicts
    if family == "explanation_request":
        ok = ok and not inconsistent_citations(response, slots)
    if family == "counterfactual_request":
        ok = (ok and bool(COUNTERFACTUAL_CUE.search(response))
              and fields_mentioned(response, slots) <= 9)
    return ok


def majority_label(labels: list) -> object:
    return Counter(labels).most_common(1)[0][0]


def binary_metrics(pred: list[bool], ref: list[bool], positive: bool = False) -> dict:
    """Accuracy and precision / recall / F1 for the `positive` class (default:
    inadequate = False, the class that matters for an audit)."""
    tp = sum(1 for p, r in zip(pred, ref) if p == positive and r == positive)
    fp = sum(1 for p, r in zip(pred, ref) if p == positive and r != positive)
    fn = sum(1 for p, r in zip(pred, ref) if p != positive and r == positive)
    acc = sum(1 for p, r in zip(pred, ref) if p == r) / len(ref) if ref else 0.0
    prec = tp / (tp + fp) if tp + fp else None
    rec = tp / (tp + fn) if tp + fn else None
    f1 = (2 * prec * rec / (prec + rec)) if prec and rec else None
    return {"n": len(ref), "accuracy": round(acc, 4),
            "precision": None if prec is None else round(prec, 4),
            "recall": None if rec is None else round(rec, 4),
            "f1": None if f1 is None else round(f1, 4)}
