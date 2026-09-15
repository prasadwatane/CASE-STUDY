# Drop-in update: annotation pilot round 1

Copy this folder's contents over `grail-audit/` (paths match). Then:

```
pytest -q tests/test_agreement.py
python scripts/score_pilot.py finance pilot_round1
```

## What is added

| path | what |
|---|---|
| `grail/annotation/agreement.py` | N-rater agreement: pairwise Cohen's κ with bootstrap CI, Fleiss κ, per-criterion breakdown, disagreement list. κ is `None` when undefined, never 0.0; never returned without marginals and expected agreement. Undeclared labels raise. |
| `scripts/score_pilot.py` | `score_pilot.py <domain> <round>` → `agreement.json` + `agreement.md` beside the rater sheets. |
| `data/annotation/finance/pilot_round1/` | the three round-1 sheets (`rater_B1/B2/B3.csv`) and their scored report. |
| `docs/annotation_guidelines_transparency_v2.md` | revised T1/T2 criteria as checklists, with the 16 disagreement items as worked examples. |
| `tests/test_agreement.py` | 5 tests incl. a regression pinning the round-1 numbers. |

`scripts/score_annotation.py` is untouched; it still handles the A/B key-file
flow for the main study. `score_pilot.py` is for guideline-calibration rounds
where every rater sees the same sheet and there is no gold.

## Paste into README under "Annotation study"

### Pilot round 1 — the guideline did not survive contact with raters

Three raters scored the same 30 transparency items under guideline v1.

| pair | agreement | expected | κ | 95% CI |
|---|---|---|---|---|
| B1–B2 | 0.70 | 0.70 | 0.00 | [−0.27, 0.38] |
| B1–B3 | 0.60 | 0.61 | −0.03 | [−0.21, 0.17] |
| B2–B3 | 0.57 | 0.59 | −0.07 | [−0.27, 0.23] |
| Fleiss, 3 raters | 0.62 | 0.64 | **−0.05** | — |

Raw agreement of 60–70% looks respectable and is exactly why it is never reported
alone: with ~80% of items labelled "adequate", chance agreement is also 60–70%, and
κ is zero. Per criterion, "decisive details + confidence" scored κ = 0.00 and
"what would have to change" κ = −0.18.

The 16 disagreements are not noise. They resolve into three implicit rubrics —
format compliance, content plausibility, and agreement with the decision itself —
each a defensible reading of v1. That is a guideline defect, not a rater defect,
and the fix is decidability, not more raters: v2 restates both criteria as
pass/fail checklists (T1.1–T1.5, T2.1–T2.4) with every disagreement item as a
worked example, and reserves "cannot judge" for unparseable output only.

Round 2 re-scores the same 30 items under v2. The gate to the 120-item overlap is
the lower bootstrap bound of κ clearing 0.61 — the point estimate does not count.
Round-1 numbers stay in the report as the pre-revision baseline; a study that only
shows the post-revision κ hides the cost of getting there.
