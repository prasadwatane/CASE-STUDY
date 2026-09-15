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


def _short_model(m: str) -> str:
    return m.split("/")[-1] if m else "the audited model"


def _md_cell(x: str) -> str:
    return (x or "").replace("|", "\\|").replace("\n", " ")


def _dedupe_notes(entries) -> tuple[dict, list[str]]:
    """Map each distinct note to a footnote number, in first-seen order.

    The jury writes the same caveat onto every finding it applies to, and the
    post-hoc tolerance disclosure is by design attached to each robustness
    entry. Printed inline that is one warning repeated forty times, and a
    warning repeated is a warning skimmed. Printed once, numbered, it is read.
    """
    idx: dict = {}
    order: list[str] = []
    for e in entries:
        for part in (e.note or "").split(" \u00b7 "):
            part = part.strip()
            if part and part not in idx:
                idx[part] = len(order) + 1
                order.append(part)
    return idx, order


def _refs(e, idx: dict) -> str:
    nums = sorted({idx[p.strip()] for p in (e.note or "").split(" \u00b7 ")
                   if p.strip() in idx})
    return " ".join(f"[{n}]" for n in nums)


def _table(rows: list[list[str]], header: list[str]) -> list[str]:
    out = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    out += ["| " + " | ".join(_md_cell(c) for c in r) + " |" for r in rows]
    return out


