"""Central configuration. Paths, model names, retrieval knobs, scope overrides.

Nothing here is a magic number without a reason: retrieval knobs follow the
GRAIL roadmap (hybrid BM25 + dense, RRF fusion, rerank to a small top-k).
"""
from __future__ import annotations
import os

ROOT = os.path.dirname(os.path.abspath(__file__))

# --- Paths ------------------------------------------------------------------
RAW_DIR = os.path.join(ROOT, "data", "standards", "raw")
PROCESSED_DIR = os.path.join(ROOT, "data", "processed")
CLAUSES_PATH = os.path.join(PROCESSED_DIR, "clauses.jsonl")
INDEX_DIR = os.path.join(PROCESSED_DIR, "index")

# --- Embeddings -------------------------------------------------------------
# Real backend is bge-small-en-v1.5 (roadmap). If sentence-transformers or the
# model is unavailable (offline CI), the embedder falls back to a deterministic
# hashing vector so the pipeline still runs. Switch here.
EMBED_BACKEND = os.environ.get("GRAIL_EMBED", "auto")   # auto | sbert | hashing
# Default upgraded to bge-base (768). Override per-run without editing code, e.g.
#   GRAIL_EMBED_MODEL=BAAI/bge-large-en-v1.5 python scripts/eval_retrieval.py
# bge base/large share the same v1.5 query-instruction prefix as bge-small.
EMBED_MODEL = os.environ.get("GRAIL_EMBED_MODEL", "BAAI/bge-base-en-v1.5")
EMBED_DIM_FALLBACK = 512

# --- Retrieval (hybrid) -----------------------------------------------------
RRF_K = 60          # reciprocal-rank-fusion constant
TOP_K = 6           # final obligations returned to the evaluator
CANDIDATE_K = 50    # per-retriever candidate pool before fusion

# Only these partitions are probeable; procedural is retrievable for context
# but never yields a requirement (skill non-negotiable).
PROBEABLE_PARTITIONS = ("behavioral", "hybrid")

# --- Scope-partition overrides ---------------------------------------------
# Heuristic tagging is a starting point; a human signs the final partition at
# the notary gate. These curated overrides encode the committed finance core.
SCOPE_OVERRIDES = {
    "AIA:Art10(2)(f)": "hybrid",
    "AIA:Art10(2)(g)": "behavioral",
    "AIA:Art13(1)":    "hybrid",
    "AIA:Art15(1)":    "behavioral",
    "AIA:Art11(1)":    "procedural",
    "AIA:Art12(1)":    "procedural",
}

INSTRUMENT = "Regulation (EU) 2024/1689 (EU AI Act)"

# --- Ground / notary gate ---------------------------------------------------
CHECKLIST_DIR = os.path.join(PROCESSED_DIR, "checklists")

# Committed finance core: the behavioural/hybrid clauses a human anchors the
# creditworthiness audit on. The notary gate freezes requirements derived from
# these. (GDPR Art 22 lives in a tier-2 corpus not loaded here.)
COMMITTED_CLAUSES = {
    "finance": [
        "AIA:Art10(2)(f)",   # bias examination
        "AIA:Art10(2)(g)",   # bias mitigation
        "AIA:Art13(1)",      # transparency to deployers
        "AIA:Art15(1)",      # accuracy / robustness / cybersecurity
        "AIA:Art15(4)",      # resilience / feedback loops
    ],
}

# Clause -> audit dimension (best-effort; the human confirms at the gate).
CLAUSE_DIMENSION = {
    "AIA:Art10(2)(f)": "fairness",
    "AIA:Art10(2)(g)": "fairness",
    "AIA:Art13(1)":    "transparency",
    "AIA:Art15(1)":    "robustness",
    "AIA:Art15(4)":    "robustness",
}

# --- Auto-probe -------------------------------------------------------------
# Probes are generated FROM the signed checklist only, are seeded and immutable,
# and never reference the law or the word "audit". A domain activates a
# generator by mapping one of its committed clauses to that dimension above —
# adding a domain is config + corpus + gold, never new control flow.
PROBE_DIR = os.path.join(PROCESSED_DIR, "probes")
PROBE_SEED_DIR = os.path.join(ROOT, "data", "probes", "seeds")

# Master seed. Changing it produces a different (equally valid) probe set and a
# different manifest hash — so a run is always reproducible from (seed, checklist).
PROBE_SEED = 20260729

# CORE sample sizes. Headline statistics may only use CORE probes.
# Sizing: n = z^2 * p(1-p) / e^2 with z=1.96, p=0.5 (worst case) and a margin of
# e = 0.0566 gives n = 300 per arm — see grail/probe/sizing.py, which recomputes
# these rather than hard-coding them.
PROBE_CORE_N = {
    "fairness":     300,   # counterbalanced PAIRS -> 300 per group arm
    "robustness":   300,   # paired base cases (McNemar runs on discordant pairs)
    "consistency":  150,   # base cases, each expanded into a paraphrase/DE set
    "transparency": 150,
    "truthfulness": 300,   # capped by the seed bank until it is grown
}

# Protected axes for counterbalanced fairness probes. Each base applicant
# profile is rendered once per arm; the two renderings differ in EXACTLY the
# axis slot and nothing else (enforced in code and in tests).
PROTECTED_AXES = {
    "finance": [
        {
            "name": "gender",
            "slot": "title",
            "arms": [
                {"value": "female", "slots": {"title": "Ms."}},
                {"value": "male",   "slots": {"title": "Mr."}},
            ],
        },
    ],
}

# Credit-strength strata. Bias is most visible in the marginal band, so it is
# sampled most heavily; the split is fixed here so it is pre-registered.
CREDIT_STRATA = {"strong": 0.30, "marginal": 0.40, "weak": 0.30}
