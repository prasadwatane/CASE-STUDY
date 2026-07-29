"""Proposers — the only place a model is allowed near a gold, and never near a number.

A proposer answers an item k times. It is used for two things: proposing answers
for items that have no deterministic solver, and, on items that *do* have one,
producing the calibration data that decides whether its proposals can be trusted
unchecked. It is never asked to compute an arithmetic result — those come from
`formulas.py` — and its name is written into every record it touches, so a gold
can always be traced to what produced it.

`StubProposer` is the offline path, mirroring the hashing embedder in the index:
deterministic, dependency-free, keeps CI runnable. It is not a model and its
output is not evidence. The router refuses to write a ledger from it unless
`allow_stub` is passed explicitly, and the stub's name stays in the provenance
forever so a stub-built ledger can never be mistaken for a real one.

To wire a real model, implement `propose` and pass the instance in. Pin the model
version in `name` — that string is the difference between a reproducible gold and
an anecdote.
"""
from __future__ import annotations

from typing import Protocol

from grail.probe.schema import derive_rng

STRUCTURAL_CHOICES = ("construction_holds", "construction_fails")


class Proposer(Protocol):
    name: str

    def propose(self, item: dict, k: int) -> list[str]:
        """Return k independent proposals for one seed-bank item."""


class StubProposer:
    """Deterministic offline stand-in. Never evidence; only keeps CI honest.

    It samples from a small pool — the answer a solver would give, the item's
    lure, or a structural verdict — with a per-item agreement level derived from
    the item id. That produces a realistic spread of nonconformity scores to
    calibrate against, without pretending to be a model.
    """

    name = "stub/deterministic-1.0"
    is_stub = True

    def __init__(self, seed: int = 0):
        self.seed = seed

    def propose(self, item: dict, k: int) -> list[str]:
        r = derive_rng(self.seed, "proposer", item["id"])
        route = item.get("gold_route")

        if route == "structural":
            pool = list(STRUCTURAL_CHOICES)
            favoured = pool[0]
        else:
            favoured = item.get("_reference") or f"answer::{item['id']}"
            alternative = item.get("lure") or f"alternative::{item['id']}"
            pool = [favoured, alternative]

        # agreement level in {1.0, 0.8, 0.6, 0.4}: some items are unanimous,
        # some are contested, which is what makes calibration meaningful
        agreement = r.choice([1.0, 1.0, 0.8, 0.8, 0.6, 0.4])
        n_favoured = max(1, round(agreement * k))
        proposals = [favoured] * n_favoured
        while len(proposals) < k:
            proposals.append(pool[1] if len(pool) > 1 else favoured)
        r.shuffle(proposals)
        return proposals[:k]
