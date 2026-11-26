# Why the round-1 annotation study failed (Fleiss κ = 0.07)

**25 November 2026.** Re-analysis of the case-study pilot (`data/processed/annotation/credit_round1/`,
four raters A–D, 30 credit explanations, guideline v1.0). Recomputed from the
rater sheets; numbers match `agreement.md`.

## 1. The numbers

| Quantity | Value |
|---|---|
| Items, raters | 30 items, 4 raters, 120 labels |
| Labels used | adequate 93 (77.5%), inadequate 22 (18.3%), cannot judge 5 (4.2%) |
| Mean observed agreement P̄ | 0.661 |
| Chance agreement Pe (Fleiss) | 0.636 |
| **Fleiss κ** | **0.069** |
| Gwet's AC1 on the same labels | 0.586 |
| Binary items only (25 items without any "cannot judge") | κ = 0.051, AC1 = 0.603 |
| By criterion | "decisive details and a confidence value" (21 items): κ = 0.13; "what would have to change" (9 items): κ = **−0.17** |
| Pairwise raw agreement | A–C 0.80, A–D 0.70, C–D 0.70, A–B 0.60, B–C 0.60, B–D 0.57 |
| Unanimous items | 11 of 30, **all of them "adequate"**; no item was unanimously "inadequate" |
| Most common disagreement | 12 items: three raters "adequate", one "inadequate" |
| Notes written | 3 (all by rater A); raters B, C, D wrote none |

## 2. What the numbers say

1. **Low κ is mostly a prevalence effect, not random labelling.** Raters agreed on
   two items in three (P̄ = 0.66). Because 77.5% of all labels were "adequate",
   two raters who label at those rates agree 64% of the time by chance alone, so
   κ = (0.661 − 0.636)/(1 − 0.636) = 0.07. On the same labels AC1, which
   corrects for chance differently, is 0.59. This is the known κ paradox
   (Feinstein & Cicchetti 1990; Gwet 2008).
2. **But the disagreement is real, and it is about failing.** Every unanimous
   item was a pass. The raters agree on what is adequate and almost never on
   what is inadequate: of the 22 "inadequate" labels, none was shared by all four
   raters, and in 12 items exactly one rater failed an item the other three
   passed. Each rater had a private rule for failing.
3. **The third label added noise.** "Cannot judge" was used 5 times, 4 of them by
   rater B; on 3 of the 5 occasions the other three raters all passed the item.
   Rater B is the outlier in every pair (raw agreement 0.57–0.60).
4. **The counterfactual criterion was worse than chance** (κ = −0.17 on 9 items):
   the guideline had no rule for how many changes are too many or what counts as
   a change "that would alter the decision".
5. **Reasons were not recorded.** With three notes in 120 labels, disagreements
   could not be traced to a rule afterwards.
6. **Thirty items cannot show agreement either way.** Pairwise κ intervals run
   from about −0.27 to 0.76.

## 3. Ambiguous criteria and weaknesses in the v1.0 instructions

| # | Weakness | Evidence | Consequence |
|---|---|---|---|
| W1 | **Unit mismatch.** The guideline asked for yes / no / cannot-judge on each of conditions A–D; the rating sheet asked for one overall label per item. Raters had to combine the conditions themselves. | Sheets have one `rating` column; the guideline has four conditions. | Each rater used a private combination rule. |
| W2 | **Criterion on the sheet not in the guideline.** The sheet said "states the decisive details **and a confidence value**"; the guideline never mentions confidence or "decisive". | Criterion strings in the sheets. | Some raters failed missing confidence lines (format), others ignored it. |
| W3 | **Condition B (direction) contradicted the commonest response format.** v1.0 said a bare `Field: value` list fails B, and flagged B as "the condition raters most often disagree on". Most responses were bare lists. | 77.5% of labels were "adequate" although most responses were bare lists, so most raters did not apply B as written. | B was applied by some raters and silently dropped by others. |
| W4 | **No rule for invented reasons.** Thresholds or policies not in the application ("exceeds the bank's recommended threshold"). | 6 of 12 disputed items in the v1.1 draft turned on this. | Treated as contradiction by some, as a stated reason by others. |
| W5 | **"Cannot judge" too loosely defined** ("use rarely"). | 5 uses, 4 by one rater. | A third category with rater-specific use. |
| W6 | **No selectivity rule for counterfactuals** ("names a change … that would alter the decision"; nothing about listing every field). | Items listing 9–12 changes split the raters. | κ = −0.17 on counterfactuals. |
| W7 | **No direction table.** Whether a cited value could support the decision was left to intuition. | Two items all four raters passed fail once a fixed direction table is applied (IT-03EFB34A89, IT-DCA4077628). | Agreement on passes was partly agreement on not checking. |
| W8 | **Decision quality leaked in.** The guideline says not to judge the decision, but rater A's notes ("good savings", "tenure is 12 months and good saving") argue the decision. | Notes column. | Explanations of decisions a rater disliked were failed. |
| W9 | **Worked examples covered single conditions, not whole items.** | v1.0 tables show sentence fragments only. | No anchor for the overall verdict. |
| W10 | **No calibration before rating, no required notes.** | Procedure section. | Rule drift was invisible until scoring. |

## 4. What changed in response

- v1.1 (credit, 18 Nov 2026) fixed W1–W10 for credit: two labels, ordered pass/fail
  checks, a direction table, "invented" and "format" as notes rather than
  conditions, a 9-of-18 selectivity limit, 26 worked examples, a 20-item
  calibration with an 18/20 pass mark.
- **Insurance guideline v2.0** (`docs/annotation/guideline_insurance_v2.0.md`)
  carries the same structure to premium explanations, the only human study left in
  scope (calibration CAL1, Amendment A2). It adds: a direction table for life-insurance rating
  factors, a rule for "Ms."/"Mr." given as a reason (noted, never a pass/fail
  condition), a 4-of-8 selectivity limit, a required reason code on every
  `inadequate`, and constructed worked examples to be replaced by real items
  after the insurance run.
- AC1 is the primary agreement statistic (OPEN 1), with κ, prevalence and bias
  indices always reported beside it, so the prevalence effect in §2.1 is visible
  rather than hidden.
