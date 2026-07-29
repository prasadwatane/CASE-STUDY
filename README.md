# GRAIL — Ground + Auto-Probe (through the probe generator)

GRAIL's auto / self-evolving audit runs **Ground → Reason/Act → Inspect → Loop**.
Built so far: **Ground** — take a domain's official standards, turn them into
precise legal units, index them, retrieve the relevant obligations at evaluation
time, and freeze a human-signed checklist at the notary gate — and **Reason/Act**
— generate immutable, seeded behavioural probes from that signed checklist.

Jury, judge, conformal gate and ledger come later and sit on top of this without
changing it. A domain is data (corpus + config + gold), never control flow.

## The one architectural rule this repo enforces

**Clauses are extracted by deterministic structural parsing, NOT by RAG.**

RAG is used *later*, at evaluation time, to retrieve the relevant obligations
(plus definitions and exceptions) for a target document. For the EU AI Act the
smallest legal unit is **Article → Paragraph → Point** (e.g. `Article 10(2)(b)`),
and obligations are stored at that granularity so compliance checking is precise
rather than page/token-chunk fuzzy.

```
official PDF
   │  loaders.py     : pdftotext + clean OJ layout (drop preamble/furniture)   ← mechanical
   │  clause_parser  : deterministic Article→Paragraph→Point parse             ← NO model, NO RAG
   ▼
legal units at Article→Paragraph→Point granularity
   │  linker.py      : attach definitions + exceptions
   │  scope/         : partition behavioral | hybrid | procedural
   ▼
hybrid index (index/): bge-small dense + BM25 sparse → RRF fusion
   │
   ▼
eval-time retriever (retrieve/)  ← THIS is the RAG step
   given a target document → obligations + their definitions + exceptions
```

## Folder structure

```
grail-audit/
├── config.py                  paths, model, retrieval knobs, scope overrides
├── requirements.txt
├── data/
│   ├── standards/raw/         source standards
│   │   ├── OJ_L_202401689_EN_TXT.pdf   the official EU AI Act
│   │   └── eu_ai_act_excerpt.txt       small seed excerpt (fallback/tests)
│   └── processed/             clauses.jsonl + persisted index (generated)
├── grail/
│   ├── ingest/
│   │   ├── schema.py          LegalUnit dataclass + metadata schema
│   │   ├── loaders.py         PDF extraction + OJ-layout cleaning
│   │   ├── clause_parser.py   DETERMINISTIC Article→Paragraph→Point parser
│   │   └── linker.py          link obligations ↔ definitions ↔ exceptions
│   ├── scope/partition.py     behavioral | hybrid | procedural tagger (heuristic)
│   ├── index/
│   │   ├── embedder.py        bge-small (auto-fallback to hashing offline)
│   │   ├── sparse.py          BM25 (+ pure-python fallback)
│   │   └── hybrid_index.py    build/persist/search with RRF fusion
│   ├── retrieve/retriever.py  eval-time RAG: obligations + defs + exceptions
│   ├── ground/
│   │   ├── checklist.py       derive a DRAFT checklist from committed clauses
│   │   └── notary.py          sign / verify / require_signed (SHA-256 freeze)
│   └── probe/
│       ├── schema.py          Probe/ProbeSet, leakage guard, freeze + manifest
│       ├── sizing.py          power calc behind the CORE sample sizes
│       ├── templates.py       neutral stimuli, case sampler, perturbations
│       ├── generate.py        signed checklist → probe set (gate runs first)
│       └── generators/        one per dimension, selected by the checklist
├── scripts/
│   ├── build_index.py         raw → parse → link → index
│   ├── query.py               retrieve for a target-document snippet
│   ├── derive_checklist.py    auto-derive the DRAFT checklist
│   ├── sign_checklist.py      notary gate: sign / verify
│   └── generate_probes.py     signed checklist → frozen CORE probe set
└── tests/                     parser, retriever, notary, probe tests (37 passing)
```

## Metadata carried on every legal unit

`id` (stable, e.g. `AIA:Art10(2)(b)`) · `citation` (`Article 10(2)(b)`) ·
`article`/`annex`/`paragraph`/`point`/`subpoint` · `heading` · `parent_id`
(chapeau link) · `unit_type` (obligation / definition / exception / scope /
chapeau) · `defined_term` · `scope_partition` · `authority` · `tier` (1 = AI Act,
2 = domain legal layer) · `lang` · `related` (linked definitions/exceptions).

