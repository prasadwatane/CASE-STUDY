"""Orchestrator: signed checklist -> probe set.

The gate comes first. `require_signed` runs before a single probe exists, so a
probe set can only ever descend from a checklist a human reviewed, signed and
froze; if the checklist has been edited since signing, nothing is generated at
all. The signature hash is then carried into the probe manifest, which is what
makes a finding traceable all the way back: finding -> probe -> requirement ->
clause -> the exact frozen text the notary approved.

Two filters run before any generator:

* **Scope.** Only behavioural and hybrid items yield probes. Procedural items are
  kept in the corpus for context but never become something to test, and each one
  dropped here is recorded as an explicit note rather than vanishing.
* **Coverage.** A dimension with no registered generator is reported as a gap in
  the manifest. Silence would look like coverage.
"""
from __future__ import annotations

from config import (CREDIT_STRATA, INSTRUMENT, PROBEABLE_PARTITIONS,
                    PROBE_CORE_N, PROBE_SEED, PROBE_SEED_DIR, PROTECTED_AXES)
from grail.ground.notary import require_signed
from grail.probe.generators import REGISTRY, GenContext
from grail.probe.schema import ProbeSet


def _group_by_dimension(items: list[dict]) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for it in items:
        out.setdefault(it.get("dimension", "unassigned"), []).append(it)
    return out


def generate_probeset(checklist_path: str, seed: int = PROBE_SEED,
                      core_n: dict | None = None,
                      axes: list | None = None,
                      strata: dict | None = None,
                      seed_dir: str = PROBE_SEED_DIR,
                      only: list[str] | None = None) -> tuple[ProbeSet, list[str]]:
    """Generate a probe set from a signed checklist. Returns (probeset, notes)."""
    signed = require_signed(checklist_path)          # notary gate — first, always
    checklist = signed["checklist"]
    domain = checklist["domain"]
    items = checklist["items"]
    notes: list[str] = []

    probeable, skipped = [], []
    for it in items:
        (probeable if it.get("scope_partition") in PROBEABLE_PARTITIONS
         else skipped).append(it)
    for it in skipped:
        notes.append(
            f"scope: {it['citation']} is {it.get('scope_partition')} — out of probe "
            "scope by design, no requirement derived from it")

    ctx = GenContext(
        domain=domain,
        seed=seed,
        core_n=dict(core_n if core_n is not None else PROBE_CORE_N),
        axes=list(axes if axes is not None else PROTECTED_AXES.get(domain, [])),
        strata=dict(strata if strata is not None else CREDIT_STRATA),
        seed_dir=seed_dir,
        notes=notes,
    )

    probes = []
    for dimension, dim_items in sorted(_group_by_dimension(probeable).items()):
        cites = ", ".join(i["citation"] for i in dim_items)
        if only and dimension not in only:
            notes.append(f"coverage: dimension '{dimension}' skipped by request ({cites})")
            continue
        generator = REGISTRY.get(dimension)
        if generator is None:
            notes.append(
                f"coverage gap: dimension '{dimension}' has no registered generator, "
                f"so {cites} is signed but not probed")
            continue
        produced = generator(ctx, dim_items)
        probes.extend(produced)
        notes.append(f"generated {len(produced)} probes for '{dimension}' from {cites}")

    ps = ProbeSet(
        domain=domain,
        instrument=checklist.get("instrument", INSTRUMENT),
        seed=seed,
        checklist_sha256=signed["signature"]["content_sha256"],
        checklist_signer=signed["signature"]["signer"],
        probes=probes,
    )
    return ps, notes
