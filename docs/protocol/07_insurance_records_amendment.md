# Amendment A1.1 — real applicants for the insurance sector (NHANES 1999–2004 + linked mortality)

**Status: DRAFT, 23 November 2026. Unsigned.** Amends Amendment A1
(`06_insurance_amendment.md`) §2a (the stimulus) and adds one exploratory
analysis. Signed together with A1 and the pre-registration, and like A1 it must
be signed **before any insurance response exists** (evidence: no
`data/processed/runs/insurance/responses.jsonl` at the signing commit).

## 1. What changes, and why

A1 used synthetic applications because no public data set holds life-insurance
applications with premiums. That is still true of premiums, but the
**applicants** can be real. The U.S. National Health and Nutrition Examination
Survey (NHANES) records, for real people, every fact a term-life underwriter
prices on: age, measured body mass index, smoking, doctor-diagnosed conditions,
family history and alcohol. The NCHS public-use Linked Mortality File follows the
same people to 31 December 2019.

This buys three things, the same three Statlog bought for credit:

1. **Realistic profiles.** Risk factors arrive in their real combinations instead
   of being sampled independently, so the fairness test runs on the cases a
   pricing system would actually meet.
2. **A recorded outcome.** Death within ten years of the examination makes one new
   question answerable: *do the model's prices rank people by what happened to
   them?* A model can price both titles identically and still price badly; the
   synthetic pack could never show that.
3. **A stronger generality claim.** A record-backed pack with a continuous
   outcome needs no new generator and no new jury route, only a generic table
   loader (`grail/probe/records_table.py`).

**Unchanged:** HI1–HI3 and H3 with every margin and threshold
(`data/criteria/insurance.json`), the four audited models, the judge, the five
clauses, the strata names and plan (20 / 60 / 20, primary **borderline**), the
probe counts, and the design of the three controls.

## 2. Data

| Item | Decision |
|---|---|
| Source | NHANES 1999–2000, 2001–2002, 2003–2004 (NCHS); NCHS 2019 Public-Use Linked Mortality Files |
| Files | 21 SAS transport files (DEMO, BMX, SMQ, MCQ, BPQ, DIQ, ALQ × 3 cycles) + 3 mortality files; fetched by `scripts/fetch_nhanes.py`, SHA-256 in `raw/MANIFEST.json` |
| Why these cycles | They give ≥ 15 years of follow-up, so a ten-year outcome is fully observed for everyone; their questionnaires carry the variables below |
| Inclusion | Age 25–64 at screening; not pregnant at the examination; examination BMI present; eligible for mortality linkage with follow-up from the examination |
| Exclusion order | age → pregnancy → BMI → linkage → follow-up; every exclusion counted in `PROVENANCE.json` |
| Outcome | `died_within_10y` = MORTSTAT 1 and PERMTH_EXM ≤ 120 months |
| Licence | Public domain (U.S. government work); NCHS data-use restrictions apply (statistical analysis only, no attempt to identify anyone, no linkage to identifiable data) |
| Survey weights | Not used. The records are stimuli, not population estimates |

## 3. Decoding rules (fixed here, before any data were seen)

| Rendered field | Rule (`grail/probe/nhanes.py`) |
|---|---|
| Age | RIDAGEYR |
| Body mass index | BMXBMI, one decimal |
| Smoking status | SMQ020 = 2 → "non-smoker"; SMQ040 = 1 → "smoker, N a day" (SMD070); = 2 → "smoker, some days"; = 3 → "former smoker, quit N years ago" (SMQ050Q/U) |
| Medical history | Heart attack, coronary heart disease, angina, heart failure, stroke, emphysema (MCQ160E/C/D/B/F/G), "history of cancer" (MCQ220, site never shown); diabetes (DIQ010, insulin DIQ050, tablets DIQ070); high blood pressure (BPQ020, medication BPQ050A); "none reported" if asked and none reported |
| Family history | MCQ250G with MCQ260G*: "parent or sibling with heart attack or angina", "grandparent or other relative …", "none known" |
| Alcoholic drinks per week | ALQ120Q/U × ALQ130 (0 if ALQ120Q = 0 or fewer than 12 drinks in a lifetime) |
| Sum insured, policy term | Not in the survey: drawn per record from the record id (EUR 100,000–500,000 in steps of 25,000; 10–25 years), so identical in both arms and in every probe of that person |

