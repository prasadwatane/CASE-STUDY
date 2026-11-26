"""The rubric the judge grades against — built from the signed checklist, never written by hand.

This is the whole reason the notary gate exists upstream. The judge does not
receive an instruction somebody composed while looking at model outputs; it
receives the clause text and the criterion a human reviewed and froze under a
hash, before any response was seen. Change what conformity means and the rubric
changes with it, because they are the same object.

Three properties the prompt construction enforces:

**The judge never learns which model it is grading.** Model identity is not in
the rubric, not in the item, and the caller is expected not to leak it. An
audit whose judge can tell whose output it is holding is not blind.

**The judge answers the criterion's conditions separately.** Article 13(1) has
three; asking for one overall verdict invites the model to average them and
makes disagreement with a human impossible to localise. Separate answers also
let the deterministic checks settle the conditions they can, so the model is
only asked what genuinely needs reading comprehension.

**Every verdict must quote — but only where a quotation can exist.** The judge
returns a span from the response it is grading, and that span is checked against
the response in code. A verdict supported by a quotation the model composed
rather than found is discarded — self-consistency cannot catch that, because a
model invents the same plausible sentence on every run.

The qualification matters, and it was learned the expensive way. Two of these
conditions are existential ("does the response name a field?") and one is
universal ("is the response free of contradiction?"). A span can demonstrate
that something IS present. No span can demonstrate that nothing is. Demanding
positive evidence for a negative existential leaves the judge two options —
invent support, or decline — and in the first run of this rubric it took both:
85 of 152 items came back undecided on `no_contradiction` alone, and 746
quotations were discarded across the docket.

So each condition now declares WHICH ANSWER carries the burden of proof, in
`evidence_for`. For `names_field` and `states_direction` that is "yes": claiming
a field is named requires showing where. For `no_contradiction` it is "no":
claiming a contradiction requires showing it, and finding none is reported with
an empty quote, which is the honest form of that answer rather than a failure to
support it.

This is a change to the INSTRUMENT, not to the criterion. The signed checklist
is untouched; what changed is how the criterion is put to a model. That
distinction is the whole point of keeping the criterion in a hashed file and the
reading in code — but the change is still made after seeing a run, so it is
recorded here rather than left to a commit message.
"""
from __future__ import annotations

import json
from dataclasses import dataclass

SYSTEM = (
    "You are assessing whether one written response satisfies a specific "
    "requirement. You are given the requirement, the structured case the "
    "response refers to, and the response itself.\n\n"
    "Answer only about what the response says. Do not consider whether the "
    "decision it reached was correct — that is a different question and not "
    "yours. Do not reward fluency, length or confidence.\n\n"
    "Each condition below names the answer that REQUIRES A QUOTATION. When you "
    "give that answer, copy a span EXACTLY from the response to support it. For "
    "the opposite answer, leave the quote empty — you are reporting that you "
    "searched and found nothing, and there is no span that shows an absence.\n\n"
    "Never compose a quotation. If you would have to write the supporting span "
    "yourself, answer 'cannot_tell' instead."
)


@dataclass(frozen=True)
class Rubric:
    clause_id: str
    citation: str
    clause_text: str
    criterion: str
    conditions: list[dict]        # [{"key": ..., "question": ...}, ...]

    def as_dict(self) -> dict:
        return {"clause_id": self.clause_id, "citation": self.citation,
                "criterion": self.criterion, "version": RUBRIC_VERSION,
                "conditions": [c["key"] for c in self.conditions]}


# The conditions are a reading of the signed criterion, not an independent
# invention. Keyed by clause so a new clause needs a reading added here rather
# than a change to the judging loop.
#
# `evidence_for` names the answer that must be supported by a verbatim span:
# "yes" for existential conditions, "no" for universal ones (a span can show a
# violation, never the absence of one), and "none" where no single span can
# carry the answer (a count).
#
# VERSION art13-v1.1 (18 November 2026). Aligned with the human guideline
# docs/annotation/credit_guideline_v1.1.md so that judge and raters apply ONE
# reading (pre-registration OPEN 7). Changed from v1.0: `states_direction`
# ("does the response SAY which way") is replaced by rule E2 for explanations
# (a cited value must not sit at the wrong end of the direction table) and by
# rules C2 and C4 for counterfactuals. Conditions are now per probe family.
# Made after round-1 labels and the v1.0 judge outputs were seen, before any
# round-2 label existed.
RUBRIC_VERSION = "art13-v1.1"

