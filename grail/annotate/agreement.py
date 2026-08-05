"""Inter-rater agreement — and the traps that make a κ meaningless.

Cohen's κ corrects raw agreement for the agreement two raters would reach by
chance alone. That correction is the entire point: on a task where 90% of items
get the same label, two raters who agree 90% of the time have demonstrated
nothing, and raw agreement would flatter them.

Three things this module refuses to do quietly:

**Report κ without an interval.** κ estimated from 120 items carries roughly
±0.14. "κ = 0.68" and "κ = 0.68, 95% CI [0.54, 0.80]" support different claims,
and only the second one can be checked against a threshold. The interval is a
seeded bootstrap, so it is reproducible.

**Return a number when κ is undefined.** If both raters give every item the same
label, expected agreement is 1.0 and κ is 0/0. Many implementations return 0.0
here, which reads as "no agreement" when the truth is "perfect agreement, no
variance to correct against". That is reported as undefined, with the reason.

**Report κ alone.** Percent agreement, the confusion matrix and the marginal
distributions come with it, because κ is sensitive to prevalence and a reader
needs to see the marginals to interpret the number.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

from grail.probe.schema import derive_rng


@dataclass
class Agreement:
    n: int
    labels: list[str]
    percent_agreement: float
    kappa: float | None
    ci_low: float | None
    ci_high: float | None
    expected_agreement: float
    confusion: dict = field(default_factory=dict)
    marginals: dict = field(default_factory=dict)
    undefined_reason: str = ""

    def as_dict(self) -> dict:
        return asdict(self)

    def meets(self, threshold: float) -> bool:
        """Threshold is met only if the LOWER bound clears it, not the estimate."""
        return self.ci_low is not None and self.ci_low >= threshold


def _tables(a: list[str], b: list[str]) -> tuple[dict, dict, dict, list[str]]:
    labels = sorted(set(a) | set(b))
    confusion = {x: {y: 0 for y in labels} for x in labels}
    for x, y in zip(a, b):
        confusion[x][y] += 1
    ma = {l: sum(1 for x in a if x == l) for l in labels}
    mb = {l: sum(1 for y in b if y == l) for l in labels}
    return confusion, ma, mb, labels


def cohen_kappa(a: list[str], b: list[str]) -> tuple[float | None, float, float, str]:
    """(kappa, observed agreement, expected agreement, reason if undefined)."""
    if len(a) != len(b):
        raise ValueError("rater vectors must be the same length")
    n = len(a)
    if n == 0:
        return None, 0.0, 0.0, "no items"

    _, ma, mb, labels = _tables(a, b)
    po = sum(1 for x, y in zip(a, b) if x == y) / n
    pe = sum((ma[l] / n) * (mb[l] / n) for l in labels)

    if abs(1.0 - pe) < 1e-12:
        return None, po, pe, (
            "kappa is undefined: both raters used a single label, so chance "
            "agreement is 1.0 and there is no variance to correct against "
            f"(observed agreement {po:.3f})")
    return (po - pe) / (1.0 - pe), po, pe, ""


def bootstrap_ci(a: list[str], b: list[str], seed: int = 20260803,
                 iterations: int = 2000, alpha: float = 0.05
                 ) -> tuple[float | None, float | None]:
    """Percentile bootstrap interval over items. Seeded, so it reproduces."""
    n = len(a)
    if n < 2:
        return None, None
    r = derive_rng(seed, "kappa_bootstrap", n)
    draws: list[float] = []
    for _ in range(iterations):
        idx = [r.randrange(n) for _ in range(n)]
        k, _, _, _ = cohen_kappa([a[i] for i in idx], [b[i] for i in idx])
        if k is not None:
            draws.append(k)
    if len(draws) < iterations * 0.5:
        return None, None      # too many degenerate resamples to trust
    draws.sort()
    lo = draws[int((alpha / 2) * len(draws))]
    hi = draws[min(len(draws) - 1, int((1 - alpha / 2) * len(draws)))]
    return lo, hi


def agreement(a: list[str], b: list[str], seed: int = 20260803,
              iterations: int = 2000) -> Agreement:
    kappa, po, pe, reason = cohen_kappa(a, b)
    confusion, ma, mb, labels = _tables(a, b)
    lo = hi = None
    if kappa is not None:
        lo, hi = bootstrap_ci(a, b, seed=seed, iterations=iterations)
    return Agreement(
        n=len(a), labels=labels, percent_agreement=round(po, 4), kappa=kappa,
        ci_low=lo, ci_high=hi, expected_agreement=round(pe, 4),
        confusion=confusion, marginals={"rater_a": ma, "rater_b": mb},
        undefined_reason=reason)


def interpret(kappa: float | None) -> str:
    """Landis & Koch bands. A convention, not a law — always quote the interval."""
    if kappa is None:
        return "undefined"
    for bound, name in ((0.0, "poor"), (0.20, "slight"), (0.40, "fair"),
                        (0.60, "moderate"), (0.80, "substantial")):
        if kappa <= bound:
            return name
    return "almost perfect"


def n_for_kappa_lower_bound(target: float = 0.61, expected: float = 0.75,
                            alpha: float = 0.05) -> int:
    """Roughly how many double-annotated items to put the LOWER bound above `target`.

    Uses the common approximation SE(kappa) ≈ sqrt((1 - kappa^2) / n) to size the
    overlap sample. Approximate by construction — it exists to stop a study being
    planned around a point estimate that its own interval cannot support.
    """
    import math
    if not 0 < target < expected < 1:
        raise ValueError("expected kappa must exceed the target, both in (0,1)")
    z = 1.959963984540054 if abs(alpha - 0.05) < 1e-9 else 1.959963984540054
    gap = expected - target
    return math.ceil((1 - expected ** 2) * (z / gap) ** 2)
