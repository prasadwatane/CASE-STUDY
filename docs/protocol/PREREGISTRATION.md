# Pre-registration record

**Status: UNSIGNED DRAFT** (updated 16 November 2026). This becomes the
pre-registration only when the open decisions below are closed, the hashes are
regenerated and all three signatures are in place. Until then nothing in
`docs/protocol/` is binding.

## What is being registered

Hypotheses H1–H3 and criteria S1–S5 (exposé rev2, Table 1), the evaluation
protocol, the annotation protocol, the frozen annotation guideline, the power
simulation, and the RQ2/RQ3 analysis code.

## Open decisions (must be closed before signing)

| # | Decision | Options | Where it bites |
|---|---|---|---|
| OPEN 1 | Primary agreement statistic for S1 | Cohen's κ (exposé rev2) or Gwet's AC1 (amendment; what the code implements) | True ceiling κ = 0.70, 70% prevalence, n = 300: S1 has a 49% chance under κ and 96% under AC1 |
| OPEN 2 | Calibration sample for the selective-error bound | Per-stratum bound with docket weights (`gate.selective.stratified_bound`), or a simple-random calibration subset | A pooled bound over a stratified sample does not certify docket-level risk |
| OPEN 3 | Interval for the S2 test | Percentile bootstrap (simulated type-I 0.06–0.07) or BCa | Every S2 result |
| OPEN 4 | `cannot judge` | Third label added to the sheets, or removed from the guideline | Guideline and sheets disagree |
| OPEN 5 | S4 definition | (a) per-seed range or CI of the mean; (b) add a coverage condition; (c) primary method: confidence sequence as in the exposé, or report it as a negative result | Development replay: S4 undetermined under the range, met for both spending rules under the mean CI; the confidence sequence keeps only 63% of static coverage |
| OPEN 6 | Judge nonconformity score | Existing five-run self-agreement at T = 0.3, or five paraphrases at T = 0 (exposé), or both with one primary | The exposé's stated reason for paraphrases (identical runs at T = 0) does not apply to the case-study judge, which runs at T = 0.3 |

Also required: guideline v1.1 merged into one rule set and frozen
(`04_guideline_v1.1_open_conflicts.md`).

## Disclosure: analyses run before signing

On 16 November 2026, before signing, the following were computed and their results
seen (`05_findings_2026-11-16.md`):

- the RQ3 replay over the 16 case-study requirements, all policies, all budgets;
- simulated error rates of all allocation policies under a known truth;
- a label-free judge preview: judge-versus-rule agreement and self-agreement
  distribution on the 608 judged items.

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
| `docs/protocol/01_contribution_matrix.md` | `07e463a18419744dac0ce8cde2f51897d48e76d3c7ee8a32154214ab71d218de` |
| `docs/protocol/02_evaluation_protocol.md` | `ed95efb46cda20f2ff7d201baaac32b7f643ab01d93f33aeaa755d16e2f53895` |
| `docs/protocol/03_annotation_protocol.md` | `928c8395ea04a53e20ca2afc180b38510bbc745d9eae5a98d04f9739d1dc9fe9` |
| `docs/protocol/04_guideline_v1.1_open_conflicts.md` | `f33fca981824aefeb3692d7537fec973fc02cf688cf6eaa05ebf9a93fca9da1e` |
| `docs/protocol/05_findings_2026-11-16.md` | `48faebc50f566cd424c2a01d56d5c6d6d62b6e954bed0d11a74f03c7079e05e6` |
| `docs/expose/power_sim.py` | `399c0e92a8484ea1f0cc7c39e79aa095467cc1294ce8879ff89ad9eece99bc17` |
| `docs/protocol/power_results.json` | `bd9e49d3308c8e83107ca6c76182cf4f5da392c1cfd5c9ae8be3721b6b1cc762` |
| `grail/allocate/sequential.py` | `a86d11277248643596b7a98fd8502eaf4419977719ab41c2653d86e69c30a742` |
| `grail/gate/selective.py` | `8c6bb09270061acb9dcfed95ff0c8f81a5cdb3dfd85d7f77ce1b949a4548d284` |
| `grail/judge/baselines.py` | `6e6e00d0151141d521c979a9aeb63515ab9ad0111043bf2a126736f4927ef9d1` |
| `data/processed/runs/finance/sequential.json` | `f48c1bd02f7108d15546d24b73d541972bd41ef4d1b7dbfeefdd746011cb8a63` |
| `data/processed/runs/finance/judge_preview.json` | `2579d9acddeb1be65256ab06950c85d722df83bfba1a7d64d3bd10933e50a01e` |
| `docs/annotation_guidelines_Art13_v1.1_DRAFT.md` | `14ce6442fa8d4fd1172ab98095a018d2aa614e46ca30d406dcfc52d6bdeb60a4` |
| `data/processed/checklists/finance_signed.json` | `3be6fd59cce9e31c7c509b0c5137ed622a18516da14253b025efeea81930666b` |

The guideline hash is of the **draft**, listed only so a later change is visible.
The frozen v1.1 gets its own row. Regenerate with `sha256sum <file>` after the open
decisions are closed.

## Evidence that no round-2 data existed at registration

- `data/processed/annotation/pilot2/` and `pilot3/`: every `rating` cell empty
  (checked 16 Nov 2026).
- No judge output exists for a round-2 or main-study packet.
- Round-1 labels (guideline v1.0) exist and are retired from evaluation.

## Signatures

| Role | Name | Date | Signature |
|---|---|---|---|
| Author | Prasad Devendra Watane | | |
| First supervisor | Prof. Dr. Swati Chandna | | |
| Second supervisor | Prof. Dr. Binh Vu | | |

Repository commit at signing: `________________`
