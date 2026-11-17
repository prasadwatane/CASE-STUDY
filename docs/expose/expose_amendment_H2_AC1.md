# Exposé amendment — H2: chance-corrected agreement statistic

**Status: pre-registered. Filed 13 September 2026, before any annotation label
has been recorded.**

That date is the point of this document. Adding a second agreement statistic
*after* seeing a disappointing κ would be indistinguishable from choosing the
statistic that gives the answer one wants, and this project's central
methodological claim is that its thresholds were fixed before its results were
known. So the change is recorded here, dated, and committed — under the same
discipline as the signed checklist, and for the same reason.

No annotation has begun. The guidelines (`annotation_guidelines_Art13.md`,
v1.0) are frozen and unchanged by this amendment: what raters do is identical.
Only the statistic computed from their labels changes.

---

## Why the amendment is needed

Cohen's κ corrects observed agreement for agreement expected by chance, and it
estimates that chance expectation from the **marginal distribution of the
labels**. When one category dominates, expected agreement approaches observed
agreement, and κ collapses toward zero even though the raters agree on almost
every item. This is the **kappa paradox** (Feinstein & Cicchetti 1990; Byrt,
Bishop & Carlin 1993): two raters agreeing on 95% of items can produce κ ≈ 0.

The Article 13(1) docket is known in advance to be skewed in exactly this way.
The judge pilot on 10 items returned 70% adequate, and the condition-level
marginals are more lopsided still — `names_field` is settled affirmatively in
code for the large majority of responses, because models writing a credit
decision almost always mention a field. A rater pair could agree on 9 items in
10 and still return κ below the pre-registered 0.61.

**Under the original H2, that outcome would be recorded as a failure to achieve
substantial agreement.** It would not be one. It would be an artefact of the
statistic meeting a base rate it was never robust to, and the thesis would
report a false negative about its own instrument.

This risk was flagged in the criterion's own review note before any data
existed: *"If most explanations are adequate the marginals are skewed and
Cohen's kappa will deflate — report Gwet's AC1 alongside."* The amendment acts
on a concern the project had already written down, which is why it can be filed
now rather than argued for later.

## What replaces it

Gwet's AC1 (Gwet 2008) corrects for chance using a different estimate of the
chance-agreement probability, one that does not inflate as the marginals skew.
It is not a more generous statistic — it is a differently-conditioned one, and
it can fall below κ where marginals are balanced. That is the reason both are
reported.

### Amended H2

> **H2.** The LLM-as-a-Judge achieves substantial agreement with human
> auditors on the qualitative docket. **Gwet's AC1 ≥ 0.61 is the primary
> criterion**, with a 95% confidence interval, reported per condition and per
> dimension. Cohen's κ is reported alongside it in every case, together with
> the prevalence and bias indices (Byrt et al. 1993), so the influence of the
> marginals on each statistic is visible rather than assumed. Both are
> interpreted against the human–human agreement ceiling computed on the same
> items: the judge is not required to exceed the ceiling, and agreement at or
> near it is the success condition.

### Consequential edits elsewhere in the Exposé

| Location | Change |
|---|---|
| C3 (contributions) | "chance-corrected agreement (Cohen's κ)" → "chance-corrected agreement (Gwet's AC1 primary, Cohen's κ reported alongside)" |
| §5 H2 | replaced with the wording above |
| §6 methods, inter-annotator agreement | add: AC1 primary; κ, prevalence index and bias index reported with it; ceiling computed on the same items |
| S2 (success criteria) | "κ ≥ 0.61" → "AC1 ≥ 0.61, with κ reported" |
| §Risks | "inter-rater agreement (Cohen's κ)" → "inter-rater agreement (AC1 and κ)" |

## The decision rule, fixed now

Stated in advance so that no choice remains to be made once the numbers exist:

1. **Both statistics are reported always**, per condition, with 95% intervals —
   whatever they show, and whichever is higher.
2. **AC1 carries the inference.** The 0.61 threshold applies to AC1.
3. **κ is reported for comparability** with the LLM-as-judge literature, which
   overwhelmingly reports κ. Where κ and AC1 diverge, the prevalence index is
   reported next to them and the divergence is discussed, not resolved in favour
   of the larger number.
4. **The ceiling governs.** Judge–human agreement is read relative to
   human–human agreement on the same items, computed with the same statistic. A
   judge that matches a ceiling of 0.55 has done as well as the task permits,
   and this is reported as such rather than as a failure against 0.61.
5. **A negative result is a result.** If AC1 falls materially below the ceiling,
   the transparency finding is reported as not automatable at acceptable
   reliability. That is a contribution, not a failed chapter: it bounds where
   automated auditing can be trusted, which is C3's stated purpose.

## Implementation

`grail/annotate/agreement.py` computes both statistics. No pipeline change is
required by this amendment; the change is to which number the hypothesis is
stated over, and to the requirement that the other be reported beside it.

## References

- Byrt, T., Bishop, J., & Carlin, J. B. (1993). Bias, prevalence and kappa.
  *Journal of Clinical Epidemiology*, 46(5), 423–429.
- Feinstein, A. R., & Cicchetti, D. V. (1990). High agreement but low kappa I:
  The problems of two paradoxes. *Journal of Clinical Epidemiology*, 43(6),
  543–549.
- Gwet, K. L. (2008). Computing inter-rater reliability and its variance in the
  presence of high agreement. *British Journal of Mathematical and Statistical
  Psychology*, 61(1), 29–48.
- Landis, J. R., & Koch, G. G. (1977). The measurement of observer agreement for
  categorical data. *Biometrics*, 33(1), 159–174.
