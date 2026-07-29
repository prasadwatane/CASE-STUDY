"""Deterministic solvers — the only thing allowed to produce a numeric gold.

A model is never asked to compute. Where a reference answer is arithmetic, it is
computed here in pure Python from arguments recorded in the seed bank, and the
gold carries the formula name and its inputs as provenance, so anyone can redo
the calculation by hand. That is what makes a computed gold **Green**: it is not
believed, it is reproduced.

Each formula is a plain function with no state. The registry at the bottom is
what the seed bank addresses by name; adding a formula is additive and never
changes an existing gold, because the formula name is part of the provenance.
"""
from __future__ import annotations

FORMULA_VERSION = "formulas/1.0.0"


def annuity_payment(principal: float, annual_rate: float, n_months: int) -> float:
    """Equal monthly instalment on an amortising loan.

        A = P * i / (1 - (1 + i)^-n),  i = annual_rate / 12

    The zero-rate case is the straight-line limit, handled separately because the
    closed form divides by zero there.
    """
    if n_months <= 0:
        raise ValueError("n_months must be positive")
    i = annual_rate / 12.0
    if i == 0:
        return principal / n_months
    return principal * i / (1.0 - (1.0 + i) ** (-n_months))


def compound_balance(principal: float, monthly_rate: float, months: int) -> float:
    """Balance after `months` of compounding with no repayment: P * (1 + r)^m."""
    if months < 0:
        raise ValueError("months must not be negative")
    return principal * (1.0 + monthly_rate) ** months


def dti_percent(monthly_debt: float, annual_income: float) -> float:
    """Debt-to-income ratio as a percentage of gross annual income."""
    if annual_income <= 0:
        raise ValueError("annual_income must be positive")
    return 100.0 * (monthly_debt * 12.0) / annual_income


def share_of_income_percent(instalment: float, monthly_net: float) -> float:
    """What share of monthly net income an instalment takes."""
    if monthly_net <= 0:
        raise ValueError("monthly_net must be positive")
    return 100.0 * instalment / monthly_net


def total_repaid_with_fee(principal: float, fee: float,
                          interest_total: float = 0.0) -> float:
    """Everything the borrower hands back: principal + fee + interest."""
    return principal + fee + interest_total


def total_interest(instalment: float, n_months: int, principal: float) -> float:
    """Interest paid over the life of a loan repaid in equal instalments."""
    return instalment * n_months - principal


REGISTRY = {
    "annuity_payment": annuity_payment,
    "compound_balance": compound_balance,
    "dti_percent": dti_percent,
    "share_of_income_percent": share_of_income_percent,
    "total_repaid_with_fee": total_repaid_with_fee,
    "total_interest": total_interest,
}

# How each formula's result is written into a gold answer.
_UNITS = {
    "annuity_payment": ("EUR", 2),
    "compound_balance": ("EUR", 2),
    "dti_percent": ("percent", 2),
    "share_of_income_percent": ("percent", 2),
    "total_repaid_with_fee": ("EUR", 2),
    "total_interest": ("EUR", 2),
}


def evaluate(spec: dict) -> tuple[float, str, dict]:
    """Run a seed-bank compute spec. Returns (value, formatted answer, provenance)."""
    name = spec["formula"]
    if name not in REGISTRY:
        raise KeyError(f"unknown formula '{name}' — the seed bank addresses a "
                       f"solver that does not exist (have: {sorted(REGISTRY)})")
    args = dict(spec.get("args", {}))
    value = REGISTRY[name](**args)
    unit, places = _UNITS[name]
    rounded = round(value, places)
    formatted = (f"{rounded:.{places}f} {unit}" if unit == "EUR"
                 else f"{rounded:.{places}f} {unit}")
    return value, formatted, {
        "method": "deterministic computation",
        "formula": name,
        "formula_version": FORMULA_VERSION,
        "args": args,
        "raw_value": value,
        "rounding": places,
        "recomputable": True,
    }
