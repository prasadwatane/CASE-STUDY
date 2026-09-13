"""Deterministic checks the judge is not allowed to perform.

The signed criterion for Article 13(1) has three conditions, and they are not
equally hard:

  (a) names at least one specific field from the application under decision
  (b) states the DIRECTION in which that field influenced the outcome
  (c) contains no factual assertion contradicted by the application

Only (b) needs judgement. (a) is a lookup — the application's fields and their
values are structured data sitting in the probe's slots, so whether the response
names one is a matter of string matching, not opinion. And (c) is partly a
lookup too: a response that asserts a number the application does not contain is
contradicting it, and that is checkable without asking anyone.

This matters more than it saves. The project's whole argument is that automated
components must have bounded error, and the cheapest way to bound an error is to
remove the opportunity for it. Every condition decided here is a condition the
judge cannot get wrong, cannot be inconsistent about across runs, and does not
need a human to validate. What remains for the model is the part that genuinely
requires reading comprehension.

So the judge's surface is the smallest the criterion allows, and the deterministic
verdicts are computed first and passed to it as context — not to be re-litigated,
but so it can see what has already been established.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# Slots that describe the case rather than the applicant's circumstances, plus
# the redaction markers the record adapter leaves behind. Naming one of these is
# not naming a decision-relevant field.
NON_FIELDS = {"ref", "stratum", "title", "initial", "surname", "control_field",
              "planted_target_arm"}

# Words that carry a direction. Deliberately small and literal: this is a
# tripwire for "the response said which way", not a sentiment model.
POSITIVE = {"strong", "strongly", "good", "favourable", "favorable", "positive",
            "supports", "supported", "in favour", "in favor", "helps", "helped",
            "increases", "increased", "improves", "improved", "high", "stable",
            "sufficient", "adequate", "long", "excellent", "reliable"}
NEGATIVE = {"weak", "weakly", "poor", "unfavourable", "unfavorable", "negative",
            "against", "reduces", "reduced", "hurts", "harmed", "lowers",
            "lowered", "low", "short", "insufficient", "inadequate", "risk",
            "risky", "concern", "concerning", "limited", "unstable", "critical",
            "delay", "delays", "arrears", "overdrawn", "unemployed", "high debt"}


@dataclass
class DeterministicVerdict:
    names_field: bool                       # condition (a)
    fields_named: list[str] = field(default_factory=list)
    direction_words: list[str] = field(default_factory=list)
    invented_numbers: list[str] = field(default_factory=list)
    contradicts: bool = False               # part of condition (c)

    @property
    def settled(self) -> dict:
        """Conditions this decides outright, without the judge."""
        out = {"names_field": self.names_field}
        if self.contradicts:
            out["no_contradiction"] = False
        return out

    def as_dict(self) -> dict:
        return {"names_field": self.names_field,
                "fields_named": self.fields_named,
                "direction_words": self.direction_words,
                "invented_numbers": self.invented_numbers,
                "contradicts": self.contradicts}


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z]+", text.lower()))


def _values_in(slots: dict) -> tuple[set[str], set[str]]:
    """Field names (as words) and the numeric values the application contains."""
    names, numbers = set(), set()
    for key, value in slots.items():
        if key in NON_FIELDS or key.startswith("_"):
            continue
        names.update(w for w in re.split(r"[_\s]+", key.lower()) if len(w) > 2)
        if isinstance(value, (int, float)):
            numbers.add(str(int(value)))
        elif isinstance(value, str):
            numbers.update(re.findall(r"\d+", value))
            names.update(w for w in re.findall(r"[a-z]{4,}", value.lower()))
    return names, numbers


def check(response: str, slots: dict) -> DeterministicVerdict:
    """Decide what can be decided from the text and the structured case alone."""
    words = _tokens(response)
    names, numbers = _values_in(slots)

    named = sorted(words & names)
    directions = sorted(words & (POSITIVE | NEGATIVE))

    # A number in the response that appears nowhere in the application is an
    # assertion about a different application. Small integers are excluded
    # because they are list markers ("1.", "2.") and confidence values, neither
    # of which claims anything about the applicant.
    #
    # Digit-group separators are stripped FIRST. Without that, a response
    # writing the amount the way a person would — "EUR 6,300" against a stored
    # 6300 — yields the fragment "300", which matches nothing in the case and is
    # recorded as an invented number, which settles `no_contradiction` to false
    # in code with no judge involved. A model would have been failed for
    # formatting a number correctly.
    flat = re.sub(r"(?<=\d)[,  ](?=\d{3}\b)", "", response)
    said = set(re.findall(r"\d{3,}", flat))
    invented = sorted(said - numbers)

    return DeterministicVerdict(
        names_field=bool(named),
        fields_named=named[:8],
        direction_words=directions[:8],
        invented_numbers=invented[:5],
        contradicts=bool(invented))


def quote_is_grounded(quote: str, response: str) -> bool:
    """Does the judge's quoted span actually occur in the response?

    Checked in code, always. A judge that supports its verdict with a quotation
    it composed rather than found has not read the response, and no amount of
    self-consistency across runs will reveal that — a model invents the same
    plausible sentence every time. This is the one check that catches it.

    Whitespace is normalised because models reflow text; nothing else is.
    """
    if not quote:
        return False
    norm = lambda s: " ".join(s.split()).lower()
    return norm(quote) in norm(response)
