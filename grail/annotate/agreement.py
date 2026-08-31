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
    ac1: float | None = None
    ac1_ci_low: float | None = None
    ac1_ci_high: float | None = None
    paradox: str = ""
    confusion: dict = field(default_factory=dict)
    marginals: dict = field(default_factory=dict)
    undefined_reason: str = ""

    def as_dict(self) -> dict:
        return asdict(self)

    def meets(self, threshold: float) -> bool:
        """Threshold is met only if the LOWER bound clears it, not the estimate.

        Still keyed on kappa, deliberately: the criterion is pre-registered on
        kappa and moving the goalposts after seeing a deflated value would be
        exactly the manoeuvre pre-registration forbids. `meets_ac1` is provided
        alongside so the paradox case can be reported honestly rather than
        resolved by quietly switching statistic.
        """
        return self.ci_low is not None and self.ci_low >= threshold

    def meets_ac1(self, threshold: float) -> bool:
        return self.ac1_ci_low is not None and self.ac1_ci_low >= threshold


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


def gwet_ac1(a: list[str], b: list[str]) -> tuple[float | None, float, float, str]:
    """Gwet's AC1 — chance-corrected agreement that survives skewed marginals.

    Cohen's kappa estimates chance agreement as the product of the raters'
    marginals, which assumes they label independently at their observed rates.
    When one category dominates, that estimate approaches the observed agreement
    and kappa collapses toward zero however well the raters actually agree. This
    is the KAPPA PARADOX, and it is not a curiosity here: on transparency, most
    explanations are expected to be adequate, so the marginals are skewed by
    construction.

    The size of the problem, on 120 items with 90% raw agreement:

        adequacy rate     raw     kappa    AC1
        92%               0.90     0.28    0.88
        85%               0.87     0.42    0.83
        75%               0.85     0.57    0.77
        50%               0.80     0.60    0.60

    Two raters agreeing on nine items in ten would be recorded as "fair"
    agreement at best, and a criterion of kappa >= 0.61 would fail — for a
    property of the label distribution rather than a property of the judge.

    Gwet estimates chance agreement from how concentrated the labels are overall
    rather than from the product of marginals, which removes that sensitivity.
    At balanced marginals the two statistics agree, so nothing is lost by
    reporting both — and reporting both is the point: they disagree exactly when
    the disagreement is diagnostic.
    """
    if len(a) != len(b):
        raise ValueError("rater vectors must be the same length")
    n = len(a)
    if n == 0:
        return None, 0.0, 0.0, "no items"

    _, ma, mb, labels = _tables(a, b)
    po = sum(1 for x, y in zip(a, b) if x == y) / n
    k = len(labels)
    if k < 2:
        return None, po, 0.0, (
            "AC1 is undefined: only one label was used, so there is no "
            f"classification to correct (observed agreement {po:.3f})")

    # pi_l is the mean prevalence of label l across the two raters
    pe = sum(((ma[l] / n + mb[l] / n) / 2) * (1 - (ma[l] / n + mb[l] / n) / 2)
             for l in labels) / (k - 1)
    if abs(1.0 - pe) < 1e-12:
        return None, po, pe, "AC1 is undefined: chance agreement is 1.0"
    return (po - pe) / (1.0 - pe), po, pe, ""


def paradox_warning(kappa: float | None, ac1: float | None,
                    percent_agreement: float) -> str:
    """Flag the case where the two statistics tell opposite stories.

    Returned as text rather than a boolean because the reader has to decide
    which statistic to believe, and that decision needs the reason in front of
    it. High raw agreement with low kappa and high AC1 is the signature.
    """
    if kappa is None or ac1 is None:
        return ""
    if percent_agreement >= 0.80 and kappa < 0.61 <= ac1:
        return (f"KAPPA PARADOX: raters agreed on {percent_agreement:.0%} of items, "
                f"but kappa is {kappa:.2f} while AC1 is {ac1:.2f}. One label "
                "dominates, so kappa's chance-agreement estimate is close to the "
                "observed agreement and the statistic is deflated by the label "
                "distribution rather than by the raters. Report both; a criterion "
                "written on kappa alone will fail here for the wrong reason.")
    return ""


def bootstrap_ci(a: list[str], b: list[str], seed: int = 20260803,
                 iterations: int = 2000, alpha: float = 0.05,
                 statistic=None) -> tuple[float | None, float | None]:
    """Percentile bootstrap interval over items. Seeded, so it reproduces.

    `statistic` defaults to Cohen's kappa; pass `gwet_ac1` for an AC1 interval.
    Both are resampled the same way so their intervals are comparable.
    """
    stat = statistic or cohen_kappa
    n = len(a)
    if n < 2:
        return None, None
    r = derive_rng(seed, "kappa_bootstrap", n)
    draws: list[float] = []
    for _ in range(iterations):
        idx = [r.randrange(n) for _ in range(n)]
        k, _, _, _ = stat([a[i] for i in idx], [b[i] for i in idx])
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
    ac1, _, _, _ = gwet_ac1(a, b)
    confusion, ma, mb, labels = _tables(a, b)
    lo = hi = alo = ahi = None
    if kappa is not None:
        lo, hi = bootstrap_ci(a, b, seed=seed, iterations=iterations)
    if ac1 is not None:
        alo, ahi = bootstrap_ci(a, b, seed=seed, iterations=iterations,
                                statistic=gwet_ac1)
    return Agreement(
        n=len(a), labels=labels, percent_agreement=round(po, 4), kappa=kappa,
        ci_low=lo, ci_high=hi, expected_agreement=round(pe, 4),
        ac1=ac1, ac1_ci_low=alo, ac1_ci_high=ahi,
        paradox=paradox_warning(kappa, ac1, po),
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