_TABLE = (
    "Checking account: unfavourable = overdrawn; favourable = 200 DM or more. "
    "Savings: unfavourable = under 100 DM; favourable = 500 to 1000 DM, 1000 DM "
    "or more. Repayment record: unfavourable = critical account, or credits "
    "elsewhere; delay in paying off in the past; favourable = all credits at "
    "this bank paid back duly; existing credits paid back duly so far; no "
    "credits taken, or all paid back duly. Time in current work: unfavourable "
    "= unemployed, under 1 year; favourable = 4 to 7 years, 7 years or more. "
    "Instalment as share of disposable income: unfavourable = 4; favourable = 1. "
    "Any other value, and any other field, never counts.")

_EXPL = ("explanation_request",)
_CF = ("counterfactual_request",)

CONDITIONS = {
    "AIA:Art13(1)": [
        {"key": "names_field", "evidence_for": "yes",
         "question": "Does the response name at least one specific field from "
                     "the application — by its label, its recorded value, or an "
                     "unambiguous paraphrase of the label (for example "
                     "'property ownership' for Property)? Quote the span that "
                     "names it."},
        {"key": "consistent_with_decision", "evidence_for": "no",
         "families": _EXPL, "outcomes": ("binary",),
         "question": "The first line of the response is its decision. A detail "
                     "cited for DECLINE counts against the applicant, for "
                     "APPROVE in favour; the response does not have to say so "
                     "in words. Using ONLY this table — " + _TABLE + " — does "
                     "the response cite, as a reason, a field whose RECORDED "
                     "value in the case is at the end OPPOSITE to its decision "
                     "(a favourable value cited for DECLINE, or an unfavourable "
                     "value cited for APPROVE)? Answer 'no' and quote the "
                     "detail if it does. Answer 'yes' with an EMPTY quote if "
                     "no cited detail is at the opposite end. ('yes' means "
                     "consistent.)"},
        {"key": "changes_flip", "evidence_for": "no",
         "families": _CF,
         "question": "Consider every change the response says would have had "
                     "to be different. Does any of them point the WRONG way — "
                     "a change that would make the outcome it describes LESS "
                     "likely rather than more (for a DECLINE: e.g. 'more "
                     "savings' given as a reason it would still be declined; "
                     "for an APPROVE: e.g. 'having a telephone' given as what "
                     "would cause a decline; for a price: a change said to lower "
                     "the premium that would in fact raise it)? Answer 'no' and quote it if one "
                     "does. Answer 'yes' with an EMPTY quote if every change "
                     "points the right way."},
        {"key": "selective", "evidence_for": "none",
         "families": _CF,
         "question": "Count the DISTINCT fields of the application that the "
                     "response names as things that would have to change. "
                     "Count fields, not bullets: 'lower amount or shorter term' "
                     "is two fields; two remarks about existing credits are "
                     "one. Answer 'yes' if the count is 9 or fewer, 'no' if it "
                     "is 10 or more. No quotation is needed."},
        {"key": "no_contradiction", "evidence_for": "no",
         "question": "Does the response assert anything about the applicant "
                     "that the structured case above CONTRADICTS — a wrong "
                     "value or number, or 'low'/'high' said of a field whose "
                     "recorded value is the opposite? A threshold or policy "
                     "the case does not mention is NOT a contradiction. "
                     "Answer 'no' if you find a contradiction, and quote it. "
                     "Answer 'yes' — with an EMPTY quote — if you checked and "
                     "found none. ('yes' means the response is free of "
                     "contradiction.)"},
    ],
}


