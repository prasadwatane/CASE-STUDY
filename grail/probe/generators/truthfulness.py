"""Truthfulness probes — reference-graded questions in three framings.

The seed bank (`data/probes/seeds/`) holds questions only. It holds **no answers**
by design: a reference answer written here would be an uncertified "trust me"
gold. Each item instead records the route by which the gold pipeline will obtain
its key — `computed` (deterministic arithmetic), `sourced` (extractable from a
primary source, provenance logged) or `structural` (the correct behaviour is to
reject the premise, so no factual key is needed).

Item types: plain factual questions, false-premise questions, questions about
entities that do not exist, and numeric traps where a plausible wrong answer is
easier to reach than the right one.

Framings: neutral, embedded in a branch scenario, and a sycophancy framing that
applies social pressure toward a stated lure. The sycophancy framing is only
emitted for items that carry a lure — pressure toward nothing measures nothing.
"""
from __future__ import annotations

import json
import os

from grail.probe.generators._common import clause_refs
from grail.probe.schema import CORE, Probe, assert_no_leakage
from grail.probe.templates import apply_framing, framings, seed_files

FAMILY_PREFIX = "truthfulness"
DEFAULT_SEED_FILES = ["truthfulness_credit_en.jsonl"]


def load_seed_bank(seed_dir: str, files: list[str] | None = None) -> list[dict]:
    items: list[dict] = []
    for name in (files if files is not None else DEFAULT_SEED_FILES):
        path = os.path.join(seed_dir, name)
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line and not line.startswith("//"):
                    items.append(json.loads(line))
    items.sort(key=lambda d: d["id"])   # deterministic order regardless of file order
    return items


def generate(ctx, items: list) -> list[Probe]:
    clause_ids, citations = clause_refs(items)
    n_target = ctx.n("truthfulness", 300)
    banks = seed_files(ctx.pack) if ctx.pack else None
    bank = load_seed_bank(ctx.seed_dir, banks)
    probes: list[Probe] = []

    if not bank:
        ctx.notes.append(
            f"truthfulness: sub-domain '{ctx.pack.get('name', '?')}' declares no "
            f"seed bank (or none found in {ctx.seed_dir}) — no probes generated")
        return probes

    for item in bank:
        question = item["question"]
        lure = item.get("lure")
        assert_no_leakage(question, where=f"seed item {item['id']}")
        for framing in framings(ctx.pack):
            frame_name = framing["name"]
            if framing.get("needs_lure") and not lure:
                continue
            probes.append(Probe(
                id=f"{ctx.domain}:truthfulness:{item['id']}:{frame_name}",
                domain=ctx.domain, dimension="truthfulness",
                family=f"{FAMILY_PREFIX}_{item['type']}",
                clause_ids=clause_ids, citations=citations,
                prompt=apply_framing(framing, question, lure),
                sample_kind=CORE, pair_id=f"{ctx.domain}:truthfulness:{item['id']}",
                variant=frame_name,
                base_id=None if frame_name == "neutral"
                        else f"{ctx.domain}:truthfulness:{item['id']}:neutral",
                gold_route=item.get("gold_route", "none"),
                expected_behavior=item.get("expected_behavior", ""),
                slots={"seed_item": item["id"], "type": item["type"],
                       "lure": lure, "framing": frame_name},
                seed=ctx.seed))

    if len(probes) < n_target:
        ctx.notes.append(
            f"truthfulness: {len(probes)} CORE probes from a {len(bank)}-item seed bank, "
            f"target {n_target}. UNDERPOWERED — grow the seed bank before quoting a "
            "headline truthfulness number.")
    return probes
