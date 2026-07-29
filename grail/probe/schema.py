"""Data model for probes — the behavioural stimuli put to the system under audit.

Three invariants live here rather than in the generators, so that no generator
can violate them:

1. **The system under audit never sees the law.** `assert_no_leakage` refuses any
   prompt containing legal or audit vocabulary. It runs on every probe at
   construction time, not only in tests.
2. **Probes are seeded and immutable.** Every probe carries a content hash; a
   probe set carries a manifest hash over all of them plus the seed, the
   generator version and the SHA-256 of the signed checklist it came from.
   Re-running the generator with the same (seed, checklist) must reproduce the
   same manifest hash.
3. **Headline statistics come from CORE probes only.** `sample_kind` is stamped
   at generation; adaptive probes (a later stage) are a labelled diagnosis
   stream and are excluded from headline numbers by construction.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
import hashlib
import json
import os
import re

# Pinned. Bump on any change to a generator's output; it is part of the manifest
# hash, so an old probe set can never be silently confused with a new one.
GENERATOR_VERSION = "probe-gen/1.0.0"

# Sample kind (non-negotiable: headline stats use CORE only).
CORE = "core"
ADAPTIVE = "adaptive"

# How a reference answer will be obtained by the gold pipeline (stage 2). The
# generator never invents a gold; it only records the route.
GOLD_COMPUTED = "computed"      # deterministically calculable -> Green
GOLD_SOURCED = "sourced"        # extractable from a primary source -> Green
GOLD_STRUCTURAL = "structural"  # correct behaviour is structural (e.g. reject a false premise)
GOLD_NONE = "none"              # no reference; scored by comparison, not by key


# --- Leakage guard ----------------------------------------------------------
# A probe that mentions the law teaches the system under audit what is being
# tested, which destroys the measurement. These patterns are checked against
# every prompt.
_BANNED = [
    r"\baudit\w*",
    r"\bcompl(?:y|ies|ied|iance|iant)\b",
    r"\bregulat\w*",
    r"\barticle\b",
    r"\bannex\b",
    r"\bai act\b",
    r"\bgdpr\b",
    r"\bdiscriminat\w*",
    r"\bbias(?:ed|es)?\b",
    r"\bfairness\b",
    r"\bprotected\s+(?:attribute|characteristic|class|group)\b",
    r"\bhigh[-\s]risk\b",
    r"\bethic\w*",
    r"\blegisl\w*",
    r"\bdirective\b",
    r"\bconformity\s+assessment\b",
]
_BANNED_RE = [re.compile(p, re.IGNORECASE) for p in _BANNED]


def leakage_terms(text: str) -> list[str]:
    """Every banned term found in `text` (empty list means clean)."""
    hits: list[str] = []
    for rx in _BANNED_RE:
        hits.extend(m.group(0) for m in rx.finditer(text))
    return hits


def assert_no_leakage(text: str, where: str = "prompt") -> None:
    hits = leakage_terms(text)
    if hits:
        raise ValueError(
            f"probe leakage in {where}: the system under audit must never see "
            f"legal or audit vocabulary, found {sorted(set(h.lower() for h in hits))}")


def digits(text: str) -> list[str]:
    """Digit multiset of a string — used to prove a perturbation is meaning-preserving."""
    return sorted(re.findall(r"\d", text))


# --- Probe ------------------------------------------------------------------
@dataclass
class Probe:
    id: str                       # stable, readable, deterministic
    domain: str
    dimension: str                # fairness | robustness | consistency | transparency | truthfulness
    family: str                   # generator sub-family, e.g. "credit_application"
    clause_ids: list[str]         # traceability back to the signed obligations
    citations: list[str]
    prompt: str                   # exactly what the system under audit receives
    sample_kind: str = CORE
    stratum: str = ""             # e.g. "marginal" — pre-registered, used for stratified reporting
    pair_id: str | None = None    # counterbalanced pair / paraphrase set membership
    variant: str = ""             # which arm or perturbation this is
    base_id: str | None = None    # for a perturbed/paraphrased probe: the unperturbed probe
    axis: str | None = None       # protected axis under test, for fairness probes
    arm: str | None = None        # value of that axis in this rendering
    reference: str | None = None       # filled by the gold pipeline, never here
    reference_status: str = "pending"  # pending | green | amber
    gold_route: str = GOLD_NONE
    expected_behavior: str = ""   # structural expectation where one exists
    slots: dict = field(default_factory=dict)   # the structured case behind the prompt
    seed: int = 0
    generator_version: str = GENERATOR_VERSION
    content_sha256: str = ""

    def __post_init__(self) -> None:
        assert_no_leakage(self.prompt, where=f"probe {self.id}")
        if not self.content_sha256:
            self.content_sha256 = self.compute_hash()

    def compute_hash(self) -> str:
        payload = json.dumps(
            {"id": self.id, "dimension": self.dimension, "family": self.family,
             "prompt": self.prompt, "variant": self.variant,
             "clause_ids": sorted(self.clause_ids), "slots": self.slots},
            ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)

    @staticmethod
    def from_json(line: str) -> "Probe":
        return Probe(**json.loads(line))


# --- Probe set + manifest ---------------------------------------------------
@dataclass
class ProbeSet:
    domain: str
    instrument: str
    seed: int
    checklist_sha256: str
    checklist_signer: str
    generator_version: str = GENERATOR_VERSION
    created_utc: str = ""
    probes: list[Probe] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.created_utc:
            self.created_utc = datetime.now(timezone.utc).isoformat(timespec="seconds")

    # -- provenance ----------------------------------------------------------
    def content_hash(self) -> str:
        """Hash over probe content + the inputs that determined it.

        `created_utc` is deliberately excluded: the same (seed, checklist,
        generator version) must hash identically whenever it is run.
        """
        payload = json.dumps(
            {"domain": self.domain,
             "seed": self.seed,
             "checklist_sha256": self.checklist_sha256,
             "generator_version": self.generator_version,
             "probes": sorted(p.content_sha256 for p in self.probes)},
            sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def counts(self) -> dict:
        """Per-dimension counts.

        `cases` is the unit power is calculated in — independent cases, not
        prompts. A fairness pair is one case rendered twice and a robustness base
        plus its perturbations is one case rendered seven times; counting prompts
        would make both look several times better powered than they are.
        """
        out: dict = {}
        pairs: dict = {}
        for p in self.probes:
            d = out.setdefault(p.dimension, {"total": 0, "core": 0, "adaptive": 0,
                                             "cases": 0, "families": {}})
            d["total"] += 1
            d[p.sample_kind] = d.get(p.sample_kind, 0) + 1
            d["families"][p.family] = d["families"].get(p.family, 0) + 1
            if p.sample_kind == CORE:
                pairs.setdefault(p.dimension, set()).add(p.pair_id or p.id)
        for dim, keys in pairs.items():
            out[dim]["cases"] = len(keys)
        return out

    def manifest(self, targets: dict | None = None,
                 notes: list[str] | None = None) -> dict:
        counts = self.counts()
        underpowered = {}
        for dim, target in (targets or {}).items():
            got = counts.get(dim, {}).get("cases", 0)
            if dim in counts and got < target:
                underpowered[dim] = {"target": target, "actual_cases": got}
        return {
            "domain": self.domain,
            "instrument": self.instrument,
            "generator_version": self.generator_version,
            "seed": self.seed,
            "checklist_sha256": self.checklist_sha256,
            "checklist_signer": self.checklist_signer,
            "created_utc": self.created_utc,
            "n_probes": len(self.probes),
            "counts": counts,
            "core_targets": targets or {},
            "underpowered": underpowered,
            "notes": notes or [],
            "content_sha256": self.content_hash(),
        }


def save_probeset(ps: ProbeSet, directory: str, targets: dict | None = None,
                  notes: list[str] | None = None, force: bool = False) -> dict:
    """Write probes.jsonl + manifest.json, refusing to silently mutate a frozen set.

    Probes are immutable: if a probe set already exists here with a different
    content hash, this raises unless `force` is passed. Regenerating an
    identical set is always allowed (that is the reproducibility check).
    """
    os.makedirs(directory, exist_ok=True)
    probes_path = os.path.join(directory, "probes.jsonl")
    manifest_path = os.path.join(directory, "manifest.json")
    new_manifest = ps.manifest(targets=targets, notes=notes)

    if os.path.exists(manifest_path) and not force:
        with open(manifest_path, encoding="utf-8") as fh:
            old = json.load(fh)
        if old.get("content_sha256") != new_manifest["content_sha256"]:
            raise SystemExit(
                "PROBE SET FROZEN: a different probe set already exists at "
                f"{directory}\n"
                f"  on disk : {old.get('content_sha256', '')[:16]}… "
                f"(seed {old.get('seed')}, checklist {str(old.get('checklist_sha256'))[:12]}…)\n"
                f"  new     : {new_manifest['content_sha256'][:16]}… "
                f"(seed {ps.seed}, checklist {ps.checklist_sha256[:12]}…)\n"
                "Probes are immutable once generated. Write to a new directory, "
                "or pass --force if you are deliberately re-freezing.")

    with open(probes_path, "w", encoding="utf-8") as fh:
        for p in ps.probes:
            fh.write(p.to_json() + "\n")
    with open(manifest_path, "w", encoding="utf-8") as fh:
        json.dump(new_manifest, fh, ensure_ascii=False, indent=2)
    return new_manifest


def load_probes(path: str) -> list[Probe]:
    out = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                out.append(Probe.from_json(line))
    return out


def derive_rng(seed: int, *parts: object):
    """A per-case RNG derived deterministically from (master seed, case key).

    Uses blake2b rather than Python's `hash()` so it is stable across processes
    and versions, and derives per-case so that adding a case later does not
    shift every earlier case.
    """
    import random
    payload = f"{seed}|" + "|".join(str(p) for p in parts)
    digest = hashlib.blake2b(payload.encode("utf-8"), digest_size=16).digest()
    return random.Random(int.from_bytes(digest, "big"))
