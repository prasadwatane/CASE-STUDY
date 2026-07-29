---
name: grail-dev
description: Build and extend the GRAIL foundation-model audit pipeline (the grail-audit repo): clause parser, retrieval, notary gate, auto-probe, deterministic jury, gated LLM judge, conformal gate, annotation study, and sub-sector generalisation. Use when implementing, testing, or extending any GRAIL audit stage, or continuing the credit/insurance instantiation — even without the word "GRAIL".
---

# GRAIL — Development Skill

Implementation guide for building and extending **GRAIL (Grounded Responsible AI
Audit Loop)** — a standards-grounded audit that tests foundation models against
EU-AI-Act obligations with clause-traceable findings and a certified,
confidence-gated judge. Master's thesis (Prasad Devendra Watane / SRH Heidelberg;
supervisor Prof. Dr. Swati Chandna). This skill is for *writing the code*; keep
the design fixed and add stages in order. The user is terse and prefers honesty
over praise: prompt his own position on open design questions before answering;
act directly when he asks for an artifact.

## Fixed design (do NOT redesign per request)

Loop: **Ground → Reason → Act → Inspect → Loop**. The loop, jury, judge, gate,
ledger and notary NEVER change per domain — a domain is data, not control flow.
Editing the audit graph to make a domain work is a design smell; stop and make it
data instead.

- **Ground** — deterministic structural parse of the standards (Article→Paragraph
  →Point), NOT RAG. Retrieval derives clause-traceable requirements; a human signs
  and freezes the checklist (notary gate).
- **Reason/Act** — auto-generate probes from the *signed* obligations; the system
  under audit never sees the law.
- **Inspect** — a deterministic **jury** (code, no LLM near numbers) scores
  quantitative dimensions; a **gated LLM judge** scores qualitative ones.
- **Loop** — terminate on evidence coverage at confidence, or budget; every
  finding is clause-traced and evidence-typed (jury / judge+confidence / human).

RAG is used only at evaluation time to retrieve obligations (+ definitions +
exceptions) for a target document — never to extract clauses.

## Current state (what is already built and tested)

Working repo `grail-audit` (Python). Ground stage is complete:

- `grail/ingest/` — `loaders.py` (pdftotext + pdfplumber fallback, OJ-layout
  cleaning), `clause_parser.py` (deterministic Article→Paragraph→Point;
  parenthesised-digit definitions, roman sub-points, bare paragraph numbers),
  `linker.py` (obligations ↔ definitions/exceptions), `schema.py` (LegalUnit).
- `grail/scope/partition.py` — behavioral | hybrid | procedural tagger.
- `grail/index/` — `embedder.py` (bge-base-en-v1.5, hashing fallback offline,
  query-instruction prefix), `sparse.py` (BM25 + pure-python fallback),
  `hybrid_index.py` (RRF fusion, exact/flat search — no vector DB, no HNSW).
- `grail/retrieve/retriever.py` — eval-time RAG returning obligations + defs + exceptions.
- `grail/ground/` — `checklist.py` (derive draft), `notary.py` (sign / verify /
  `require_signed()`), tamper-evident SHA-256 freeze.
- `scripts/` — `build_index.py`, `query.py`, `eval_retrieval.py`,
  `derive_checklist.py`, `sign_checklist.py`.
- Results: full EU AI Act parses to ~1143 legal units; retrieval measured at
  **recall@3 = 1.00** on a 10-query finance gold set (bge-base chosen over
  small/large by measurement). 12 tests pass.

Committed domain: banking / consumer credit (EU AI Act Annex III 5(b)). Second
sub-sector for generalisation: insurance (5(c)).

## Non-negotiable rules

- The LLM never computes or aggregates numbers — all statistics are deterministic code.
- No audit runs on an unsigned or tampered checklist (`require_signed()` first).
- Headline stats come from pre-registered CORE samples only; adaptive probes are a
  labelled diagnosis stream, never in headline numbers.
- Probes immutable + seeded; supervisor routing deterministic; judge version pinned,
  both-order scoring, canary drift test (McNemar).
- Ledger append-only: every finding carries clause ID + evidence type + sample kind.
- Derive requirements only from behavioral + hybrid clauses; procedural is out of scope.
- Never claim "complies with the EU AI Act" — claim conformance to a requirement
  DERIVED from an article by a documented, human-verified interpretation.
