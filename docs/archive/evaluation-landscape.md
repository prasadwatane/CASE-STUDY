# How LLMs Are Evaluated — Benchmarks, Papers, and How GRAIL Generalizes

A reference map for the GRAIL related-work chapter. Three questions:
1. What benchmarks exist to evaluate a model?
2. What papers underpin GRAIL's method (auditing + judge reliability + calibration)?
3. How does any of this generalize across domains — and why is that GRAIL's contribution?

Verify arXiv IDs against the linked sources before final submission.

---

## 1. Benchmarks used to evaluate a model

### A. Holistic / capability (the baseline everyone starts from)

| Benchmark | What it measures | Note for GRAIL |
|---|---|---|
| **HELM** (Stanford CRFM) | 7 dims: accuracy, calibration, robustness, fairness, bias, toxicity, efficiency across scenarios | Closest "holistic" ancestor; measures *capability*, not *lawful behaviour*. GRAIL's novelty is clause-traceability HELM lacks. |
| **MMLU / BIG-bench / MT-Bench** | knowledge, reasoning, open-ended chat quality | Capability only; not trust, not compliance. |

### B. Trust / Responsible-AI (multi-dimensional trust)

| Benchmark | Dimensions | Relevance |
|---|---|---|
| **TrustLLM** | truthfulness, safety, fairness, robustness, privacy, machine ethics (30+ datasets, 16 LLMs) | The dimension taxonomy GRAIL's rubric cube echoes. |
| **DecodingTrust** | toxicity, stereotype bias, adversarial + OOD robustness, privacy, ethics, fairness (GPT-focused) | Dimension-per-perspective design. |
| **HELM Safety / SafetyBench** | safety, harm categories | Safety slice. |
| **AILuminate (MLCommons v1.0/1.1)** | AI product risk across 12 hazard categories, 24k+ prompts, ensemble judge | Industry-standard *risk* benchmark; still capability-style scoring, not law-anchored. |

### C. Regulation / compliance (the layer nearest GRAIL)

| System | What it does | Gap GRAIL fills |
|---|---|---|
| **COMPL-AI** (LatticeFlow/ETH/INSAIT) | First technical interpretation of the EU AI Act → maps Act to existing benchmarks; leaderboard | Mapping is **manual**, suite **frozen**, scoring **never human-validated**, explicitly "not an official audit". GRAIL auto-derives, human-signs, and certifies the judge. |
| **Foundation Model Transparency Index (FMTI)** | transparency scoring of model providers | Its own agent appendix emits confidence but still human-verifies every finding — confirms GRAIL's premise + gap. |

### D. Finance-domain (your committed domain)

| Benchmark | Focus | Finding you can cite |
|---|---|---|
| **FinBen** | 42 datasets, 24 tasks, 8 aspects (IE, QA, risk, forecasting, trading, RAG) | LLMs strong at extraction, weak at reasoning/forecasting. The broad capability map. |
| **PIXIU / FinQA / ConvFinQA** | financial numerical reasoning + QA | Task ancestors; capability, not trust. |
| **FinanceBench** | filing-grounded QA on real 10-Ks | Even retrieval-augmented leading models fail/refuse a large share — professional performance is weak. |
| **FinTrust** (EMNLP 2025) | 7 trust dims (truthfulness, robustness, safety, fairness, privacy, transparency, knowledge); 15,680 pairs | All models fail hardest cells: **fiduciary alignment + disclosure** → "significant gap in legal awareness". Legally *inspired* but NOT clause-traceable — GRAIL's exact opening. |
| **FailSafeQA** (Writer, 2025) | robustness under query/context perturbation; LLM-as-judge (Qwen-72B) | Most robust model (o3-mini) still **fabricates in 41%** of perturbed cases. Also: judge is same-family as models judged (no disjoint judge) — GRAIL fixes this. |
| **MultiFinBen / BizFinBench** (2026 wave) | multilingual + multimodal finance | Breadth expanding; still capability-centric, monolingual-to-multilingual. |

### E. Single-dimension benchmarks (what your jury/judge can reuse as probe seeds)

- **Fairness:** BBQ (bias QA), HolisticBias; **HMDA credit-audit (Bowen et al.)** — counterbalanced loan applications varying only race/credit score → the exact CV-pair design GRAIL uses for finance fairness.
- **Truthfulness / hallucination:** TruthfulQA, HaluEval, FELM.
- **Robustness:** PromptRobust, AdvGLUE, meaning-preserving perturbation (as in FailSafeQA).

### F. LLM-as-a-judge reliability (the core of your Inspect stage)

