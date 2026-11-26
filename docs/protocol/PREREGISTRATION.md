# Pre-registration record

**Status: UNSIGNED DRAFT** (updated 25 November 2026). All seven open decisions are closed. This becomes the
pre-registration only when the hashes are
regenerated and all three signatures are in place. Until then nothing in
`docs/protocol/` is binding.

**Numbering.** Sections written before 25 November 2026 use the exposé's
numbering (RQ1 reliability, RQ2 certification, RQ3 sequential cost). Amendment A2
renumbers: RQ1 early stopping, RQ2 carry-over to life insurance, RQ3 Ms./Mr.
pricing; human agreement and the judge are calibration steps CAL1–CAL3.

**Status note, 23 November 2026: human study parked.** The human annotation
study (RQ1 and RQ2: hypotheses H1–H2, criteria S1–S3, the annotation protocol and
guideline) is parked and will be redone. Its registered text below is kept
unchanged for the re-run, but no result reported in the meantime depends on
human labels, and LLM-judge scores are reported as descriptive only. The parts
that need no raters (RQ3, RQ4, Amendments A1 and A1.1) are unaffected.

**Status note, 23 November 2026: credit results corrected (Correction C1,
`08_credit_repeated_applications.md`).** The credit probe set repeats applicants
(333 people behind the 2,844 marginal pairs). All finance scoring now counts
each applicant once. Verdict labels for Article 10(2)(f) are unchanged, the
intervals are about three times wider, and on the credit development replay
O'Brien–Fleming no longer meets S4 (spend 0.87 × static). The insurance run
remains the confirmatory test.

## What is being registered

Hypotheses H1–H3 and criteria S1–S5 (exposé rev2, Table 1), the evaluation
protocol, the annotation protocol, the frozen annotation guideline, the power
simulation, and the RQ2/RQ3 analysis code. **Amendment A1**
(`06_insurance_amendment.md`) adds life insurance pricing (Annex III 5(c)) as a
second audited sector and as the confirmatory data set for H3; it is signed
together with this record. **Amendment A1.1** (`07_insurance_records_amendment.md`,
23 November 2026) replaces A1's synthetic applications with real NHANES
1999–2004 participants and adds one exploratory analysis (do the quotes rank
people by recorded ten-year mortality?); hypotheses, margins and the run plan of
A1 are unchanged, and A1's synthetic pack stays the fallback if the imported data
fail A1.1 §6. **Amendment A2** (`09_amendment_A2_final_scope.md`, 25 November 2026, revised the
same day after supervisor feedback) replaces the research questions with three final
ones (RQ1 early stopping, RQ2 carry-over to life insurance, RQ3 Ms./Mr. pricing on
NHANES) and moves human agreement and the LLM judge out of the research questions
into a calibration of the explanation measurement (CAL1 human agreement on 240
insurance explanations under guideline v2.0, mandatory; CAL2 judge calibration with
the pooled selective-error bound, conditional on CAL1; CAL3 judge robustness,
optional). An earlier hiring draft of A1 was withdrawn on 18 November 2026 before
signature; its files were removed from the repository on 25 November 2026 and
remain in the git history.

## Open decisions (must be closed before signing)

