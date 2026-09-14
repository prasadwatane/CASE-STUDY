"""Render the ledger as a report that cannot overclaim.

The sentence this module exists to prevent is *"the model complies with Article
10(2)(f)."* A behavioural audit cannot establish that. Compliance is a legal
determination about a provider's whole obligation — documentation, risk
management, human oversight, post-market monitoring — made by a notified body or
a court. What this pipeline establishes is narrower and worth stating precisely:
a model's observable behaviour did or did not meet **a requirement that a named
human derived from a named clause and froze under a hash before any response was
seen.**

So every claim is rendered in one shape:

    conforms to requirement R, derived from Article 10(2)(f)

and never

    complies with Article 10(2)(f)

The distance between those two sentences is the honest scope of the method, and
it is enforced in code rather than left to whoever is writing at the time.
`check_language` runs over the rendered text and raises; it is called before the
report is written, so an overclaiming report cannot be produced by accident.

Three further rules, each of which exists because the natural way to write the
sentence is wrong:

**UNDETERMINED survives to the page.** A three-verdict criterion that gets
rendered as a two-way pass/fail has thrown away the finding that the evidence
was insufficient — which is frequently the most useful thing an audit learns and
always the easiest to lose. It is reported in its own words, never rounded
toward either side.

**Judged evidence is marked as judged, every time it appears.** A share produced
by a language model reads exactly like a share produced by arithmetic once it is
in a table. Until the judge behind it has been measured against the human
ceiling, the number is an input to a validation study, and the report says so on
the line where the number appears rather than in a methods section the reader
may not reach.

**Controls are shown but never counted.** Instrument checks tell you whether the
method can detect what it claims to detect. Letting them into a headline would
be reporting the thermometer as the temperature.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

# The phrasings a verdict is allowed to take. Note that none of them says
# "complies", and that UNDETERMINED gets a sentence of its own rather than a
# hedge attached to a pass or a fail.
VERDICT_PHRASING = {
    "PASS": "conforms to",
    "FAIL": "does not conform to",
    "UNDETERMINED": "could not be determined against",
    "PARTIAL": "partially assessed against",
    "NOT_ASSESSED": "was not assessed against",
}

# Phrases that claim more than a behavioural audit can support. Matched
# case-insensitively on word boundaries.
FORBIDDEN = [
    (r"\bcompl(?:y|ies|ied|iant|iance)\b",
     "compliance is a legal determination about a provider's whole obligation, "
     "not a property of observed behaviour. Say 'conforms to requirement R, "
     "derived from <clause>' instead."),
    (r"\b(?:is|are)\s+(?:un)?biased\b",
     "'biased' is a conclusion about a system; what was measured is a "
     "difference in outcome under a single-token swap. Report the estimand."),
    (r"\b(?:certif|accredit)\w*\b",
     "nothing here certifies anything. Certification is a conformity "
     "assessment procedure with a legal meaning."),
    (r"\bproves?\b",
     "an interval and a p-value are evidence, not proof. Say what was measured "
     "and how strongly."),
    (r"\bsafe\b",
     "safety is not among the properties this pipeline measures."),
]


class Overclaim(ValueError):
    """Raised when rendered text says more than the method can support."""


def check_language(text: str) -> None:
    """Refuse text that overclaims. Raises Overclaim with the offending line.

    Run over the whole report before it is written. The point is not to police
    vocabulary — it is that these particular words each name something the
    method does not do, and a reader is entitled to assume a word means what it
    means.
    """
    for i, line in enumerate(text.splitlines(), start=1):
        # Quoted clause text is the Act's own words and is not the audit
        # speaking; it may legitimately contain 'compliance'.
        if line.lstrip().startswith(">"):
            continue
        for pattern, why in FORBIDDEN:
            m = re.search(pattern, line, re.I)
            if m:
                raise Overclaim(
                    f"line {i} says {m.group(0)!r}: {why}\n  {line.strip()}")


def claim_line(entry, citation: str = "") -> str:
    """The one sentence an entry is allowed to make about an obligation."""
    where = citation or ", ".join(entry.clause_ids)
    phrase = VERDICT_PHRASING[entry.verdict]
    subject = entry.model_id or "the audited model"
    return (f"{subject} {phrase} the requirement derived from {where}")


def _interval(e) -> str:
    if e.estimate is None:
        return "—"
    if e.ci_low is None or e.ci_high is None:
        return f"{e.estimate:.4g}"
    return f"{e.estimate:.4g} [{e.ci_low:.4g}, {e.ci_high:.4g}]"


def _evidence_note(e) -> str:
    if e.evidence_type == "deterministic":
        return "arithmetic over the response log; no model consulted"
    if e.evidence_type == "human":
        return "human annotation"
    if not e.judge_validated:
        return (f"judged by {e.judge_id} — **judge not yet validated against "
                "the human ceiling; this is an input to that study, not a "
                "finding**")
    return f"judged by {e.judge_id}, validated against the human ceiling"


def render_markdown(ledger, *, domain: str, checklist_signer: str = "",
                    checklist_sha256: str = "", clause_citations: dict | None = None,
                    clause_text: dict | None = None) -> str:
    """Render the whole ledger. Raises Overclaim rather than emitting bad text."""
    cites = clause_citations or {}
    texts = clause_text or {}
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    out: list[str] = []
    w = out.append

    w(f"# Audit findings — {domain}")
    w("")
    w(f"Generated {now} from an append-only ledger of "
      f"{len(ledger)} admitted findings.")
    if checklist_signer:
        w("")
        w(f"Scored against a checklist signed by **{checklist_signer}** "
          f"(`{checklist_sha256[:16]}…`) and frozen before any model response "
          "was collected.")
    w("")
    w("## What this report does and does not say")
    w("")
    w("Every statement below concerns a **requirement derived from a clause** — "
      "a measurement, a threshold and a decision rule, written by a named person "
      "and hashed before any result was known. It does not state whether any "
      "system meets its legal obligations. That determination rests on evidence "
      "a behavioural audit cannot observe: technical documentation, risk "
      "management, human oversight, post-market monitoring. The distance "
      "between the two is deliberate and is the honest scope of this method.")
    w("")

    ok, why = ledger.verify()
    w(f"**Ledger integrity:** {why}." if ok
      else f"**LEDGER INTEGRITY FAILURE:** {why}")
    w("")

    for clause in ledger.clauses():
        entries = ledger.for_clause(clause)
        w(f"## {cites.get(clause, clause)}")
        w("")
        if texts.get(clause):
            for line in texts[clause].strip().splitlines():
                w(f"> {line.strip()}")
            w("")

        headline = [e for e in entries if e.headline_eligible]
        controls = [e for e in entries if e.sample_kind == "control"]
        other = [e for e in entries
                 if e not in headline and e.sample_kind != "control"]

        if headline:
            for e in headline:
                w(f"**{claim_line(e, cites.get(clause, clause))}.**")
                w("")
                w(f"- Measured: {e.estimand}")
                w(f"- Estimate: {_interval(e)}"
                  + (f", p = {e.p_value:.3g}" if e.p_value is not None else ""))
                w(f"- n = {e.n:,}" + (f", stratum '{e.stratum}'" if e.stratum else ""))
                w(f"- Method: {e.method}")
                w(f"- Evidence: {_evidence_note(e)}")
                if e.note:
                    w(f"- Note: {e.note}")
                w("")
        else:
            w("_No finding on this clause is eligible to carry a claim._")
            w("")

        if other:
            w("**Reported, not carrying a claim.**")
            w("")
            for e in other:
                why_not = ("the sample was added after seeing data"
                           if e.sample_kind == "adaptive"
                           else "the judge behind it is not yet validated")
                w(f"- {e.estimand}: {_interval(e)} (n = {e.n:,}) — "
                  f"{e.verdict}; excluded from headline claims because "
                  f"{why_not}.")
                # A finding's note reaches the page even when the finding
                # carries no claim. Provenance disclosures live in notes — a
                # post-hoc threshold revision, a sample below the floor at which
                # the test can reject — and suppressing them for non-headline
                # findings would hide exactly the entries most in need of the
                # caveat.
                if e.note:
                    w(f"  - {e.note}")
            w("")

        if controls:
            w("**Instrument checks.** These say whether the method can detect "
              "what it claims to detect. They are never counted toward a "
              "finding about the audited system.")
            w("")
            for e in controls:
                w(f"- {e.estimand}: {_interval(e)} (n = {e.n:,}) — {e.verdict}")
            w("")

    undetermined = [e for e in ledger.entries if e.verdict == "UNDETERMINED"]
    if undetermined:
        w("## Requirements that could not be determined")
        w("")
        w("These are not passes. The evidence was insufficient to place the "
          "interval on one side of the threshold, and that is reported rather "
          "than resolved.")
        w("")
        for e in undetermined:
            w(f"- {', '.join(e.clause_ids)} — {e.estimand}: {_interval(e)} "
              f"(n = {e.n:,})")
        w("")

    text = "\n".join(out)
    check_language(text)
    return text
