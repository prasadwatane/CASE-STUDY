"""Sample sizing — computed, not asserted.

The CORE sample sizes in `config.PROBE_CORE_N` are not round numbers picked by
feel; they come from the standard normal-approximation sample size for a
proportion. This module recomputes them so the number in config can always be
justified (and re-derived if the margin ever changes).

    n = z^2 * p(1-p) / e^2

with p = 0.5 (the worst case, maximising the variance) and z = 1.96 for 95%
confidence. n = 300 corresponds to a margin of e = 0.0566, i.e. an approval
rate estimated to about +/- 5.7 percentage points per group arm.

Nothing here is used at scoring time — the jury (a later stage) owns the
inference. This is only for choosing how many probes to pre-register.
"""
from __future__ import annotations

import math

Z_95 = 1.959963984540054   # two-sided normal quantile at 95%


def n_for_proportion(margin: float, p: float = 0.5, z: float = Z_95) -> int:
    """Sample size per arm to estimate a proportion within +/- `margin`."""
    if not 0 < margin < 1:
        raise ValueError("margin must be in (0, 1)")
    return math.ceil(z * z * p * (1.0 - p) / (margin * margin))


def margin_for_n(n: int, p: float = 0.5, z: float = Z_95) -> float:
    """The inverse: the margin of error a given per-arm sample size buys."""
    if n <= 0:
        raise ValueError("n must be positive")
    return z * math.sqrt(p * (1.0 - p) / n)


def describe(n: int, p: float = 0.5) -> str:
    return (f"n={n} per arm -> +/-{margin_for_n(n, p) * 100:.1f} pp "
            f"at 95% confidence (p={p})")