| Work | Point |
|---|---|
| **JudgeBench** (ICLR 2025) | Strongest judge only ~64% on hard objective-correctness pairs; many judges near random. Direct evidence you must *measure and gate* the judge. |
| **MT-Bench / Chatbot Arena** (Zheng et al.) | Origin of LLM-as-judge; documents position & verbosity bias → your both-order scoring. |
| **Gu et al. survey** | reliability = human-alignment + consistency; catalogues judge biases. |
| **"Are We on the Right Way to Assessing LLM-as-a-Judge?" (SAGE, 2025)** | judge failures concentrate on *close cases* → rationale for a self-consistency gate. |
| **Verga et al. — jury of LLMs** | panel of judges; GRAIL deliberately inverts it (deterministic *code* in the jury box, LLM only on the typed docket). |

---

## 2. Papers underpinning GRAIL's method

- **Auditing frameworks:** Mökander et al. — three-layered LLM auditing (governance / model / application). LLMAuditor — multi-probe + human-in-loop (but no rule for *when* the human is needed → GRAIL's conformal gate supplies it).
- **Risk-first finance auditing:** Chen et al. — argues standard finance benchmarks measure performance not deployability, calls for risk-first auditing but builds no machinery. GRAIL is that machinery.
- **Selective automation / calibration:** Angelopoulos & Bates — conformal prediction (distribution-free selective-error bound → your τ gate). Landis & Koch — κ agreement bands ("substantial" ≥ 0.61).
- **Regulatory anchors (not benchmarks — the corpus):** EU AI Act (Reg. 2024/1689) Arts 10/13/15 + Annex III 5(b); NIST AI RMF (guidance, MEASURE subcategories); GDPR Art 22 + CJEU SCHUFA.

---

## 3. How it generalizes — and why that is the thesis

**The blunt truth about the benchmarks above: almost none of them generalize.** Each is
hand-built for its domain and frozen. FinTrust is finance-only; COMPL-AI is a manual
Act→benchmark mapping; HELM's scenarios are curated by hand. To cover a new domain,
every one of them requires humans to author new datasets. That is the gap.

**GRAIL generalizes by construction — the domain is data, not code:**

| Layer | How it generalizes |
|---|---|
| **Standards corpus** | Swap the source PDFs (EU AI Act → employment law → NIST). The deterministic parser + retriever are domain-agnostic; only the corpus changes. |
| **Requirements** | *Auto-derived* from the new corpus (retrieval → checklist), not hand-written. |
| **Trust root** | A human *signs* the auto-derived checklist (notary gate) — the only per-domain human step. |
| **Probes** | *Auto-generated from the signed obligations* — the jury/judge machinery never changes. |
| **Jury / judge / gate / ledger** | Fixed. Editing them per domain is a design smell. |

So the generalization claim is testable and bounded: **prove it deep on one domain
(finance, Annex III 5(b)), then show it on a second (employment, Annex III pt 4) by
swapping only the corpus and re-signing.** One deep, one shown — the "auto/self-evolving"
methodology, demonstrated rather than merely asserted.

**Where the existing benchmarks still help you per domain:** reuse them as *probe seed
banks and validation sets*, not as the audit. HMDA/Bowen → finance fairness probes;
TruthfulQA/HaluEval → truthfulness probes; FailSafeQA-style perturbations → robustness
probes; FinTrust/COMPL-AI → cross-checks for your findings. GRAIL's addition on top of
all of them is the one thing none provide: **clause-traceable requirements + a certified,
human-calibrated, selectively-automated judge inside a governed loop.**

---

## Sources
- FinBen — https://arxiv.org/abs/2402.12659
- FinTrust (EMNLP 2025) — https://arxiv.org/abs/2510.15232 · https://aclanthology.org/2025.emnlp-main.512/
- FailSafeQA — https://arxiv.org/abs/2502.06329 · https://writer.com/engineering/failsafeqa-benchmark/
- COMPL-AI — https://arxiv.org/abs/2410.07959 · https://github.com/compl-ai/compl-ai
- JudgeBench (ICLR 2025) — https://arxiv.org/abs/2410.12784
- "Are We on the Right Way to Assessing LLM-as-a-Judge?" — https://arxiv.org/pdf/2512.16041
- TrustLLM — https://arxiv.org/abs/2401.05561 · https://trustllmbenchmark.github.io/TrustLLM-Website/
- DecodingTrust — https://howiehwong.github.io/TrustLLM/ (comparison) 
- AILuminate (MLCommons v1.0) — https://arxiv.org/abs/2503.05731 · https://mlcommons.org/ailuminate/
- HELM (Stanford CRFM) — https://crfm.stanford.edu/helm/ · https://github.com/stanford-crfm/helm