def render_markdown(ledger, *, domain: str, checklist_signer: str = "",
                    checklist_sha256: str = "", clause_citations: dict | None = None,
                    clause_text: dict | None = None, signed_utc: str = "",
                    first_response_utc: str = "",
                    robustness_margins: tuple[float, float] | None = None,
                    annotation_ceiling: dict | None = None) -> str:
    """Render the whole ledger. Raises Overclaim rather than emitting bad text.

    `robustness_margins` is (pre-registered, revised); when given, every
    Article 15 section carries a verdict table at BOTH tolerances so the
    post-hoc revision is visible on the page and not only in a footnote.

    `annotation_ceiling` is the scored human-human agreement for the judged
    dimension (kappa, ci, n, threshold). When given, the Article 13 section
    states whether the judge can be validated at all, which is the fact that
    decides whether its numbers are findings or inputs.
    """
    cites = clause_citations or {}
    texts = clause_text or {}
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    out: list[str] = []
    w = out.append

    w(f"# Audit findings \u2014 {domain}")
    w("")
    w(f"Generated {now} from an append-only ledger of "
      f"{len(ledger)} admitted findings.")
    if checklist_signer:
        w("")
        w(f"Scored against a checklist signed by **{checklist_signer}** "
          f"(`{checklist_sha256[:16]}\u2026`)"
          + (f", signed {signed_utc[:10]}." if signed_utc else "."))
        if first_response_utc and signed_utc and signed_utc <= first_response_utc:
            w("")
            w("This checklist was frozen **before any model response was "
              "collected**, so every threshold below was fixed in advance of "
              "the result it is applied to.")
        elif first_response_utc and signed_utc:
            w("")
            w(f"**This checklist was signed AFTER responses were collected** "
              f"(first response {first_response_utc[:10]}). At least one "
              "criterion was revised with results already known; the affected "
              "findings carry the disclosure on their own line, and the "
              "pre-registration claim does not extend to them.")
    w("")
    w("## What this report does and does not say")
    w("")
    w("Every statement below concerns a **requirement derived from a clause** \u2014 "
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

    # --- summary: one line per (clause, model) headline verdict --------------
    models = sorted({e.model_id for e in ledger.entries if e.model_id})
    head_rows = []
    for clause in ledger.clauses():
        for e in ledger.for_clause(clause):
            if e.headline_eligible:
                head_rows.append([cites.get(clause, clause), _short_model(e.model_id),
                                  e.verdict, _interval(e), f"{e.n:,}"])
    if head_rows:
        w("## Summary of headline verdicts")
        w("")
        w("Only findings from the pre-registered CORE sample, scored by "
          "deterministic arithmetic or a validated judge, appear here.")
        w("")
        out += _table(head_rows, ["clause", "model", "verdict", "estimate [CI]", "n"])
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
        is_robustness = clause in ("AIA:Art15(1)", "AIA:Art15(4)")
        is_judged = any(e.evidence_type == "judged" for e in entries)

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

        # Article 15: the verdict at both tolerances, on the face of the page.
        if is_robustness and robustness_margins and other:
            orig, revised = robustness_margins
            w(f"**Tolerance revised post hoc.** The signed tolerance was "
              f"{orig:.2f}; it was raised to {revised:.2f} after all models had "
              f"been measured and had failed at {orig:.2f} "
              "(`docs/criteria_amendment_robustness_020.md`). Both verdicts are "
              "shown; the pre-registered one is the one the method promised.")
            w("")
            rows = []
            for e in other:
                if e.ci_low is None or e.ci_high is None:
                    continue
                def _v(tol):
                    if e.ci_high < tol:
                        return "PASS"
                    if e.ci_low > tol:
                        return "FAIL"
                    return "UNDETERMINED"
                rows.append([_short_model(e.model_id), _interval(e), f"{e.n:,}",
                             _v(orig), _v(revised)])
            out += _table(rows, ["model", "flip share [90% CI]", "n",
                                 f"at {orig:.2f} (pre-registered)",
                                 f"at {revised:.2f} (revised)"])
            w("")

        # Article 13: whether the judge can be validated at all.
        if is_judged and annotation_ceiling:
            c = annotation_ceiling
            k = c.get("kappa")
            ci = c.get("ci") or [None, None]
            thr = c.get("threshold", 0.61)
            w("**Human ceiling.** Before a judge can be validated, two humans "
              "following the frozen guideline must agree above chance. ")
            if k is None:
                w(f"The pilot ceiling is undefined (n = {c.get('n', '?')}): "
                  "raters used a single label, so chance agreement is 1.")
            else:
                lo = ci[0] if ci[0] is not None else float("nan")
                hi = ci[1] if ci[1] is not None else float("nan")
                verdict = ("clears" if (ci[0] is not None and ci[0] >= thr)
                           else "does not clear")
                w(f"Pilot ceiling: \u03ba = {k:.2f} [{lo:.2f}, {hi:.2f}] on "
                  f"n = {c.get('n', '?')} double-annotated items ({c.get('raters', 2)} "
                  f"raters); the lower bound {verdict} the {thr:.2f} threshold.")
                if verdict == "does not clear":
                    w("")
                    w("Until a revised guideline lifts the ceiling, the judge's "
                      "shares below are inputs to that study. If the ceiling "
                      "cannot be lifted, the result is that explanation adequacy "
                      "under this criterion is not reliably annotatable \u2014 a "
                      "negative finding about the criterion, reported as such.")
            w("")

        if other:
            w("**Reported, not carrying a claim.**")
            w("")
            reasons = sorted({("the sample was added after seeing data"
                               if e.sample_kind == "adaptive"
                               else "the judge behind it is not yet validated")
                              for e in other})
            w("Excluded from headline claims because " + "; ".join(reasons) + ".")
            w("")
            idx, notes = _dedupe_notes(other)
            rows = [[_short_model(e.model_id), e.estimand,
                     e.stratum or "\u2014", f"{e.n:,}", _interval(e),
                     e.verdict, _refs(e, idx)] for e in other]
            out += _table(rows, ["model", "estimand", "stratum", "n",
                                 "estimate [CI]", "verdict", "notes"])
            w("")
            for i, n in enumerate(notes, start=1):
                w(f"[{i}] {n}")
            if notes:
                w("")

        if controls:
            w("**Instrument checks.** These say whether the method can detect "
              "what it claims to detect. They are never counted toward a "
              "finding about the audited system.")
            w("")
            rows = []
            for e in controls:
                fired = (e.detail or {}).get("fired")
                rows.append([_short_model(e.model_id), e.estimand, f"{e.n:,}",
                             _interval(e),
                             "fired" if fired else ("silent" if fired is False else "\u2014")])
            out += _table(rows, ["model", "control", "n", "estimate [CI]", "status"])
            w("")

    undetermined = [e for e in ledger.entries
                    if e.verdict == "UNDETERMINED" and e.sample_kind == "core"]
    if undetermined:
        w("## Requirements that could not be determined")
        w("")
        w("These are not passes. The evidence was insufficient to place the "
          "interval on one side of the threshold, and that is reported rather "
          "than resolved. Only CORE-sample findings are listed; exploratory "
          "ones appear in their clause section.")
        w("")
        rows = [[", ".join(cites.get(c, c) for c in e.clause_ids),
                 _short_model(e.model_id), e.estimand, _interval(e), f"{e.n:,}"]
                for e in undetermined]
        out += _table(rows, ["clause", "model", "estimand", "estimate [CI]", "n"])
        w("")

    text = "\n".join(out)
    check_language(text)
    return text
