import pytest

from grail.annotation.agreement import cohen_kappa, fleiss_kappa, score_study


def test_perfect_agreement_is_one():
    a = {f"i{k}": ("x" if k % 2 else "y") for k in range(20)}
    r = cohen_kappa(a, dict(a), n_boot=200)
    assert r.kappa == pytest.approx(1.0)


def test_single_label_is_undefined_not_zero():
    a = {f"i{k}": "adequate" for k in range(10)}
    r = cohen_kappa(a, dict(a), n_boot=50)
    assert r.kappa is None and r.percent_agreement == 1.0
    assert fleiss_kappa([a, dict(a)]).kappa is None


def test_chance_level_is_near_zero():
    import random
    rng = random.Random(1)
    a = {f"i{k}": rng.choice("ab") for k in range(400)}
    b = {f"i{k}": rng.choice("ab") for k in range(400)}
    r = cohen_kappa(a, b, n_boot=100)
    assert abs(r.kappa) < 0.15
    assert r.ci_low is not None and r.ci_low <= 0 <= r.ci_high


def test_kappa_never_without_marginals_and_ci():
    a = {f"i{k}": ("x" if k % 3 else "y") for k in range(30)}
    b = {f"i{k}": ("x" if k % 2 else "y") for k in range(30)}
    r = cohen_kappa(a, b, n_boot=100)
    assert r.marginals["a"] and r.marginals["b"]
    assert r.ci_low is not None


def test_pilot_round1_reproduces_committed_numbers():
    """Regression: the committed round-1 sheets score at chance."""
    from pathlib import Path
    from grail.annotation.agreement import load_sheet, load_meta
    d = Path(__file__).resolve().parents[1] / "data/annotation/finance/pilot_round1"
    if not d.exists():
        pytest.skip("pilot data not present")
    files = sorted(d.glob("rater_*.csv"))
    sheets = {f.stem: load_sheet(f) for f in files}
    rep = score_study(sheets, load_meta(files[0]))
    assert rep.n_items == 30
    assert rep.fleiss["kappa"] == pytest.approx(-0.045, abs=0.01)
    for v in rep.pairwise.values():
        assert v["ci_low"] < 0 < v["ci_high"]  # nothing distinguishable from chance