## Corpus: the real EU AI Act

`data/standards/raw/OJ_L_202401689_EN_TXT.pdf` is the official Act (OJ L
2024/1689). `grail/ingest/loaders.py` extracts it (poppler `pdftotext`, with a
`pdfplumber` fallback) and cleans the OJ layout before parsing:

- slices from `HAVE ADOPTED THIS REGULATION` (drops the preamble + 180 recitals),
- strips page furniture injected mid-paragraph (`NN/144`, `ELI:` url, running
  `EN` and `OJ L, 12.7.2024` headers),
- drops `CHAPTER` / `SECTION` / `TITLE` structural headings.

The deterministic parser then handles the OJ's real quirks: **paragraph numbers
on their own line** (`1.` then the text on the next line), **definitions numbered
`(1)…(68)`** in Article 3, letter points `(a)`, and roman sub-points `(i)`.

Current build from the full Act: **1143 legal units** — 941 obligations,
88 chapeaux, 69 definitions, 37 exceptions, 8 scope statements. The finance
anchors parse correctly: `Article 10(2)(f)/(g)` (bias), `Article 13(1)`
(transparency), `Article 15(1)` (accuracy/robustness), `Annex III(5)(b)`
(creditworthiness — typed as an exception because of the fraud carve-out), and
`Annex III(4)` (employment — your second domain, already in the same file).

## Run it

```bash
pip install -r requirements.txt          # or: numpy rank-bm25 pytest
python scripts/build_index.py            # ingests the PDF if present, else seed .txt
python scripts/query.py "the AI system evaluated an applicant's creditworthiness and may be biased"
pytest -q tests/
```

`build_index.py` prefers a `*.pdf` in `data/standards/raw/`; if none is present
it falls back to the seed `*.txt`. Drop any domain's standards PDF in that folder
and rebuild — no code changes (the domain is data).

Embeddings: the real backend is `bge-small-en-v1.5` (used automatically if
`sentence-transformers` + the model are available). Offline it falls back to a
deterministic hashing vector so the pipeline and tests still run — set
`GRAIL_EMBED=sbert` to force the real model, `GRAIL_EMBED=hashing` to force
fallback.

## Scope partition (why procedural clauses are stored but never probed)

GRAIL derives requirements only from **behavioral** and **hybrid** clauses.
Procedural clauses (record-keeping, technical documentation — e.g. Art 11, 12)
are parsed and indexed for context but are excluded from the primary retrieval
set, so they never become an obligation to probe. The heuristic tagger is a
first pass; `config.SCOPE_OVERRIDES` holds the human-signed values, and the final
partition is fixed at the notary gate.

## Retrieval evaluation (Gate A / S1)

`scripts/eval_retrieval.py` scores retrieval against a gold query→clause set
(`data/eval/e1_gold.jsonl`) and reports recall@k + MRR. Compare models:

```bash
GRAIL_EMBED_MODEL=BAAI/bge-base-en-v1.5  python scripts/eval_retrieval.py
GRAIL_EMBED_MODEL=BAAI/bge-large-en-v1.5 python scripts/eval_retrieval.py
```

Measured (10 finance gold queries): bge-base recall@3 = 1.00; bge-large ties it,
so **bge-base is the committed default** (smaller, no accuracy loss). Grow the
gold set to ~30–50 before quoting a headline number.

## Notary gate (the trust root) — built

Auto-derivation is not trusted blindly: a human signs and freezes the derived
checklist, and no audit stage may run on an unsigned or altered one.

```bash
python scripts/derive_checklist.py finance             # auto-derive DRAFT
#   → review/edit data/processed/checklists/finance_draft.json
python scripts/sign_checklist.py finance "Your Name"   # sign + freeze (SHA-256)
python scripts/sign_checklist.py finance --verify      # re-check anytime
```

`grail/ground/notary.py: require_signed()` is the enforcement point — it raises
if the checklist is missing, unsigned, or its content no longer matches the
signature (tamper-evident). Every downstream stage calls it first. `config.py`
holds the committed finance clauses and the clause→dimension map confirmed at
the gate.

## Auto-probe (Reason/Act) — built

