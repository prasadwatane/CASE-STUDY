# Annotation protocol — briefing, calibration, round 2, adjudication

Status: **ready to run once guideline v1.1 is frozen.** It is not frozen; see
`04_guideline_v1.1_open_conflicts.md`. No round-2 label exists.

## 1. Roles

| Role | Who | Sees | Never sees |
|---|---|---|---|
| Rater A, Rater B | Two M.Sc. peers, not the author | Application, model response, frozen guideline | Model identity, judge verdict, the other rater's labels |
| Arbiter | A third person, not the author | Same as raters, plus the fact that the item was disputed | Which rater gave which label; judge verdict |
| Author | Prasad Watane | Everything after scoring | Does not label, does not arbitrate |

The author stays out of labelling because the judge prompt was written by the
author; a reference the author helped produce would not be independent of the
system under test.

## 2. Briefing (30 minutes, both raters together)

1. What the task is: decide whether an explanation meets the frozen checklist. It
   is **not** to decide whether the loan decision was right.
2. Read guideline v1.1 in full. Questions are answered by pointing to a rule; if
   no rule answers it, that is recorded as a gap and not improvised.
3. Consent: participation is voluntary, withdrawal is possible at any time, no
   personal data is recorded, sheets carry a rater code only.
4. Conduct: no discussion of items between raters until both sheets are complete.

## 3. Calibration exercise (before round 2, not evidence)

Purpose: confirm both raters apply v1.1 the way its worked examples do. Uses
round-1 items only, which are retired from evaluation.

| Step | Detail |
|---|---|
| Items | The 12 round-1 disagreement items plus 8 round-1 items all four raters agreed on (20 total) |
| Procedure | Each rater scores all 20 alone under v1.1, citing the rule number for every `inadequate` |
| Answer key | The single worked verdict per item in frozen v1.1 |
| Pass | At least 18 of 20 match the key, and every miss is traced to a named rule |
| On a miss | The rule is clarified in the guideline **before** freezing, never by coaching the rater on the item |
| Record | Scores are kept in `data/processed/annotation/calibration/` and labelled as training; they enter no agreement statistic |

Calibration cannot run yet: six of the twelve disagreement items have two
conflicting worked verdicts in the draft.

## 4. Freeze

1. Both raters and the author accept every rule; the draft's two halves are merged.
2. `sha256sum docs/annotation_guidelines_Art13_v1.1.md` is recorded in
   `PREREGISTRATION.md` and embedded in every exported sheet's key file.
3. From this point the guideline does not change. A later change is v1.2, a new
   hash, and a new round; labels are never pooled across versions.

## 5. Round 2 (pilot, 30 fresh items)

```
G=docs/annotation_guidelines_Art13_v1.1.md
python scripts/export_annotation.py finance --n 30 --overlap 30 --seed 20261116 \
       --guidelines $G --out data/processed/annotation/round2
python scripts/make_rater_packet.py data/processed/annotation/round2/annotation_rater_A.csv --guidelines $G
python scripts/make_rater_packet.py data/processed/annotation/round2/annotation_rater_B.csv --guidelines $G
# raters fill their sheets independently
python scripts/score_annotation.py finance --dir data/processed/annotation/round2
```

The existing `pilot3` sheets are 30 fresh items but their key carries the v1.0
guideline hash, so the packet is re-exported with a new seed. Before sending it
out, confirm from the key file that no (probe, model) pair also appears in
`pilot/`; a round-1 item in round 2 would measure memory, not the rules.

Reported for round 2: raw agreement, Cohen's κ, Gwet's AC1, prevalence and bias
indices, both raters' marginals, 95% bootstrap intervals, the confusion table,
and every disagreement with the rule each rater cited.

### Decision rule (proposed; becomes binding when the pre-registration is signed)

The exposé gates the main study on the lower bound clearing 0.61 at 30 items.
The simulation shows that gate is close to unpassable: even with a true ceiling
of κ = 0.70–0.80 the bound clears at n = 30 in only 13–33% of studies. The rule
below keeps that gate and adds a second, explicit route.

| Round-2 outcome | Action |
|---|---|
| Lower bound of the primary statistic ≥ 0.61 | Proceed to the main study. |
| Point estimate ≥ 0.61, lower bound below | Proceed **only if** raw agreement is ≥ 0.89 and every disagreement maps to one identifiable rule; the main study then decides S1. |
| Raw agreement below 0.80 | Do not start the main study. Record the negative result; rescope RQ1 to the countable dimensions and report transparency as not decidable under two guideline versions. |
| Between | One further guideline revision is allowed (v1.2, fresh items). A third failure is the finding. |

Thirty items cannot establish the ceiling; they can only show that it is
plausible. The 0.89 figure is the raw agreement that corresponds to κ ≈ 0.75 at
70% prevalence, the level at which the 300-item study has 87% power under the κ
criterion. The 0.80 floor is the level at which the case study's own power
analysis found the main study cannot succeed.

## 6. Main study (300 items, all double-rated)

- Stratified selection as in `grail/annotate/study.py`; item identity is
  (probe, model); per-rater seeded order; opaque tokens.
- Both raters label all 300. Batches of 50, with a check after the first batch
  that the `cannot judge` rate is below 5% per rater.
- No interim agreement statistic is computed for decision-making after batch 1;
  the study is not stopped early on a good or bad number.

## 7. Adjudication

1. Scoring identifies disputed items. The arbiter receives them in random order,
   stripped of both labels.
2. The arbiter applies frozen v1.1 and records a label and the rule number.
3. If the arbiter cannot decide under the rules, the item is marked
   `undecidable` and excluded from the reference; the count is reported.
4. Reference `R*` = the agreed label where A and B agree, the arbiter's label
   where they do not.

## 8. Storage (originals are never overwritten)

| File | Content | Mutable? |
|---|---|---|
| `annotation_rater_A.csv`, `…_B.csv` | Original labels as submitted | No. Hash recorded at submission. |
| `arbitration.csv` | Arbiter label and rule per disputed item | No |
| `reference.csv` | `R*`, derived by script from the three files above | Regenerated, never hand-edited |
| `KEY_do_not_open_until_scored.json` | Token → (probe, model), strata, guideline hash | Opened only after both sheets are hashed |

S1 and S2 are computed from the two original sheets. S2b and S3 use `reference.csv`.
Round-1 labels stay in `pilot/` as the pre-revision baseline.

## 9. What is recorded if agreement stays low

Raw agreement, κ and AC1 for each guideline version, the disagreement taxonomy,
and the statement that Article 13(1) adequacy, as operationalised twice, could
not be applied consistently by trained raters. Judge validation on transparency
is then reported as not possible, and RQ2 proceeds on the arithmetic of the bound
alone.
