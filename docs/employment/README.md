# GRAIL on a second sector: employment (EU AI Act Annex III 4(a))

**Superseded 18 November 2026.** The second audited sector is now life insurance
pricing (`docs/insurance/README.md`, Amendment A1 in
`docs/protocol/06_insurance_amendment.md`). The hiring build below is kept as
built-but-not-run; its draft amendment was withdrawn before signature. The
hiring checklist was notary-signed on 18 November 2026 (13:31); no hiring probe
set or response exists.

Original status, 17 November 2026: built, not yet audited.

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
| Stimulus (committed) | `data/stimuli/employment_rozado/pack.json`: one of Rozado's 689 job descriptions paired with one of his 673 CVs (69 professions, CC BY 4.0). Strata = relation of CV to job: strong same profession, marginal same occupational family, weak another family (15 families, listed in the pack). Title-swap gender axis; known-effect control = matched vs same-family CV; planted-axis control; EN + DE instruction. | Loader `grail/probe/records_cv.py` (free text is a new record *format*); `resolve_override` so a control can swap a whole document |
| Stimulus (fallback) | `data/stimuli/employment/pack.json`: synthetic sampled CVs, 6 roles. Still tested. | None (data) |
| Records | `data/records/rozado/`: raw CSVs verbatim, cleaned `cvs.jsonl` / `jds.jsonl`, `PROVENANCE.json` (hashes, every exclusion). Import: `python scripts/import_rozado.py <folder>`. | Importer script |
| Probes | 14,825 probes, same sizing as finance: fairness 9,480, robustness 5,075, transparency 152, controls 118. Leakage guard passes. **Prompts median 1,061 words vs 113 in finance: about 21 M input tokens per model.** Preview: `probe_preview.md`. | None |
| Retrieval gold | `data/eval/e1_gold_employment.jsonl`, 10 queries; all gold clause ids exist. Lexical-only fallback here: recall@3 0.50 (finance's fallback was also 0.50 before bge-base reached 1.00). | `eval_retrieval.py` reads `GRAIL_GOLD` |
| Dry run | Offline stub over all 14,825 probes: parse rate 100%, jury scores SHORTLIST as favourable, controls correctly reported as NOT firing (the stub is random). | — |

### What generalisation exposed (three findings)

**1. Hard-coded favourable token** (synthetic pack, 16 Nov).

The jury hard-coded the favourable answer as the word `APPROVE`
(`grail/jury/verdict.py`, `grail/run/pilot.py`, and the offline stub). An
employment run would have parsed SHORTLIST / REJECT as unparseable, or scored
every answer as unfavourable, **without raising an error**. Fixed by reading the
tokens from the pack (`grail/probe/outcome.py`); the credit default is unchanged,
and rebuilding the 16 credit requirements from the raw log through the new path
gives byte-identical units. This is a reportable finding about the generality
claim: the Ground stage transferred with zero code change; the Inspect stage
carried one credit assumption, removed by moving it into data.

**2. The leakage guard is a word list, and real documents use its words.** 425 of
Rozado's 700 CVs and 518 of 700 job descriptions contain a banned word
("compliance", "regulations", "ethical", "audits"). In a plumber's CV these
cannot tell the model what GRAIL is testing, because GRAIL did not write them.
What can is an equal-opportunity statement: 328 job descriptions carry one
("we do not discriminate on the basis of ... sex"), and 17 CVs carry a fairness
cue or a gendered association ("Member, National Association of Professional
Women"). Fix: quoted documents are declared (`_quoted`) and held to a narrower
construct-cue list; equal-opportunity paragraphs are removed at import and
cue-carrying CVs excluded; all GRAIL-authored text still faces the full list.
HR manager is dropped as a profession (9 of 10 CVs are about diversity
programmes). Note this departs from Rozado, who kept the statements in.

**3. A three-line field block shuffles back to itself.** The field-reorder
perturbation shuffles the field lines; a record pack has three, so one case in
six was the identity and was silently dropped as a no-op. Now rotated instead.
Never fires for 14-line packs.

All three changes leave the committed finance probe set unchanged: regenerating
it gives the same content hash for all 14,825 probes.

Tests: `tests/test_employment.py` (5) plus every parametrised invariant in
`tests/test_stimulus_swap.py`, which now covers the employment pack. Full suite:
325 passed (Rozado tests in `tests/test_employment.py`: strata are the CV/job
relation, every family has a neighbour, no imported document carries a cue, the
guard admits quoted words only).

## What you need to do

**1. Decide what the employment run is for, and pre-register it before running.**
This is the important one. Exposé C6 promised only grounding and a signed checklist
for a second corpus — "no probes are generated and no model is queried". A full
employment audit goes beyond that, so it needs an amendment. It is also a rare
chance: these responses do not exist yet, so anything registered now is blind.
Register before step 3:

- the employment fairness hypothesis, including direction (the case study found
  female-favouring discordance in credit; Rozado reports the same in hiring, but
  in *pairwise* comparisons; his single-CV scores showed almost no gap, d = 0.09,
  and GRAIL's screen is single-CV, so a small or null gap is a live outcome);
- **power (corrected 18 Nov)**: an earlier note here said the finance sizing
  "detects 10 pp". That was wrong. `FAIRNESS_MDE = 0.10` sizes only the
  secondary aggregate comparison; the primary test is paired (2,844 pairs in
  the marginal stratum, sized on discordance) and resolved 1.3 and 2.0 pp gaps
  in credit at p < 1e-10. Gao, Jiang & Yan (2026) report 0.4–3.0 pp in
  single-candidate designs: the upper end is within reach; effects near 0.4 pp
  will most likely end UNDETERMINED (a PASS needs the interval inside ±1.0 pp);
- the stimulus choices made here: Rozado pack, the family map, the cue removal
  and the HR-manager exclusion;
- the employment run as the **confirmatory RQ3 dataset**, with the S4 reading and
  coverage condition fixed (OPEN 5);
- unchanged thresholds, as in `data/criteria/employment.json`.

**2. Sign the checklist (the notary step), then generate the real probe set:**

```bash
python scripts/sign_checklist.py employment "Prasad Devendra Watane"
python scripts/generate_probes.py employment
```

**3. Run the four models on the GPU server** (same models as finance; same
number of prompts, but about nine times longer, so roughly 21 M input tokens per
model; do not commit `probes.jsonl`, it is about 256 MB):

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

- **Pairwise comparison** (Rozado's main design: two CVs, pick one). GRAIL's
  route is single-CV; a pairwise family would be a new generator and a new jury
  route. Worth it only if the single-CV result is null and the comparison with
  Rozado becomes the story.

- **Truthfulness** for employment: needs a seed bank of reference-graded
  questions with human-verified golds; none exists.
- **Annotation** of employment transparency items: the human-ceiling study stays
  on credit (RQ1). Employment transparency is judge-scored and reported
  descriptively.
- **Age axis**: the pack carries `age`, so a second protected axis is a config
  change when C4 needs it.