Probes are generated **from the frozen, signed checklist**, never from the corpus
directly. `require_signed()` runs before a single probe exists, and the checklist
signature is carried into the probe manifest, so every later finding traces back
finding → probe → requirement → clause → the exact text the notary approved.

```bash
python scripts/generate_probes.py finance            # signed checklist → probes
python scripts/generate_probes.py finance --verify   # regenerate, compare hashes
python scripts/generate_probes.py finance --only fairness --seed 123
```

Output goes to `data/processed/probes/<domain>/` as `probes.jsonl` plus a
`manifest.json` recording the seed, generator version, checklist SHA-256 and a
content hash. Probes are immutable: regenerating an identical set is fine,
overwriting a different one needs `--force`.

**The system under audit never sees the law.** `schema.assert_no_leakage` runs on
every probe at construction and refuses any prompt containing legal or audit
vocabulary — a runtime invariant, not just a test. Probes read as ordinary retail
banking work.

**Which generators fire is data.** A checklist item carries a dimension, and that
dimension selects a generator from the registry. The committed finance checklist
activates three; a dimension with no generator is reported in the manifest as a
coverage gap rather than silently skipped, and procedural items are dropped with
an explicit note.

| dimension | family | design |
|---|---|---|
| fairness | `credit_application` | counterbalanced pairs, stratified by credit strength |
| robustness | `perturbed_application` | 6 meaning-preserving perturbations per base case |
| transparency | `explanation_request`, `counterfactual_request` | judge-scored, not jury-scored |
| consistency | `paraphrase_set` | 3 EN paraphrases + a hand-written DE rendering |
| truthfulness | seeded question bank | false-premise / nonexistent-entity / numeric traps × neutral, scenario, sycophancy framings |

Current finance run: **3492 prompts over 1097 independent cases** — fairness
1310/655, robustness 2030/290, transparency 152/152. Counts are reported in
*cases*, not prompts: a pair rendered twice is one case, and counting prompts
would make the set look several times better powered than it is.

### Sizing: powered for the test actually run

Fairness compares two rates, so it is sized with the two-proportion power
calculation, not the single-rate margin. The distinction is not cosmetic — an
earlier version of this repo sized fairness on `n = z²p(1−p)/e²`, which is the
margin on *one* rate and under-powers a difference by about a factor of four. A
real gap would have been reported as "no significant difference".

```
n per arm = 2 (z_α/2 + z_β)² p̄(1−p̄) / d²      p̄ = 0.5 (worst case)
```

**One primary endpoint is pre-registered:** the approval-rate gap in the
*marginal* credit stratum. Strong and weak applications sit near the ceiling and
floor and carry little information about differential treatment, so they are
controls — a gap appearing there too would indicate blanket rather than marginal
bias. Declaring a single primary endpoint is also what keeps the analysis free of
a multiplicity correction; the control strata are reported descriptively with
their wider intervals and are not formally tested.

| stratum | pairs/arm | detectable gap (80% power) |
|---|---|---|
| **marginal** (primary, 60%) | 393 | **10.0 pp** |
| strong (control, 20%) | 131 | 17.3 pp |
| weak (control, 20%) | 131 | 17.3 pp |

Robustness sizing is contingent rather than fixed: McNemar needs 29 discordant
pairs to detect a 3:1 flip asymmetry, but how often a perturbation flips a
decision at all is unknowable before a pilot. At an assumed 10% flip rate that is
290 base cases; at 5% it would be 580. The assumption is recorded in config and
travels with the numbers instead of hiding inside them.

Every size in `config.PROBE_CORE_N` is derived at import from
`grail/probe/sizing.py` — change a threshold and the sample sizes follow.

### Why the fairness probes are testable, not just plausible

A measured group gap is only about the system under audit if the probe set itself
is clean. Two invariants, both enforced in code and re-checked in tests:

- the applicant profile RNG is derived from the case key and **never** from the
  arm, and `_assert_counterbalanced` raises if two arms of a pair differ in
  anything but the axis slot — that is the slot-to-group mapping bug, caught at
  generation rather than discovered in the results;
- perturbations must leave the prompt's digit multiset unchanged, so a
  perturbation that quietly altered a number cannot reach a probe file.