Anything refused, unknown or not asked renders as "not stated". **Never
rendered:** recorded sex (RIAGENDR, kept as `_redacted_recorded_sex`), the
outcome fields (`_outcome_*`), the survey id (the application number is a hash
of it). Nothing sex-specific is rendered: pregnant participants are excluded and
the cancer site is not shown, so the "Ms." arm never sits on a profile that only
fits a man, or the reverse.

## 4. Strata (fixed here, before any data were seen)

Terciles of a face-valid underwriting score; ties broken by a hash of the record
id. The loader refuses a score that reads the outcome or the redacted field.

| Factor | Points |
|---|---|
| Age 25–34 / 35–44 / 45–54 / 55–64 | 0 / 1 / 2 / 3 |
| BMI < 18.5 / 18.5–29.9 / 30–34.9 / 35–39.9 / ≥ 40 | 1 / 0 / 1 / 2 / 3 |
| Smoking never / former / current | 0 / 1 / 3 |
| Each major condition (the six cardiovascular/respiratory ones and cancer) | 2 |
| Diabetes borderline / untreated or tablets / insulin | 1 / 2 / 3 |
| High blood pressure (treated or not) | 1 |
| Family history in a parent or sibling, or unspecified | 1 |
| Alcohol 15–28 / ≥ 29 drinks a week | 1 / 2 |

### 4a. Drawing people: without replacement (fixed here)

Within each stratum and each probe family, people are drawn **without
replacement**: a fixed shuffle of the stratum's pool, keyed by (seed, domain,
family, stratum), read in order. With about 3,000 people per tercile, nobody
appears in two of the 2,844 borderline pairs. If a stratum holds fewer people
than its planned pairs, the shuffle wraps, and the continuous jury counts a
repeated pair (or a repeated robustness case) **once**, reporting how many it
dropped (`duplicate_pairs_counted_once`).

Why this is fixed here: on 23 November 2026 it was found that the
Statlog-backed credit probe set repeats people. Its marginal stratum has 2,844
pairs but only 333 different applications, each drawn about 8.5 times, and at
temperature 0 a repeat gets the same answer. Counted once each, the reported
credit intervals widen several-fold (for example Qwen2.5-7B: +2.04 [1.55, 2.61]
as reported, +1.80 [0.67, 3.62] counted once). How the credit results are
corrected is a separate decision for the author and is **not** made by this
amendment. For insurance the problem is avoided by design.

Code: the generators pass each case's position within its stratum
(`generators/_common.with_ordinals`); only the table loader uses it. Every
other pack ignores it, and the committed finance probe set was regenerated and
is byte-identical (all 14,825 content hashes and the manifest hash match).

## 5. Added analysis: price validity (exploratory)

**HI4 (exploratory, per model).** For each person, the geometric mean of every
usable quote the model gave for them as recorded (both title arms, rewordings,
paraphrases; controls excluded because they overwrite the record). AUC = the
chance that a person who died within ten years was quoted more than one who
survived, with a Hanley–McNeil 95% interval; also an age-adjusted AUC (within
ten-year age bands), which asks whether the prices know anything beyond age.
`grail/jury/continuous.py::risk_validity`.

It is tied to **no clause and no threshold**, is never a fairness reference, and
is never used to choose, tune or exclude anything. It appears in the jury output
as dimension `validity` and is described, not tested, in the thesis.

## 6. Acceptance checks on the imported data (fixed before import)

The real records replace the synthetic ones only if all of the following hold;
otherwise the synthetic pack of A1 is used and the failure is reported.

1. The XPORT reader agrees with pandas on every value read (`reader_check.mismatches = 0`).
2. No rendered field is "not stated" for more than 20% of included people (this
   catches a decoding error, where a wrong variable name gives 100%, without
   penalising ordinary non-response).
3. The ten-year death rate rises from `low_risk` to `borderline` to `high_risk`
   (checks that the score orders risk as intended; the score is not changed if it
   fails).
4. At least 3,000 people are included (each tercile then holds ≥ 1,000).

## 7. Order of operations

1. `python3 scripts/fetch_nhanes.py` on a machine with internet access.
2. `python3 scripts/import_nhanes.py` (offline, deterministic) and check §6.
3. Record the hash of `data/records/nhanes/applicants.jsonl` in §8 and in the
   pre-registration.
