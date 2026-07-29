"""Generator library — one generator per audit dimension, selected by data.

Which generators fire is decided by the *signed checklist*: a checklist item
carries a dimension, and that dimension selects a generator from this registry.
Adding a domain therefore means adding clauses and a clause->dimension mapping in
config, never editing the audit graph. A dimension with no registered generator
is reported in the manifest as an explicit gap rather than silently skipped.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from grail.probe.generators import (consistency, fairness, robustness,
                                    transparency, truthfulness)


@dataclass
class GenContext:
    """Everything a generator is allowed to depend on.

    `pack` is the sub-domain's stimulus pack. No generator reads sub-domain
    content any other way, which is what makes credit -> insurance a data swap.
    """
    domain: str
    seed: int
    pack: dict = field(default_factory=dict)     # stimulus pack (the sub-domain)
    core_n: dict = field(default_factory=dict)
    axes: list = field(default_factory=list)     # protected axes (fairness only)
    strata: dict = field(default_factory=dict)   # stratum shares (analysis plan)
    seed_dir: str = ""                           # seed banks (truthfulness)
    notes: list = field(default_factory=list)    # generators append honest caveats

    def n(self, dimension: str, default: int) -> int:
        return int(self.core_n.get(dimension, default))

    @property
    def outcome_type(self) -> str:
        return self.pack.get("outcome", {}).get("type", "binary")


REGISTRY = {
    "fairness": fairness.generate,
    "robustness": robustness.generate,
    "consistency": consistency.generate,
    "transparency": transparency.generate,
    "truthfulness": truthfulness.generate,
}


def registered_dimensions() -> list[str]:
    return sorted(REGISTRY)
