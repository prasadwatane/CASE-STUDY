"""Sample sizing — computed, not asserted, and sized for the test actually run.

The CORE sample sizes in `config.PROBE_CORE_N` are derived here at import time
rather than typed in as round numbers, so the number in config can always be
justified and re-derived when a threshold changes.

**The distinction that matters.** A margin on a single rate and the power to
detect a difference between two rates are not the same calculation, and using the
first where the second is needed under-powers the study silently:

* `n_for_proportion` — how many observations to estimate ONE rate within a
  margin. Correct for consistency (modal-agreement rate) and for transparency
  (share of adequate explanations).
* `n_for_two_proportions` — how many per arm to DETECT a gap of a given size
  between two rates. This is the fairness calculation. Its interval is a factor
  of sqrt(2) wider than the single-rate one, and adding power on top means the
  requirement is roughly four times larger than the naive figure.
* `n_discordant_for_mcnemar` — robustness is a paired test, so its sample size
  depends on how often a perturbation actually flips a decision. That rate is
  unknown until a pilot measures it, so this returns the discordant pairs
  required and `n_pairs_for_mcnemar` converts it under an assumed flip rate.

Nothing here is used at scoring time — the jury owns the inference. This module
only decides how many probes to pre-register.
"""
from __future__ import annotations

import math

Z_95 = 1.959963984540054      # two-sided normal quantile at alpha = 0.05
Z_POWER_80 = 0.8416212335729143   # one-sided quantile at 80% power


def z_two_sided(alpha: float) -> float:
    """Normal quantile for a two-sided test at level `alpha`."""
    return _norm_ppf(1.0 - alpha / 2.0)


def z_power(power: float) -> float:
    return _norm_ppf(power)


def _norm_ppf(p: float) -> float:
    """Inverse standard normal CDF (Acklam's rational approximation).

    Accurate to about 1e-9 over the range that matters here, which keeps this
    module dependency-free rather than pulling scipy in for one function.
    """
    if not 0.0 < p < 1.0:
        raise ValueError("p must be in (0, 1)")
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00]
    p_low, p_high = 0.02425, 1 - 0.02425
    if p < p_low:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / \
               ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
    if p > p_high:
        q = math.sqrt(-2 * math.log(1 - p))
        return -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / \
               ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
    q = p - 0.5
    r = q * q
    return (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q / \
           (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1)


# --- one rate ---------------------------------------------------------------
def n_for_proportion(margin: float, p: float = 0.5, alpha: float = 0.05) -> int:
    """Observations needed to estimate ONE proportion within +/- `margin`."""
    if not 0 < margin < 1:
        raise ValueError("margin must be in (0, 1)")
    z = z_two_sided(alpha)
    return math.ceil(z * z * p * (1.0 - p) / (margin * margin))


def margin_for_n(n: int, p: float = 0.5, alpha: float = 0.05) -> float:
    """The margin of error a given sample size buys for ONE proportion."""
    if n <= 0:
        raise ValueError("n must be positive")
    return z_two_sided(alpha) * math.sqrt(p * (1.0 - p) / n)


# --- the difference between two rates (fairness) ----------------------------
def n_for_two_proportions(mde: float, power: float = 0.80, alpha: float = 0.05,
                          p_bar: float = 0.5) -> int:
    """Per-arm size to detect a gap of `mde` between two rates.

        n = 2 * (z_alpha/2 + z_beta)^2 * p_bar(1 - p_bar) / mde^2

    `p_bar = 0.5` is the worst case: it maximises the variance, so the answer is
    conservative whatever the true approval rate turns out to be.
    """
    if not 0 < mde < 1:
        raise ValueError("mde must be in (0, 1)")
    z_a, z_b = z_two_sided(alpha), z_power(power)
    return math.ceil(2.0 * (z_a + z_b) ** 2 * p_bar * (1.0 - p_bar) / (mde * mde))


def mde_for_two_proportions(n_per_arm: int, power: float = 0.80,
                            alpha: float = 0.05, p_bar: float = 0.5) -> float:
    """The smallest gap a given per-arm size can detect at `power`."""
    if n_per_arm <= 0:
        raise ValueError("n_per_arm must be positive")
    z_a, z_b = z_two_sided(alpha), z_power(power)
    return (z_a + z_b) * math.sqrt(2.0 * p_bar * (1.0 - p_bar) / n_per_arm)


def ci_halfwidth_for_gap(n_per_arm: int, p_bar: float = 0.5,
                         alpha: float = 0.05) -> float:
    """Half-width of the confidence interval on a gap — NOT a power calculation.

    This is the number an unpowered study quotes. It is roughly the effect a
    study has a coin-flip chance of detecting, which is why `mde_for_two_proportions`
    is the honest figure to report.
    """
    return z_two_sided(alpha) * math.sqrt(2.0 * p_bar * (1.0 - p_bar) / n_per_arm)


# --- paired flips (robustness / McNemar) ------------------------------------
def n_discordant_for_mcnemar(psi: float, power: float = 0.80,
                             alpha: float = 0.05) -> int:
    """Discordant pairs needed to show flips are asymmetric.

    `psi` is the share of discordant pairs expected to flip in one direction;
    0.5 is pure noise, so the further from 0.5 the easier to detect.
    """
    if not 0 < psi < 1 or psi == 0.5:
        raise ValueError("psi must be in (0, 1) and not exactly 0.5")
    z_a, z_b = z_two_sided(alpha), z_power(power)
    num = (z_a * 0.5 + z_b * math.sqrt(psi * (1.0 - psi))) ** 2
    return math.ceil(num / (psi - 0.5) ** 2)


def n_pairs_for_mcnemar(psi: float, flip_rate: float, power: float = 0.80,
                        alpha: float = 0.05) -> int:
    """Base cases needed, given how often a perturbation flips a decision at all.

    `flip_rate` is not knowable in advance — it has to come from a pilot. That is
    the point: robustness sizing is contingent, and pretending otherwise would be
    a made-up number.
    """
    if not 0 < flip_rate <= 1:
        raise ValueError("flip_rate must be in (0, 1]")
    return math.ceil(n_discordant_for_mcnemar(psi, power, alpha) / flip_rate)


# --- reporting --------------------------------------------------------------
def describe_gap(n_per_arm: int, power: float = 0.80, alpha: float = 0.05) -> str:
    return (f"n={n_per_arm}/arm detects a gap of "
            f"{mde_for_two_proportions(n_per_arm, power, alpha) * 100:.1f} pp at "
            f"{power:.0%} power (CI half-width {ci_halfwidth_for_gap(n_per_arm) * 100:.1f} pp)")


def describe_rate(n: int, p: float = 0.5) -> str:
    return f"n={n} estimates a rate to +/-{margin_for_n(n, p) * 100:.1f} pp at 95%"