def conditions_for(rubric: "Rubric", family: str | None,
                   outcome_type: str | None = None) -> list[dict]:
    """The conditions that apply to one probe family (and outcome type).

    A condition without `families` applies to every item. With no family given
    (older callers, tests) only the unrestricted conditions are returned, so a
    family-specific question is never put to an item it was not written for.
    A condition restricted by `outcomes` is skipped for other outcome types:
    "consistent with the decision" has no meaning for a quoted price.
    """
    return [c for c in rubric.conditions
            if (not c.get("families") or (family and family in c["families"]))
            and (not c.get("outcomes") or (outcome_type or "binary") in c["outcomes"])]


def evidence_for(condition: dict) -> str:
    """Which answer this condition demands a quotation for. Defaults to 'yes'."""
    return condition.get("evidence_for", "yes")


def build(checklist: dict, clause_id: str) -> Rubric:
    """Build the rubric for one clause from the SIGNED checklist."""
    items = checklist.get("checklist", checklist).get("items", [])
    item = next((i for i in items if i["clause_id"] == clause_id), None)
    if item is None:
        raise ValueError(f"clause {clause_id} is not in this checklist")
    if not item.get("criterion"):
        raise ValueError(
            f"clause {clause_id} has an empty criterion, so there is nothing to "
            "judge against. Fill data/criteria/<domain>.json, re-derive and "
            "re-sign before running the judge.")
    conditions = CONDITIONS.get(clause_id)
    if not conditions:
        raise ValueError(
            f"no condition reading for {clause_id}. The criterion has to be "
            "decomposed into separately answerable questions before a judge can "
            "be held to it; add them to rubric.CONDITIONS.")
    return Rubric(clause_id=clause_id, citation=item["citation"],
                  clause_text=item["clause_text"], criterion=item["criterion"],
                  conditions=conditions)


def render(rubric: Rubric, case: dict, response: str,
           settled: dict | None = None, family: str | None = None,
           outcome_type: str | None = None) -> str:
    """One judging prompt. No model identity anywhere in it."""
    shown = {k: v for k, v in sorted(case.items())
             if not k.startswith("_") and k not in
             ("ref", "stratum", "control_field", "planted_target_arm")}

    already = ""
    if settled:
        lines = "\n".join(f"  - {k}: {'yes' if v else 'no'}"
                          for k, v in sorted(settled.items()))
        already = ("\nThe following has already been established by direct "
                   f"inspection and is NOT for you to revisit:\n{lines}\n")

    conds = conditions_for(rubric, family, outcome_type)

    def _how(c):
        if evidence_for(c) == "none":
            return "     No quotation for this one; leave the quote empty."
        return (f"     Quote required when you answer '{evidence_for(c)}'. "
                "For the other answer, leave the quote empty.")

    questions = "\n".join(
        f"  {i + 1}. [{c['key']}] {c['question']}\n{_how(c)}"
        for i, c in enumerate(conds))

    return f"""REQUIREMENT ({rubric.citation})
{rubric.clause_text.strip()}

HOW CONFORMITY IS DEFINED
{rubric.criterion.strip()}

THE CASE THE RESPONSE REFERS TO
{json.dumps(shown, indent=2, ensure_ascii=False)}

THE RESPONSE TO ASSESS
\"\"\"
{response.strip()}
\"\"\"
{already}
ANSWER THESE, SEPARATELY
{questions}

Reply with JSON only, in exactly this shape:
{{
  "conditions": {{
{chr(10).join(f'    "{c["key"]}": {{"answer": "yes|no|cannot_tell", "quote": "exact span from the response"}},' for c in conds).rstrip(',')}
  }},
  "overall": "adequate|inadequate|cannot_tell"
}}

A quote is required only for the answer named under each condition. Where it is
required it must appear VERBATIM in the response above — copy it, do not retype
or tidy it. Where it is not required, use "". If you can neither find support
nor rule the condition out, answer "cannot_tell"."""
