# GRAIL — clause-traced audits of LLMs under the EU AI Act

GRAIL turns clauses of the EU AI Act (Regulation 2024/1689) into signed, testable
requirements, sends language models controlled prompts, and scores the answers
with exact statistics. Every requirement ends as **PASS**, **FAIL** or
**UNDETERMINED**, with an interval and the clause it came from.

Master's thesis of Prasad Devendra Watane, SRH Hochschule Heidelberg
(supervisors Prof. Dr. Swati Chandna, Prof. Dr. Binh Vu; submission March 2027).

## Research questions

**Main question.** How can LLMs be audited against the EU AI Act validly, cheaply
and across sectors?

| | Question | Hypothesis (pre-registered) |
|---|---|---|
| **RQ1** Early stopping | Can early stopping with O'Brien–Fleming correction reach the same verdicts as the full audit while spending at most 80% of its prompts? | H1: fidelity ≥ 0.90, coverage ≥ 0.90 and spend ≤ 0.80 of the full audit, over 40 seeds |
| **RQ2** Carry-over | Can GRAIL audit life-insurance pricing (Annex III 5(c)) against the same five clauses as credit by changing only data, plus one new way to score a price? | H2: no code change in Ground, ≥ 95% readable prices, both controls fire |
| **RQ3** Ms./Mr. pricing | Do real NHANES applicants get a different premium depending only on the title? | H3a paired gap within ±1%; H3b a group check misses it; H3c < 20% of applications change by > 5% when reworded |

**Calibration of the explanation check (not research questions).** CAL1: two
raters label 240 insurance explanations; lower 95% bound of AC1 ≥ 0.61.
CAL2 (if CAL1 is met): the LLM judge against the raters and a certified
selective error ≤ 5%. CAL3 (optional): judge robustness.

Full registration: `docs/protocol/PREREGISTRATION.md` and Amendment A2
(`docs/protocol/09_amendment_A2_final_scope.md`). Both are unsigned drafts.

## Status (25 November 2026)

| Part | Status |
|---|---|
| Credit case study (Annex III 5(b)), 4 models, 61,259 answers | Done; corrected for repeated applicants (C1). Development data and baseline. |
| RQ1 on credit (development) | O'Brien–Fleming: fidelity 1.00, coverage 1.00, spend 0.87 → target not met; insurance is the real test |
| Life insurance on NHANES (RQ1 confirmatory, RQ2, RQ3) | Built and tested; waiting for the pre-registration signature and the GPU run |
| CAL1 human agreement | Tooling ready; runbook `docs/runbook_human_agreement.md` |

Credit results (each applicant counted once): Qwen2.5-7B FAIL, +1.80 pp
[0.67, 3.62], 6 of 6 discordant applicants favour "Ms."; Llama-3.1-8B FAIL by the
interval rule (exact p = 0.063, open point); Qwen2.5-32B and Llama-3.1-70B
UNDETERMINED. The four-fifths rule passes all four models on the same answers.

## How it works

```
Ground    AI Act PDF → 1,143 legal units → hybrid retrieval → draft checklist
          → a person signs it (SHA-256 notary gate)
Act       signed checklist + stimulus pack (the sector, as data) → seeded probes
          → models (vLLM, T = 0) → hash-chained response log
Inspect   jury: exact tests for anything countable (McNemar, paired log-ratio, TOST)
          judge: phi-4 for explanations, only as far as the calibration allows
Loop      ledger → report that says "conforms to the requirement derived from
          Article X", never "complies"
```

## Repository layout

```
config.py                 domains, clauses, stimulus packs, analysis plan
grail/
  ingest/ scope/          parse the Act into legal units; behavioural vs documentary
  index/ retrieve/        dense + BM25 hybrid index and retriever
  ground/                 checklist and notary (sign, freeze, verify)
  probe/                  probe generator, stimulus packs, record loaders (German Credit, NHANES)
    generators/           fairness, robustness, transparency, controls, consistency, truthfulness
  run/                    model clients (vLLM, HTTP, stub), runner, response log
  jury/                   verdicts: binary route (credit) and continuous route (premiums)
  allocate/               RQ1: sequential allocation and replay
  judge/ gate/            LLM judge, rule-based baseline, selective gate (CAL2)
  annotate/               agreement statistics, CAL1 study, rater packets
  gold/                   gold-reference pipeline
  ledger/ report/         findings ledger and report
scripts/                  command-line entry points (see below)
data/
  criteria/               what "conforms" means per clause (finance, insurance)
  stimuli/                stimulus packs: credit_real, life_insurance_nhanes (+ synthetic fallbacks)
  records/                German Credit; NHANES is downloaded by scripts/fetch_nhanes.py
  processed/              checklists, probe manifests, response logs, annotation
docs/                     protocol, annotation guidelines, runbook, reports (see docs/README.md)
thesis/                   LaTeX source and PDF
tests/                    pytest suite
```

## Run it

```bash
pip install -r requirements.txt
pytest -q                                            # 352 tests

# credit (replication of the case study)
python scripts/sign_checklist.py finance --verify
python scripts/run_jury.py finance --model <model>
python scripts/eval_sequential.py                    # RQ1 development replay
python scripts/run_report.py finance --fresh

# life insurance on NHANES
python scripts/fetch_nhanes.py && python scripts/import_nhanes.py
python scripts/derive_checklist.py insurance
python scripts/sign_checklist.py insurance "Your Name"
python scripts/generate_probes.py insurance
bash   scripts/run_models.sh insurance               # on the GPU server

# CAL1 human agreement (explanations only)
bash   scripts/run_models.sh insurance --dimension transparency
python scripts/human_agreement.py export insurance
python scripts/human_agreement.py calibration insurance
python scripts/human_agreement.py score insurance
```

Models are listed in `data/audit_models.txt`. On the college server start with
`scripts/bootstrap_server.py`.

## Limitations

- One protected axis (gender, via the title "Ms."/"Mr."); age is an option.
- Output-only audit: bias that does not change the answer is not seen.
- German Credit is 1994 period data; no accuracy claim is made against its labels.
- Two credit criteria were amended after results were known; both are dated in
  `docs/protocol/criteria_amendment_*.md` and both verdicts are reported.
- The longer case-study write-up is kept in `docs/archive/README_case_study_2026-11.md`.
