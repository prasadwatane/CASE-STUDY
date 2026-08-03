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

from config import (INSTRUMENT, PROBEABLE_PARTITIONS, PROBE_CORE_N, PROBE_SEED,
                    PROBE_SEED_DIR, PROTECTED_AXES, STIMULUS_DIR, STIMULUS_PACK,
                    STRATUM_PLAN)
from grail.ground.notary import require_signed
from grail.probe.generators import REGISTRY, GenContext
from grail.probe.generators import controls as controls_gen
from grail.probe.schema import ProbeSet
from grail.probe.templates import load_pack


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
                      pack: dict | str | None = None,
                      stimulus_dir: str = STIMULUS_DIR,
                      include_controls: bool = True,
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

    # The sub-domain arrives as data: a pack name from config, or a pack passed
    # in directly (tests, or a one-off swap without touching config).
    if isinstance(pack, dict):
        stimulus = pack
    else:
        pack_name = pack or STIMULUS_PACK.get(domain)
        if not pack_name:
            raise SystemExit(
                f"No stimulus pack configured for domain '{domain}'. Add one to "
                "config.STIMULUS_PACK and put it in data/stimuli/<name>/pack.json.")
        stimulus = load_pack(pack_name, stimulus_dir)

    plan = dict(strata if strata is not None else STRATUM_PLAN.get(domain, {}))
    if not plan:
        raise SystemExit(f"No stratum plan for domain '{domain}' (config.STRATUM_PLAN).")
    unknown = set(plan) - set(stimulus["strata"])
    if unknown:
        raise SystemExit(
            f"Stratum plan for '{domain}' names {sorted(unknown)}, which pack "
            f"'{stimulus['name']}' does not define. The analysis plan and the "
            "stimulus pack must agree on the strata.")

    notes.append(f"stimulus pack '{stimulus['name']}' "
                 f"({stimulus.get('label', '')}), outcome "
                 f"{stimulus['outcome']['type']}")

    ctx = GenContext(
        domain=domain,
        seed=seed,
        pack=stimulus,
        core_n=dict(core_n if core_n is not None else PROBE_CORE_N),
        axes=list(axes if axes is not None else PROTECTED_AXES.get(domain, [])),
        strata=plan,
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

    # Controls sit OUTSIDE the checklist loop on purpose: they are not derived
    # from a clause and are not requirements, so they carry no clause ids and are
    # stamped CONTROL, which keeps them structurally out of every headline number.
    if include_controls and probes:
        controls = controls_gen.generate(ctx)
        if controls:
            probes.extend(controls)
            notes.append(f"generated {len(controls)} positive controls "
                         "(instrument checks, excluded from headline statistics)")

    ps = ProbeSet(
        domain=domain,
        instrument=checklist.get("instrument", INSTRUMENT),
        seed=seed,
        checklist_sha256=signed["signature"]["content_sha256"],
        checklist_signer=signed["signature"]["signer"],
        probes=probes,
    )
    return ps, notes
