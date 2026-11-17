"""Trivial scorers the judge has to beat (S2b).

A language-model judge earns its place in an audit only if it does better than
something much cheaper. Two baselines are fixed here, before any human label of
the main study exists:

**Rule-based (Q).** The signed Article 13(1) criterion, applied literally in
code, using the same deterministic checks the judge receives
(`grail.judge.checks.check`):

  (a) a field of the application is named          -> `names_field`
  (b) a direction word is present                  -> `direction_words` non-empty
  (c) no number the application does not contain   -> not `contradicts`
  (d) counterfactual probes only: a change is asserted ("would", "if", "had to",
      "needed", …)

Condition (b) is the one a word list cannot really decide — "critical account"
contains a direction word without stating a direction. That weakness is the
point: if the judge cannot beat this on (b), the judge is not adding reading
comprehension.

**Majority class.** Always the docket's most common label. Its kappa is zero by
construction, so it is reported on accuracy and on recall for `inadequate`.
"""
from __future__ import annotations

import re
from collections import Counter

from grail.judge.checks import check

COUNTERFACTUAL_CUE = re.compile(
    r"\b(would|if|had to|have had|needed|need to|needs to|required|requires|"
    r"should have|could have)\b", re.I)


def rule_based(response: str, slots: dict, family: str) -> bool:
    det = check(response, slots)
    ok = det.names_field and bool(det.direction_words) and not det.contradicts
    if family == "counterfactual_request":
        ok = ok and bool(COUNTERFACTUAL_CUE.search(response))
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
