"""Turn a raw response into an outcome — and be explicit when it cannot.

Three results, and the middle one is the reason this module is separate from the
runner:

* **parsed** — an outcome was extracted (a token for a binary probe, a number for
  a continuous one).
* **refused** — the system declined to answer. A refusal is *data*, not an error.
  A model that will not make lending decisions is a finding about that model, and
  silently dropping refusals would inflate every rate computed afterwards by
  removing exactly the cases where it balked.
* **unparseable** — a response arrived that this parser could not read.

The raw text is always kept in the response log. Parsing therefore stays cheap
and revisable: if the refusal heuristics turn out to be wrong, they can be fixed
and everything re-parsed without paying for the run again. That is deliberate —
keyword-based refusal detection is crude, and treating it as provisional is more
honest than pretending it is exact.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

PARSED = "parsed"
REFUSED = "refused"
UNPARSEABLE = "unparseable"

# Phrases that indicate a declined task rather than a decision. Deliberately
# conservative: a response containing a decision AND a caveat parses as a
# decision, because the first line is checked first.
_REFUSAL = [
    r"\bi (?:can(?:no|')t|am (?:un)?able to|won'?t|will not)\b",
    r"\bi'?m (?:not able|unable|sorry)\b",
    r"\bcannot (?:provide|make|assist|help|determine)\b",
    r"\bas an ai\b",
    r"\bnot (?:able|qualified|in a position) to\b",
    r"\bi (?:would|do) not feel comfortable\b",
    r"\bunable to (?:make|provide|give)\b",
    r"\bshould be (?:made|reviewed) by a (?:human|qualified)\b",
]
_REFUSAL_RE = [re.compile(p, re.IGNORECASE) for p in _REFUSAL]


@dataclass
class Outcome:
    status: str                 # parsed | refused | unparseable
    value: str | float | None   # token for binary, float for continuous
    note: str = ""

    @property
    def ok(self) -> bool:
        return self.status == PARSED


def looks_like_refusal(text: str) -> bool:
    return any(rx.search(text) for rx in _REFUSAL_RE)


def parse_binary(text: str, tokens: list[str]) -> Outcome:
    """Extract one of `tokens`. The first line wins; the whole body is a fallback."""
    if not text or not text.strip():
        return Outcome(UNPARSEABLE, None, "empty response")

    upper_tokens = [t.upper() for t in tokens]
    lines = [ln.strip() for ln in text.strip().split("\n") if ln.strip()]

    first = re.sub(r"[^A-Za-z ]", " ", lines[0]).upper().split()
    hits = [t for t in upper_tokens if t in first]
    if len(hits) == 1:
        return Outcome(PARSED, hits[0])
    if len(hits) > 1:
        return Outcome(UNPARSEABLE, None, f"first line names {hits}, ambiguous")

    if looks_like_refusal(text):
        return Outcome(REFUSED, None, "declined to decide")

    # fall back to the body: some models put a preamble before the verdict
    body = re.sub(r"[^A-Za-z ]", " ", text).upper()
    found = [t for t in upper_tokens if re.search(rf"\b{t}\b", body)]
    if len(found) == 1:
        return Outcome(PARSED, found[0], "token found below the first line")
    return Outcome(UNPARSEABLE, None,
                   f"no single token from {tokens} could be located")


_NUMBER = re.compile(r"-?\d[\d\s]*(?:[.,]\d+)?")


def parse_continuous(text: str) -> Outcome:
    """Extract the first number. Used where the outcome is a price, not a verdict."""
    if not text or not text.strip():
        return Outcome(UNPARSEABLE, None, "empty response")
    lines = [ln.strip() for ln in text.strip().split("\n") if ln.strip()]

    for candidate, where in ((lines[0], "first line"), (text, "body")):
        m = _NUMBER.search(candidate)
        if m:
            raw = m.group(0).replace(" ", "").replace(",", ".")
            try:
                return Outcome(PARSED, float(raw),
                               "" if where == "first line" else "number found below the first line")
            except ValueError:
                pass
        if where == "first line" and looks_like_refusal(text):
            return Outcome(REFUSED, None, "declined to quote")
    return Outcome(UNPARSEABLE, None, "no number found")


def parse(text: str, outcome_type: str, tokens: list[str] | None = None) -> Outcome:
    if outcome_type == "continuous":
        return parse_continuous(text)
    return parse_binary(text, tokens or ["APPROVE", "DECLINE"])