| # | Decision | Options | Where it bites |
|---|---|---|---|
| ~~OPEN 1~~ **CLOSED 18 Nov** | Primary agreement statistic for S1 | **Gwet's AC1 primary**; Cohen's κ, prevalence and bias indices reported alongside | True ceiling κ = 0.70, n = 300: S1 passes 49% (κ) vs 96% (AC1) at 70% prevalence, 38% vs 100% at 15%. Decided knowing round-1 κ was low; disclosed below |
| ~~OPEN 2~~ **CLOSED 18 Nov** | Calibration sample for the selective-error bound | **Per-stratum bound with docket weights** (`gate.selective.stratified_bound`) on the 300 stratified items; no separate random subset. *Superseded for the insurance study by A2 §5: pooled bound on a self-weighting sample of 240 (per-stratum bounds cannot certify 5% at that size)* | — |
| ~~OPEN 3~~ **CLOSED 18 Nov** | Interval and statistic for S2 / S2b | **BCa**, one-sided 95%, over items; **AC1** (matching OPEN 1); κ-based D and Δ reported. Implemented in `grail/annotate/judge_validation.py` | Simulated false-pass rate at the margin: percentile 0.055–0.061, BCa 0.047–0.055 (n 120–300, prevalence 0.65–0.70) |
| ~~OPEN 4~~ **CLOSED 18 Nov** | `cannot judge` | **Removed from the guideline**; two labels, matching the sheets and the binary power simulation | — |
| ~~OPEN 5~~ **CLOSED 18 Nov** | S4 definition | **CI of the mean over seeds, plus coverage ≥ 0.90 × static; O'Brien–Fleming spending primary**; the confidence sequence (exposé's primary) reported as a comparator / negative result. `sequential.s4_primary`, `PRIMARY_POLICY` | Chosen on the finance development replay with results in view; there OBF meets S4 at full budget only. Confirmatory test: the insurance run (Amendment A1). *Corrected 23 Nov (C1): counting each applicant once, OBF stays faithful on the development replay (fidelity 1.00, coverage 1.00 × static) but spends 0.87 × static, so S4 is not met there; OBF stays the primary policy* |
| ~~OPEN 6~~ **CLOSED 18 Nov** | Judge nonconformity score | **Five-run self-agreement at T = 0.3** (existing); no paraphrase design. The exposé's claim that runs at T = 0 are identical is corrected: the judge runs at T = 0.3 | Coarse score (four usable values) |

| ~~OPEN 7~~ **CLOSED 18 Nov** | Judge rubric against guideline v1.1 | **(a) aligned.** Rubric `art13-v1.1`: per-family conditions (explanations: names_field, consistent_with_decision, no_contradiction; counterfactuals: names_field, changes_flip, selective, no_contradiction); rule E2 settled in code when a recorded value is copied at the wrong end of the direction table (47 of 304 explanations). Rule-based baseline Q re-stated as v1.1 in code. **The judge must be re-run on all four models before any round-2 label** (`run_judge.py … --local --fresh`); checkpoints are versioned so v1.0 verdicts cannot be resumed into a v1.1 run | The v1.0 judge outputs and the 16 Nov judge-vs-rule preview (`judge_preview.json`) were produced under the old reading and are superseded; they are kept, not used |

Guideline v1.1 merged into one rule set on 18 November 2026
(`docs/annotation/credit_guideline_v1.1.md`, decisions below). It is frozen when
the calibration exercise passes and both raters accept it.

### Guideline v1.1 decisions (18 November 2026)

| Conflict (`04_…`) | Decided |
|---|---|
| 1. Must a detail state its direction in words? | No. A named field consistent with the decision is enough; inconsistency is defined by a fixed direction table (the face-valid ordering that defines the credit strata) |
| 2. Does an invented threshold or policy fail? | No. Only contradiction fails, as the signed criterion (c) says. Invented reasons are noted and reported descriptively |
| 3. Counterfactual selectivity | More than 9 of the 18 fields fails |
| 4. Round 2 items | Fresh: `scripts/export_annotation.py --exclude` removes every (probe, model) rated in round 1; checked, 0 overlap |
| 5. Gate statistic | AC1 (OPEN 1) |
| 6. Main-study overlap | All 300 double-rated |
| 7. `cannot judge` | Removed (OPEN 4) |
| 8–9. Scoring command, stale hash | Round-2 packet is exported only after freezing, so its key carries the v1.1 hash |
| 10. AC1 amendment date | Unchanged: still not evidenced by git; disclosed below |
| Not in `04`: format checks | Three details and a confidence line are **not** conditions; the signed criterion does not contain them and the judge does not score them |

These are readings of the signed Article 13(1) criterion, whose text is
unchanged. Decision 1 is a lenient reading of condition (b) "states the
direction"; it is made deliberately, and an expected adequacy rate of roughly
60–70% (word-matching estimate) was in view when it was made.

## Disclosure: analyses run before signing

On 16 November 2026, before signing, the following were computed and their results
seen (`05_findings_2026-11-16.md`):