- Every gold answer is Green (extracted from a primary source, with provenance) or
  Amber (model-proposed, conformally measured) — never a "trust me" gold.
- Negative results are findings (S4): a dimension shown NOT reliably automatable,
  with quantified evidence, is a valid result.

## Build order for the remaining stages (each has a gate)

1. **auto-probe** — generate behavioural probes from the frozen, signed
   obligations. Fairness (credit): counterbalanced loan applications varying a
   protected attribute, stratified by credit strength. Truthfulness:
   reference-graded questions incl. false-premise / nonexistent-entity / numeric
   traps, in neutral / scenario / sycophancy framings. Robustness:
   meaning-preserving perturbations. Consistency: paraphrase + DE/EN sets. Probes
   immutable + seeded + cached; never reference the law or the word "audit". Add a
   unit test on an injected-bias synthetic (the slot→group mapping bug).
2. **Gold pipeline (Green/Amber, A-then-B)** — a router stamping each gold Green
   (sourced, provenance logged) or Amber (proposed → conformal set → human checks
   only uncertain ones, bounded leakage). Report the Green/Amber split per domain.
3. **Courtroom Inspect — jury (deterministic).** Fairness: two-proportion z-test +
   bootstrap CI on the group gap (credit approval-rate; insurance adds a proxy /
   rate-disparity route). Robustness: paired accuracy drop + McNemar. Consistency:
   modal-agreement rate + Wilson. Single rates: Wilson. Sample size from a power
   calc (n ≈ z²p(1−p)/e² → ~300 core per deep dimension). No model touches a number.
4. **Courtroom Inspect — gated judge.** LLM on a typed docket: rubric = clause text
   + operationalized criterion + reference; k=5 at temperature 0; confidence =
   modal share; judge family DISJOINT from every audited model (e.g. Llama judges
   Qwen); version pinned; both-order scoring; raw runs logged. Gate: auto-accept
   iff k-run agreement ≥ per-dimension τ tightened by split-conformal so
   selective error ≤ ~5%; below τ escalate to human appeal; appeals recalibrate τ
   against the human-human κ ceiling. Add a canary drift test.
5. **Annotation study (the long pole — start ethics/recruitment first).** Stratified
   export incl. high-confidence judge items (confidently-wrong detector) and
   marginal-stratum fairness items; pilot 30 → freeze guidelines → ~300 items, two
   annotators + arbiter, blind to model. Report the human-human ceiling first;
   per-dimension Cohen's κ; never raw agreement alone.
6. **Ledger + report** — clause-traced, evidence-typed findings; "conforms/fails
   requirement R derived from Article X", never "complies".
7. **Generalisation** — run the frozen pipeline on the API model (fills S3); then
   swap the standards corpus credit→insurance and re-sign (one notary signature, no
   code change). Insurance fairness likely needs a *second jury route* (proxy
   discrimination in pricing) — adding a route to the jury's library is allowed;
   rewriting the jury per sub-sector is not, and the transfer/limit is a finding.

## Scope discipline (the biggest risk is sprawl — hold it)

- Keep the human as **notary** (signs the checklist, verifies golds). Do NOT chase
  fully human-free generation — it has no certified bound in the thesis timeframe.
- Go **deep on ONE sub-sector (credit)**; merely *demonstrate* a second (insurance).
  One domain proven beats several demoed shallowly.
- **Measure the generator, don't just run it** — compare auto-probes to hand-written
  ones and check auto-golds; that measurement is the contribution, not more features.
- Exact search, bge-base, hybrid + BM25. No vector DB / HNSW unless scale demands it
  (it won't at ~tens of thousands of clauses) — approximate recall can miss a clause.

## Dev conventions

- Every new stage ships with tests; the suite must stay green (`pytest -q tests/`).
- Keep an offline-runnable path (hashing embedder, pure-python BM25) so CI works
  without model downloads; the real backend is bge-base / sbert.
- Config lives in `config.py` (committed clauses, clause→dimension map, thresholds
  as cited constants, retrieval knobs). A domain = config + corpus + gold, not code.
- Success criteria: S1 ≥90% clause-mapping + 100% findings clause-tagged (retrieval
  already at recall@3 = 1.00); S2 κ ≥ 0.61 on ≥1 dimension with gate selective error
  ≤5% at coverage ≥50%; S3 both models audited; S4 negative results count.
