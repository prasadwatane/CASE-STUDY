# Pre-registration record

**Status: UNSIGNED DRAFT** (updated 23 November 2026). All seven open decisions are closed. This becomes the
pre-registration only when the hashes are
regenerated and all three signatures are in place. Until then nothing in
`docs/protocol/` is binding.

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
fail A1.1 §6. An earlier hiring draft of A1
(`06_employment_amendment.md`) was withdrawn on 18 November 2026 before signature.

## Open decisions (must be closed before signing)

| # | Decision | Options | Where it bites |
|---|---|---|---|
| ~~OPEN 1~~ **CLOSED 18 Nov** | Primary agreement statistic for S1 | **Gwet's AC1 primary**; Cohen's κ, prevalence and bias indices reported alongside | True ceiling κ = 0.70, n = 300: S1 passes 49% (κ) vs 96% (AC1) at 70% prevalence, 38% vs 100% at 15%. Decided knowing round-1 κ was low; disclosed below |
| ~~OPEN 2~~ **CLOSED 18 Nov** | Calibration sample for the selective-error bound | **Per-stratum bound with docket weights** (`gate.selective.stratified_bound`) on the 300 stratified items; no separate random subset | — |
| ~~OPEN 3~~ **CLOSED 18 Nov** | Interval and statistic for S2 / S2b | **BCa**, one-sided 95%, over items; **AC1** (matching OPEN 1); κ-based D and Δ reported. Implemented in `grail/annotate/judge_validation.py` | Simulated false-pass rate at the margin: percentile 0.055–0.061, BCa 0.047–0.055 (n 120–300, prevalence 0.65–0.70) |
| ~~OPEN 4~~ **CLOSED 18 Nov** | `cannot judge` | **Removed from the guideline**; two labels, matching the sheets and the binary power simulation | — |
| ~~OPEN 5~~ **CLOSED 18 Nov** | S4 definition | **CI of the mean over seeds, plus coverage ≥ 0.90 × static; O'Brien–Fleming spending primary**; the confidence sequence (exposé's primary) reported as a comparator / negative result. `sequential.s4_primary`, `PRIMARY_POLICY` | Chosen on the finance development replay with results in view; there OBF meets S4 at full budget only. Confirmatory test: the insurance run (Amendment A1). *Corrected 23 Nov (C1): counting each applicant once, OBF stays faithful on the development replay (fidelity 1.00, coverage 1.00 × static) but spends 0.87 × static, so S4 is not met there; OBF stays the primary policy* |
| ~~OPEN 6~~ **CLOSED 18 Nov** | Judge nonconformity score | **Five-run self-agreement at T = 0.3** (existing); no paraphrase design. The exposé's claim that runs at T = 0 are identical is corrected: the judge runs at T = 0.3 | Coarse score (four usable values) |

| ~~OPEN 7~~ **CLOSED 18 Nov** | Judge rubric against guideline v1.1 | **(a) aligned.** Rubric `art13-v1.1`: per-family conditions (explanations: names_field, consistent_with_decision, no_contradiction; counterfactuals: names_field, changes_flip, selective, no_contradiction); rule E2 settled in code when a recorded value is copied at the wrong end of the direction table (47 of 304 explanations). Rule-based baseline Q re-stated as v1.1 in code. **The judge must be re-run on all four models before any round-2 label** (`run_judge.py … --local --fresh`); checkpoints are versioned so v1.0 verdicts cannot be resumed into a v1.1 run | The v1.0 judge outputs and the 16 Nov judge-vs-rule preview (`judge_preview.json`) were produced under the old reading and are superseded; they are kept, not used |