The tests then score the generated set twice. A scorer **blind** to the protected
arm must produce a gap of exactly 0.0 (anything else means a profile slot tracks
the arm), and a scorer with a **known injected bias** in the marginal stratum must
show that bias, localised to that stratum. A probe set that cannot detect a bias
put there deliberately could not detect a real one.

Golds are never invented here. Truthfulness probes carry `reference: null`,
`reference_status: "pending"` and a `gold_route` (`computed` / `sourced` /
`structural`) for the gold pipeline to honour — a reference written at generation
time would be exactly the uncertified "trust me" gold the design rules out.

## Gold pipeline (Green / Amber) — built

Every reference answer is obtained one of two ways, and the record says which.

**Green** — obtained without trusting a model. Either computed by a solver in
`grail/gold/formulas.py`, with the formula name and its arguments recorded so
anyone can redo the arithmetic by hand, or extracted from a primary source with a
locator a human signed off. A Green gold is reproduced, not believed.

**Amber** — proposed by a model and accepted by a conformal gate, carrying the
raw proposals, the disagreement score, the threshold and a certified error bound.

Anything the gate cannot accept is **escalated**: no gold yet, queued for a human.
That is a normal outcome, and the share of items in it is the *bounded leakage*
the design promises — measured, not asserted.

```bash
python scripts/build_golds.py finance --probes <probes.jsonl> --stub
python scripts/build_golds.py finance --verify        # check the ledger hash chain
```

### A-then-B, and why the gate usually refuses

Items with a compute spec are solved first and cost nothing. Their labels are
then free calibration data for everything else: run the proposer on them, record
`(disagreement, was it right)`, and choose the largest threshold whose selective
error is provably at or below α.

The bound is exact Clopper–Pearson, and because the threshold is chosen by
searching every candidate, each test uses δ/m (Bonferroni over the m candidates)
so the guarantee holds simultaneously rather than being the luckiest cut.

The consequence is arithmetic, and it is the useful finding of this stage:

> With zero observed errors, the exact bound from n calibration points is
> 1 − δ^(1/n), which first reaches α at n = log δ / log(1−α). For α = δ = 0.05
> that is **59 points**. The seed bank supplies 6.

So on the current bank the gate certifies nothing, every non-computed item
escalates, and the split is **6 Green / 0 Amber / 14 escalated — 70% leakage**.
That is the correct output, not a broken one: the alternative is quoting a 5%
error bound that 6 points cannot support. It also puts a number on how much the
seed bank has to grow before Amber golds are available at all.

### What the pipeline refuses to do

- **No model near a number.** Computed golds never call a proposer; the tests
  assert that no Green record has a proposer anywhere in its provenance.
- **No gold without provenance.** `GoldRecord` raises on construction if a
  green/amber record has an empty provenance dict.
- **No stub silently passing as evidence.** `StubProposer` keeps CI runnable
  offline, but the router refuses to build a ledger from it unless `allow_stub`
  is passed, and its name stays in every record it touched.
- **No editing the ledger.** Rows are hash-chained, and a `.head` anchor records
  the tail so truncation is caught too — a shortened chain still verifies on its
  own, which is exactly why the anchor exists.

## What plugs in next (not in this repo yet)

1. **Courtroom Inspect** — deterministic jury + gated LLM judge.
2. **Ledger + report** — clause-traced, evidence-typed findings.
3. **Generalisation** — re-sign on the insurance corpus, no code change.

## Notes / limitations

- **Ranking needs the real embedder.** The offline hashing fallback is lexical
  only; real ranking uses bge-base (sentence embeddings). Measured recall@3 = 1.00
  on the 10-query finance gold set — grow that set before quoting a number.
- The scope-partition tagger is heuristic; the human-signed partition governs.
- A cross-encoder reranker hook is noted in `requirements.txt` but not yet wired.
- **Truthfulness is underpowered and knows it.** The seed bank holds 20 items
  against a target of 300; the manifest flags the shortfall. No truthfulness
  clause is in the committed finance checklist yet, so the generator is present
  but inactive for this domain.
- **One protected axis is committed** (gender, via the applicant title, so a pair
  differs by exactly one token). Adding an age or nationality axis is a config
  change; each axis costs a full CORE sample.
- Probes have not yet been run against a model — the generator is measured
  structurally (counterbalancing, determinism, leakage), not yet against
  hand-written probes. That comparison is the contribution and is still to come.