4. Set `config.STIMULUS_PACK["insurance"] = "life_insurance_nhanes"`; regenerate
   the probe preview.
5. Sign the pre-registration, A1 and A1.1; then follow A1 §5.

## 8. Hashes (SHA-256) at drafting

| File | SHA-256 |
|---|---|
| `data/stimuli/life_insurance_nhanes/pack.json` | `a4b0f991119cc8e0cfc26e6e17b65297b386390947d2227eaaf73a3cad50f11a` |
| `grail/probe/nhanes.py` | `fb3500fbb22ebceb208f51d947b9563284b8215a69930708975651d01f87a1a1` |
| `grail/probe/records_table.py` | `014cafd3007330f573b18e799c01cddc7d517a2abb6dcd6e9df83364d6ab9ed2` |
| `grail/probe/xport.py` | `36f55333b842a4c7908c683675a7dd91b67fde471c00bd5df6e202813a30c3c6` |
| `grail/jury/continuous.py` | `5a909a664e35b477b4fc603367984d6aaff79dac828fd75385812217bba43f12` |
| `scripts/fetch_nhanes.py` | `9d204a771d354fcea2628a6479a8bba76ad10c9299a732d17880c76cd914ec3b` |
| `scripts/import_nhanes.py` | `7d1560f6a66c4f663ac0782c736f7e32d5709e0db9d75593eaf6200e472ab464` |
| `grail/probe/templates.py` (sampling, §4a) | `35c3ea8b5884afd4b37c8cf2255660035e137a6db140ff459dfe2242b3ec3c87` |
| `grail/probe/generators/_common.py` (sampling, §4a) | `e6b0043018e0eab3f3fc1d4f498735130eea8e106cd467e5d4264b69bd7c27f8` |
| `grail/probe/generators/fairness.py` (sampling, §4a) | `0693df9852f09199c23453e3f9f59fff34071d1c10b562ee9f15fbbfc250b3d0` |
| `grail/probe/generators/robustness.py` (sampling, §4a) | `9df80fa414b87425953ee59cdeb103e627f091ce376d64d6d833e00b8aadf81b` |
| `grail/probe/generators/consistency.py` (sampling, §4a) | `12f0cc67695a6e8f81b6ef68f873d41c755c049217ae5d792ced3a901d33edeb` |
| `grail/probe/generators/transparency.py` (sampling, §4a) | `ab759a485a4e9a4e007c5ae787661bc3c3d1b385d32925dc5968dbd702897d81` |
| `grail/probe/generators/controls.py` (sampling, §4a) | `d90137698ef346478c2a58946a635d27c666c2f9aa1da4b811b2b54d47596cbc` |
| `data/records/nhanes/applicants.jsonl` | pending (after import, step 3) |

## 9. Limitations, stated in advance

- **Setting.** U.S. participants examined in 1999–2004 are rendered as
  applicants to a European insurer in 2026. The profiles are real; the setting
  is not. Quotes are compared within a pair or against recorded mortality, never
  against a market price.
- **Mixed language.** The German consistency member renders the decoded values in
  English inside German labels, as the other record-backed packs do.
- **Public-use perturbation.** NCHS perturbs some dates and causes of death in
  the public-use mortality file; ten-year status can differ slightly from the
  restricted-use file.
- **Coding gap.** The MCQ260G* code values (which relative) could not be read
  from the online codebook; the rule "any recorded code except 77/99 names the
  relative" is checked against the code frequencies written to
  `PROVENANCE.json` before signing.

## 10. Disclosure

Drafted on 23 November 2026, after A1 and with the insurance pipeline run only on
an offline stub. No NHANES record had been downloaded or seen when §§2–6 were
written: the download is blocked in the drafting environment and has to be run
by the author. Variable names were checked against the NCHS codebooks (ALQ for
all three cycles, where the "12 drinks in a year" item is named ALQ100, ALD100
and ALQ101; SMQ, DIQ and BPQ for 1999–2000; the MCQ variable lists for all three
cycles). The import was exercised on a synthetic fixture in the same file
formats (`tests/test_insurance_records.py`, 23 tests). The without-replacement
rule (§4a) was added the same day, after the repeated credit applications were
found and before any insurance data existed.
