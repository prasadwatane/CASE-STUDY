# Contribution matrix — case study versus thesis

What the preceding GRAIL case study already delivered, where it stopped, and what
the thesis adds. Every figure in the "already exists" column is taken from the
repository as of commit `Case study report: benchmark landscape…` (15 Sep 2026)
and the exposé; nothing in the "thesis adds" column has been run yet.

## 1. Component by component

| Component | Already exists (case study) | Limitation left open | Thesis contribution | RQ | Status |
|---|---|---|---|---|---|
| Grounding: parser, hybrid retrieval, signed checklist | EU AI Act parsed into 1,143 legal units; checklist signed and hashed; retrieval recall@3 = 1.00 on a 10-query gold set | One corpus only; generality asserted, not shown | **C6 (conditional):** second corpus to a signed draft checklist with zero code change | — | optional |
| Probe generator and response log | 14,825 probes per model; 61,259 logged responses from four open-weight models | One protected axis (gender via title); open-weight models only | **C4:** second axis (age) and one API-served model. **C4b (conditional):** title vs name vs explicit-statement cue | — | C4 mandatory, C4b optional |
| Deterministic jury | Exact paired tests, TOST equivalence, Holm correction, three-way verdicts | None for the committed scope | Reused unchanged | — | reuse |
| LLM judge (phi-4, k = 5, pinned) | Verdicts for four models on the transparency docket; burden-of-proof rubric; quote grounding check | **Never validated against humans**; no trivial baseline to beat | **C1/C1b:** judge scored as a third rater against a measured human ceiling; rule-based and majority-class baselines | RQ1 | mandatory |
| Human annotation | Pilot round 1: 30 items, four raters, Fleiss κ = 0.069; reconciliation worksheet; guideline v1.1 drafted | **Reference unreliable**; guideline not frozen; round 2 not run | **C1:** ceiling-first procedure: frozen decidable guideline, 30-item round 2, gate on the lower bound, 300 double-rated items, independent arbitration | RQ1 | mandatory, critical path |
| Selective gate | Split-conformal code exists in the gold pipeline; judge escalates below 0.80 self-agreement | **Gate never wired to the judge path**; no error bound | **C2:** nonconformity = five-run self-agreement at T = 0.3 (OPEN 6, decided 18 Nov; the judge does not run at T = 0), stratified docket-weighted bound (OPEN 2), pre-registered threshold grid, fixed-sequence search, exact Clopper–Pearson bound, risk–coverage curves | RQ2 | mandatory |
| Budget allocation | Static and uncorrected adaptive replay over 16 requirements (uncommitted code) | Adaptive raises coverage (0.50 → 0.65 at full budget) and halves spend (58,220 → 29,989) but **fidelity falls to 0.78**: optional stopping | **C3:** O'Brien–Fleming α-spending primary, confidence sequence as comparator (OPEN 5, decided 18 Nov on the development replay); S4 with a coverage condition; confirmatory test on the insurance run (Amendment A1) | RQ3 | mandatory |
| Ledger and report | Append-only, hash-chained, clause-traced report for four models | None | Reused; S5 re-verified on new findings | — | reuse |
| Reproducibility | Seeds, manifests, signed checklists, response log | Thesis design not yet hashed or countersigned | **C5:** pre-registration record, replication package | — | mandatory |

## 2. Mandatory versus optional

| Tier | Items | Rule |
|---|---|---|
| **Mandatory** | C1, C1b, C2, C3, C4, C5 | The thesis is assessed on these. |
| **Optional** | C4b (mechanism probe), C6 (second corpus) | Run only if the annotation study does not overrun. Cut in the order C4b, then C6. No chapter depends on either. |
| **Amendment A1 (pending signature)** | Life insurance pricing (Annex III 5(c)) as a second audited sector and the confirmatory RQ3 data; one new jury route for continuous outcomes | Built 18 Nov; registered in `06_insurance_amendment.md` before any response. Hiring (Annex III 4(a)) built 16–17 Nov, withdrawn before signature, kept as built-not-run |
| **Out of scope** | Hiring as an audited sector (built, not run), motor insurance (not Annex III), zero-human gold generation, vector database, fine-tuned embeddings | Named as future work; not started. |

## 3. What is new scientifically (and what is not)

| Claim | New? | Why |
|---|---|---|
| A clause-traced audit pipeline can be built | No | Delivered by the case study. |
| Title-swap fairness effect in two of four models, missed by the four-fifths rule | No | Case-study finding; C4 only tests whether it generalises. |
| Human ceiling measured **before** the judge is scored, per dimension | Yes | Judge validation in the literature is global and one-off. |
| Judge tested for non-inferiority **as a third rater**, and required to beat a rule-based scorer | Yes | Avoids scoring the judge against a label neither human had to meet. |
| Distribution-free selective-error bound on an **audit** judge, with the labelling cost of each guarantee | Yes | Selective classification exists; applying it to gate regulatory verdicts does not. |
| Audit budget treated as a **sequential-inference** problem with a spending correction | Yes | To the author's knowledge unexplored. |