Guideline v1.1 merged into one rule set on 18 November 2026
(`docs/annotation_guidelines_Art13_v1.1.md`, decisions below). It is frozen when
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
| `docs/protocol/03_annotation_protocol.md` | `8398661cac1368d12c4ffd9c9f9d16c8e3388acbdf8c57f809f676185a000ccf` |
| `docs/protocol/04_guideline_v1.1_open_conflicts.md` | `f33fca981824aefeb3692d7537fec973fc02cf688cf6eaa05ebf9a93fca9da1e` |
| `docs/protocol/06_insurance_amendment.md` | `e9e847cceeec7710e161655d653c34844f86573c2a8e9396f485605972da8d3f` |
| `docs/protocol/07_insurance_records_amendment.md` (A1.1) | `1d32d4d2909672204361b691f331f7ada0e8960356ac03579bf3aa5ced8fd2ae` |
| `data/stimuli/life_insurance_nhanes/pack.json` (A1.1) | `a4b0f991119cc8e0cfc26e6e17b65297b386390947d2227eaaf73a3cad50f11a` |
| `grail/jury/continuous.py` (A1 route + A1.1 validity) | `5a909a664e35b477b4fc603367984d6aaff79dac828fd75385812217bba43f12` |
| `data/records/nhanes/applicants.jsonl` (A1.1) | pending: recorded after the import, before signing |
| `docs/protocol/08_credit_repeated_applications.md` (C1) | `92a9fb5c740348e9792f0dc206e977ddc10f982b379a0f88a32ab0945b54f861` |
| `grail/jury/verdict.py` (C1) | `07a104b2a8155a0def05032bca0bda464c6e703fdb5fc98edd108dea20f4c8dd` |
| `grail/allocate/replay.py` (C1) | `e469859f46667c91e79899f85c105b067e033714ab1f35095f52b6d43906fc20` |
| `docs/protocol/06_employment_amendment.md` (withdrawn) | `61703281f7b8696f48c13edf97ad4b6c3d3f57bb46569bd391372f62d3c3f8c8` |
| `docs/protocol/05_findings_2026-11-16.md` | `48faebc50f566cd424c2a01d56d5c6d6d62b6e954bed0d11a74f03c7079e05e6` |
| `docs/expose/power_sim.py` | `399c0e92a8484ea1f0cc7c39e79aa095467cc1294ce8879ff89ad9eece99bc17` |
| `docs/protocol/power_results.json` | `bd9e49d3308c8e83107ca6c76182cf4f5da392c1cfd5c9ae8be3721b6b1cc762` |
| `grail/allocate/sequential.py` | `a536a580c13628f6f7215c481ffb6daa1e9566363c319aaa50c3f931965cefef` |
| `grail/gate/selective.py` | `8c6bb09270061acb9dcfed95ff0c8f81a5cdb3dfd85d7f77ce1b949a4548d284` |
| `grail/judge/baselines.py` (v1.1) | `25bdbeadca5e183b81dd5724df9ed764ee78dfb2cc9a7fe288389caab79994f0` |
| `grail/judge/rubric.py` (art13-v1.1) | `59274b62b0a267c009fd943cd3738d9d8d37c777edc42bfc795320edac532938` |
| `grail/annotate/judge_validation.py` | `4f69607787e0ef0fa107a07944b8a1dbb1f03484279da85474643efe888bfd83` |
| `grail/judge/checks.py` | `a3b4120b6ccb4e2599d90de7594cb2ee6efb6722bd4b9740db9f0571a9f1d830` |
| `data/processed/runs/finance/sequential.json` | `35da5998cbd29e6bf2d0c0b9a1453b2b7f60588bbfc263279c092cdbe1c57eca` |
| `data/processed/runs/finance/judge_preview.json` | `2579d9acddeb1be65256ab06950c85d722df83bfba1a7d64d3bd10933e50a01e` |
| `docs/annotation_guidelines_Art13_v1.1_DRAFT.md` | `14ce6442fa8d4fd1172ab98095a018d2aa614e46ca30d406dcfc52d6bdeb60a4` (superseded) |
| `docs/annotation_guidelines_Art13_v1.1.md` (candidate; final after calibration) | `9cc7fece07adebde27f96be8188fed0138f624126977f3c5537495b0d2707108` |
| `data/processed/checklists/finance_signed.json` | `3be6fd59cce9e31c7c509b0c5137ed622a18516da14253b025efeea81930666b` |

The v1.1 row is the candidate text. If calibration forces a clarification the
hash changes and this row is updated before round 2 is exported. Regenerate with `sha256sum <file>` after the open
decisions are closed.

## Evidence that no round-2 data existed at registration

- `data/processed/annotation/pilot2/` and `pilot3/`: every `rating` cell empty
  (checked 16 Nov 2026).
- No judge output exists for a round-2 or main-study packet.
- Round-1 labels (guideline v1.0) exist and are retired from evaluation.

## Guideline v1.1 acceptance (both raters, after calibration passes)

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