- the RQ3 replay over the 16 case-study requirements, all policies, all budgets;
- simulated error rates of all allocation policies under a known truth;
- a label-free judge preview: judge-versus-rule agreement and self-agreement
  distribution on the 608 judged items.

On 18 November 2026, before signing and before any round-2 label existed, the
following were also computed and seen while deciding the guideline: a
word-matching estimate of the adequacy rate under each candidate rule set on the
608 logged responses, and the S1 power simulation at 15% and 25% prevalence. The
guideline decisions and OPEN 1 were made with round-1 labels (κ ≈ 0) and the
judge's outputs (adequate 71–95%) known.

On 18 November 2026 the second sector was switched from hiring to life
insurance pricing at the author's decision. The hiring checklist had been
notary-signed that day (13:31); no hiring probe set or response exists. The
insurance pipeline was exercised only with an offline stub.

Consequences: (i) the 16-requirement replay is a **development set**; the
confirmatory RQ3 test is to be pre-registered on the responses produced by the C4
breadth run, which do not yet exist. (ii) Choices under OPEN 5 and OPEN 6 are
made knowing these results and must say so. (iii) No human label of round 2 or the
main study exists, so RQ1 and the RQ2 calibration remain blind.

## Hashes (SHA-256) as of this draft

| File | SHA-256 |
|---|---|
| `docs/expose/Expose_Watane_PrasadDevendra_rev2.pdf` | `2b3f4ef5fd926a8fd3fde9487e56986d27da7a552f784714c71c05313daec3ee` |
| `docs/expose/expose_amendment_H2_AC1.md` | `8324c5b15fe4b80f841a2f7f19914e203f1d7ac2d81752ffdcc21d88bf748383` |
| `docs/protocol/01_contribution_matrix.md` | `1d54af7d389b3e9da8955dd22beba2eb6fa09da0aabc318bf1f245c019a0d608` |
| `docs/protocol/02_evaluation_protocol.md` | `7747c714059801cf5fd88bcec0d77c95ba4d7b529c9da4073c5e6ff566494d32` |
| `docs/protocol/03_annotation_protocol.md` | `b88a75b4fb94c2583576631e0bbadd3f46fe5b589a5a5e720e8d7c0b04236d40` |
| `docs/protocol/04_guideline_v1.1_open_conflicts.md` | `f33fca981824aefeb3692d7537fec973fc02cf688cf6eaa05ebf9a93fca9da1e` |
| `docs/protocol/06_insurance_amendment.md` | `e9e847cceeec7710e161655d653c34844f86573c2a8e9396f485605972da8d3f` |
| `docs/protocol/07_insurance_records_amendment.md` (A1.1) | `1d32d4d2909672204361b691f331f7ada0e8960356ac03579bf3aa5ced8fd2ae` |
| `data/stimuli/life_insurance_nhanes/pack.json` (A1.1) | `a4b0f991119cc8e0cfc26e6e17b65297b386390947d2227eaaf73a3cad50f11a` |
| `grail/jury/continuous.py` (A1 route + A1.1 validity) | `5a909a664e35b477b4fc603367984d6aaff79dac828fd75385812217bba43f12` |
| `data/records/nhanes/applicants.jsonl` (A1.1) | pending: recorded after the import, before signing |
| `docs/protocol/09_amendment_A2_final_scope.md` (A2) | `be920933e539a9e374a6ce2a8df7ac4dd4f62f95b930e51bb3740936f97b2636` |
| `docs/annotation/guideline_insurance_v2.0.md` (A2) | `9550833c16cc38b6fea527dab92eb55f5690e5da8d66ece4cb5ddb1918922584` |
| `docs/protocol/10_round1_annotation_analysis.md` (A2) | `d5ebeaa0cb3c22a24aa10a2803048aa44d720c7a95bdb95f3bd9190cb4fd83bb` |
| `docs/protocol/margin_sim_n240_ac1.json` (A2) | `522192f158e4d9335c635dfe7d24f6d4adfed6062592acbe7be40edee023b231` |
| `grail/annotate/insurance_study.py` (A2, CAL1) | `d25f2e917a7256163205bd3a47389298ba6c8e3cad9818e09c1c993ed67f6549` |
| `scripts/human_agreement.py` (A2, CAL1) | `91169be52ef14b30207f72e22648ed9fee112555cba6a5a309e48bf70787fbd1` |
| `docs/protocol/08_credit_repeated_applications.md` (C1) | `92a9fb5c740348e9792f0dc206e977ddc10f982b379a0f88a32ab0945b54f861` |
| `grail/jury/verdict.py` (C1) | `e6926b7a940851dc3a39d84363a7bc423eaaea6937c7c5d54778ee9d3cf55cc5` |
| `grail/allocate/replay.py` (C1) | `3d8de865cfa46ee709ec1bb05b33ea0dd448d10be1d850734cd89b79ce35a8e1` |
| `docs/protocol/05_findings_2026-11-16.md` | `48faebc50f566cd424c2a01d56d5c6d6d62b6e954bed0d11a74f03c7079e05e6` |
| `docs/expose/power_sim.py` | `399c0e92a8484ea1f0cc7c39e79aa095467cc1294ce8879ff89ad9eece99bc17` |
| `docs/protocol/power_results.json` | `bd9e49d3308c8e83107ca6c76182cf4f5da392c1cfd5c9ae8be3721b6b1cc762` |
| `grail/allocate/sequential.py` | `eb16f5ffeab506517e3f12ecbc57540b6e6fe350485a1bee93a1aacbc1a90ff9` |
| `grail/gate/selective.py` | `e7de170b3818be03d36b75a5865a39996818b92f4af2e89c76e429fabbf13cc5` |
| `grail/judge/baselines.py` (v1.1) | `9945271f815ffd75fae96829e68b0ec699b5cd553180b5645d054ed26d0c4e7a` |
| `grail/judge/rubric.py` (art13-v1.1) | `ee7e3811cb0a09829aea7ea254c36384f009fe4be9fed716548d09590a8446c6` |
| `grail/annotate/judge_validation.py` | `4f69607787e0ef0fa107a07944b8a1dbb1f03484279da85474643efe888bfd83` |
| `grail/judge/checks.py` | `9e2c6bba3bea0140238ba29b9a0a77d0efd00ff39465e715b1920daef2157b12` |
| `data/processed/runs/finance/sequential.json` | `35da5998cbd29e6bf2d0c0b9a1453b2b7f60588bbfc263279c092cdbe1c57eca` |
| `data/processed/runs/finance/judge_preview.json` | `2579d9acddeb1be65256ab06950c85d722df83bfba1a7d64d3bd10933e50a01e` |
| `docs/annotation/credit_guideline_v1.1.md` (candidate; final after calibration) | `3994cf4167e045b813cee6237d6f17225c29539be52f6409ddb2f121d20ba2a8` |
| `data/processed/checklists/finance_signed.json` | `3be6fd59cce9e31c7c509b0c5137ed622a18516da14253b025efeea81930666b` |

The v1.1 row is the candidate text. If calibration forces a clarification the
hash changes and this row is updated before round 2 is exported. Regenerate with `sha256sum <file>` after the open
decisions are closed.

## Evidence that no round-2 data existed at registration

- The credit round-2 sheets (`pilot2/`, `pilot3/`): every `rating` cell empty
  (checked 16 Nov 2026); removed from the repository on 25 Nov 2026 with the
  credit human study (out of scope, A2).
- No judge output exists for a round-2 or main-study packet.
- Round-1 labels (guideline v1.0) exist and are retired from evaluation.

## Guideline v2.0 acceptance (both raters, after the 20-item calibration passes)

| Rater | Name | Calibration score (of 20) | Date | Accepted |
|---|---|---|---|---|
| A | | | | |
| B | | | | |

## Signatures

| Role | Name | Date | Signature |
|---|---|---|---|
| Author | Prasad Devendra Watane | | |
| First supervisor | Prof. Dr. Swati Chandna | | |
| Second supervisor | Prof. Dr. Binh Vu | | |

Repository commit at signing: `________________`
