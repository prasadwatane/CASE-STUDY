# GRAIL on a second sector: employment (EU AI Act Annex III 4(a))

Status 17 November 2026: **built and dry-run, not yet audited.** Everything up to
the model run is in place. Two steps are yours: the notary signature, then the
GPU sweep.

## Why employment

Chosen over life/health insurance on the literature (see the 17 Nov notes):
paired-name LLM audits are densest in hiring, so results can be compared with
published ones (Wilson & Caliskan 2024; FAIRE 2025; Iso et al. 2025; Rozado 2025,
who reports LLMs favouring female-named candidates across 70 professions; "Can
LLMs Hire Fairly?" 2026). The four-fifths rule is an employment standard. Annex
III 4(a) names recruitment explicitly. The outcome is binary, so the existing
jury route applies unchanged.

## What was done

| Stage | Result | Code change? |
|---|---|---|
| Ground | Same parsed Act (1,143 units). Draft checklist `data/processed/checklists/employment_draft.json`: the same five obligations as finance (Art 10(2)(f), 10(2)(g), 13(1), 15(1), 15(4)). Anchor clause `AIA:AnnexIII(4)(a)` present. | **None** — `derive_checklist.py employment` ran as is |
| Criteria | `data/criteria/employment.json` = finance criteria **unchanged** (test-enforced). Same thresholds is the generalisation claim. | None |
| Stimulus | `data/stimuli/employment/pack.json`: synthetic CVs, 6 roles, 3 strata (strong / marginal / weak by experience, requirements met, employment gap), title-swap gender axis, known-effect control on "requirements met", planted-axis control, EN + DE. | None (data) |
| Probes | 14,825 probes, same sizing as finance: fairness 9,480, robustness 5,075, transparency 152, controls 118. Leakage-guard hits: 0. Preview: `probe_preview.md`. | None |
| Retrieval gold | `data/eval/e1_gold_employment.jsonl`, 10 queries; all gold clause ids exist. Lexical-only fallback here: recall@3 0.50 (finance's fallback was also 0.50 before bge-base reached 1.00). | `eval_retrieval.py` reads `GRAIL_GOLD` |
| Dry run | Offline stub over all 14,825 probes: parse rate 100%, jury scores SHORTLIST as favourable, controls correctly reported as NOT firing (the stub is random). | — |

### The one thing generalisation exposed

The jury hard-coded the favourable answer as the word `APPROVE`
(`grail/jury/verdict.py`, `grail/run/pilot.py`, and the offline stub). An
employment run would have parsed SHORTLIST / REJECT as unparseable, or scored
every answer as unfavourable, **without raising an error**. Fixed by reading the
tokens from the pack (`grail/probe/outcome.py`); the credit default is unchanged,
and rebuilding the 16 credit requirements from the raw log through the new path
gives byte-identical units. This is a reportable finding about the generality
claim: the Ground stage transferred with zero code change; the Inspect stage
carried one credit assumption, removed by moving it into data.

Tests: `tests/test_employment.py` (5) plus every parametrised invariant in
`tests/test_stimulus_swap.py`, which now covers the employment pack. Full suite:
318 passed.

## What you need to do

**1. Decide what the employment run is for, and pre-register it before running.**
This is the important one. Exposé C6 promised only grounding and a signed checklist
for a second corpus — "no probes are generated and no model is queried". A full
employment audit goes beyond that, so it needs an amendment. It is also a rare
chance: these responses do not exist yet, so anything registered now is blind.
Register before step 3:

- the employment fairness hypothesis, including direction (the case study found
  female-favouring discordance in credit; Rozado reports the same in hiring);
- the employment run as the **confirmatory RQ3 dataset**, with the S4 reading and
  coverage condition fixed (OPEN 5);
- unchanged thresholds, as in `data/criteria/employment.json`.

**2. Sign the checklist (the notary step), then generate the real probe set:**

```bash
python scripts/sign_checklist.py employment "Prasad Devendra Watane"
python scripts/generate_probes.py employment
```

**3. Run the four models on the GPU server** (same models as finance; about as
many prompts as the finance sweep):

```bash
HF_TOKEN=... GIT_TOKEN=... nohup bash scripts/run_models.sh employment &
```

**4. Score and report:**

```bash
python scripts/run_jury.py employment --model <id>          # per model
python scripts/run_judge.py employment --model <id> --local # transparency
python scripts/run_report.py employment
GRAIL_GOLD=e1_gold_employment.jsonl python scripts/eval_retrieval.py   # with bge-base
python scripts/eval_sequential.py employment --part replay   # confirmatory RQ3, after registering
```

## Not in scope here

- **Truthfulness** for employment: needs a seed bank of reference-graded
  questions with human-verified golds; none exists.
- **Annotation** of employment transparency items: the human-ceiling study stays
  on credit (RQ1). Employment transparency is judge-scored and reported
  descriptively.
- **Age axis**: the pack carries `age`, so a second protected axis is a config
  change when C4 needs it.
