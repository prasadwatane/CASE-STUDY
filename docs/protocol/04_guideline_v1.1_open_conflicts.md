# Guideline v1.1 — conflicts that block freezing

`docs/annotation_guidelines_Art13_v1.1_DRAFT.md` cannot be frozen as it stands.
It contains two rule sets written a day apart (the "Proposed rules" of 14 Sep and
the "Appendix — pass/fail checklists" of 15 Sep) and they give **opposite verdicts
on 6 of the 12 pilot disagreements**. Two raters who each follow the document
faithfully can still disagree, depending on which half they read. That is the
same failure as v1.0, relocated.

This sheet is the agenda for the reconciliation session. It decides nothing; each
row needs a decision from both raters.

## A. The six items the two halves decide differently

| Item | Rules section says | Appendix says | The underlying conflict |
|---|---|---|---|
| IT-13E3317D8F | inadequate (Rule 1: values, no valence) | adequate ("all five hold") | Is `Field: value` enough? |
| IT-06C7AB95B7 | inadequate (Rule 1) | adequate (T1, all five hold) | same |
| IT-B6F742ECEF | inadequate (Rule 1) | adequate (T1, all five hold) | same |
| IT-D7F8314FC1 | adequate (Rule 1: the parenthetical gives direction) | inadequate (T1.3: "exceeds the bank's recommended threshold" is an invented fact) | Is a stated reason valence, or invention? |
| IT-DC911E05FF | adequate (Rule 2: counterfactual states direction) | inadequate (T2.3: invented "standard requirement") | Does an invented policy void a correctly directed counterfactual? |
| IT-6714142770 | adequate (Rule 2) | inadequate (T2.3: invented policy, introduces age) | same |

Two further items get the same verdict from both halves but for different
reasons (IT-2100D1523F: Rule 1 versus T1.1; IT-DC80A1173A: Rule 1 versus T1.2).
They agree here and will diverge on the next similar item. IT-BCFC6F40BD fails
under both for being non-selective, but against different thresholds (decision 3).

## B. The three decisions that resolve all of them

| # | Decision | Option 1 | Option 2 | What it does to the docket |
|---|---|---|---|---|
| 1 | Must a detail **state** its direction? | Yes (Rule 1): `Field: value` fails | No (T1.2/T1.4): naming the field is enough if it is consistent with the decision | Option 1 makes the commonest response format inadequate and moves prevalence sharply towards 50% or below. Option 2 keeps the docket skewed towards `adequate`. |
| 2 | Is an unsupported reason a failure? | Yes (T1.3/T2.3): any threshold or policy not in the prompt fails | No: it counts as valence (Rule 1 worked example) | Under option 1 combined with decision 1 = Yes, a response must give a direction without giving a reason the prompt does not contain. Check that any real response can pass both. |
| 3 | How many fields make a counterfactual non-selective? | More than five (Rule 3) | More than roughly half the fields (T2.4) | Pick one number. "Roughly" is not applicable by two people. |

A caution on decision 1 + 2 together: if direction must be stated **and** every
stated reason must come from the prompt, the passing set may be nearly empty. Run
both raters over ten round-1 responses under the candidate rule set before
freezing, and look at the pass rate.

## C. Other inconsistencies to settle in the same session

| # | Issue | Where | Needs |
|---|---|---|---|
| 4 | Round 2 on **fresh** items or the **same** 30? | Rules section step 4 says fresh items ("re-rating would measure memory"); Appendix procedure and exposé rev2 say the same 30 | One answer. Fresh items is the defensible one. `pilot3` (30 rows, no overlap with round 1) already exists for it. |
| 5 | Gate statistic | Appendix: lower bound of Fleiss κ or every pairwise κ; amendment and code: AC1 primary; exposé rev2 Table 1: κ | Same decision as [OPEN 1] in the evaluation protocol. |
| 6 | Main-study overlap | Appendix: "120-item overlap"; exposé rev2: all 300 double-rated | 300, per rev2; the appendix line is stale. |
| 7 | `cannot judge` | Guideline keeps it (Rule 4); the exported `pilot2`/`pilot3` sheets allow only `adequate` / `inadequate` | Either add the label to the sheets or remove Rule 4. |
| 8 | Scoring command | Appendix names `score_pilot.py … pilot_round2`; no such directory exists | Use the directory of the re-exported packet. |
| 9 | Stale guideline hash | `pilot2` and `pilot3` keys record the v1.0 guideline hash (`2d111b5e…`) | Re-export the round-2 packet after v1.1 is frozen so the key carries the v1.1 hash. Unfilled sheets, so nothing is lost. |
| 10 | Amendment date cannot be evidenced | The AC1 amendment says "filed 13 September, before any annotation label has been recorded… dated, and committed". The amendment file is not tracked in this repository. The code change that makes AC1 primary was committed on 14 Sep at 16:40; rater A's and B's sheets were last written on 14 Sep at 14:28 and 14:46. | Commit the amendment file. If an earlier timestamped copy exists (email to the supervisor, server commit), cite it. If not, reword the claim: the amendment still stands on its written reasoning (the risk was noted before data), but "committed before any label" is not shown by this history. |

## D. After the session

1. Merge the two halves into **one** rule set; delete the losing rules rather than
   leaving them as commentary.
2. Rewrite the worked-examples table so every round-1 item has a single verdict.
3. Bump to v1.1, hash, record the hash in `PREREGISTRATION.md`.
4. Retire all v1.0 labels from evaluation; keep them as the pre-revision baseline.
5. Re-export the round-2 packet and run it (see `03_annotation_protocol.md`).
