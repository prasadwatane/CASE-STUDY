"""Power and sample-size simulation for the annotation study (S1, S2).

NOT DATA. Nothing here is an observation. The script answers two design
questions before any round-2 label exists:

  S1  How many double-rated items put the LOWER bootstrap bound of the
      human-human agreement statistic at or above 0.61?
  S2  How many are needed to show the judge NON-INFERIOR to a human rater at
      margin 0.10, with the judge treated as a third rater?

Generative model (stated, so it can be attacked)
------------------------------------------------
Each item has a latent binary truth, `adequate` with probability `prevalence`.
Raters A and B each report the truth and flip it independently with probability
e_h; the judge flips it independently with probability e_j. e_h is solved so
that the population Cohen's kappa between A and B equals the stated ceiling.

Independent, symmetric errors are the OPTIMISTIC case. Real raters differ in
severity and real judges make errors correlated with item difficulty; both make
the required n larger. Read every number below as a floor.

Statistics
----------
S1: percentile bootstrap over items, two-sided 95% (lower = 2.5th percentile),
    as in grail/annotate/agreement.py. Reported for Cohen's kappa and Gwet's AC1.
S2: D = mean_r[ kappa(J, r) ] - kappa(A, B),  r in {A, B}.
    Non-inferiority is declared when the one-sided 95% lower bootstrap bound of
    D (5th percentile) is above -margin.

The item-level bootstrap is drawn as a multinomial over the eight (A, B, J)
response patterns, which is the same resampling and far faster.

    python docs/expose/power_sim.py                 # full grid, writes JSON + MD
    python docs/expose/power_sim.py --reps 500      # quick look
"""
from __future__ import annotations

import argparse
import itertools
import json
import os

import numpy as np

SEED = 20261116
PATTERNS = np.array(list(itertools.product([0, 1], repeat=3)))  # columns A, B, J


# ------------------------------------------------------------ population
def pattern_probs(prev: float, e_h: float, e_j: float) -> np.ndarray:
    """P(A=a, B=b, J=j) under the generative model."""
    p = np.zeros(8)
    for t, pt in ((1, prev), (0, 1 - prev)):
        for i, (a, b, j) in enumerate(PATTERNS):
            pa = (1 - e_h) if a == t else e_h
            pb = (1 - e_h) if b == t else e_h
            pj = (1 - e_j) if j == t else e_j
            p[i] += pt * pa * pb * pj
    return p


def _pair_tables(counts: np.ndarray, x: int, y: int):
    """Agreement and marginals for raters in columns x, y. counts: (..., 8)."""
    n = counts.sum(axis=-1)
    both1 = counts[..., (PATTERNS[:, x] == 1) & (PATTERNS[:, y] == 1)].sum(axis=-1)
    both0 = counts[..., (PATTERNS[:, x] == 0) & (PATTERNS[:, y] == 0)].sum(axis=-1)
    x1 = counts[..., PATTERNS[:, x] == 1].sum(axis=-1)
    y1 = counts[..., PATTERNS[:, y] == 1].sum(axis=-1)
    po = (both1 + both0) / n
    return po, x1 / n, y1 / n


def kappa(counts: np.ndarray, x: int, y: int) -> np.ndarray:
    po, px, py = _pair_tables(counts, x, y)
    pe = px * py + (1 - px) * (1 - py)
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(pe < 1, (po - pe) / (1 - pe), np.nan)


def ac1(counts: np.ndarray, x: int, y: int) -> np.ndarray:
    po, px, py = _pair_tables(counts, x, y)
    q = (px + py) / 2
    pe = 2 * q * (1 - q)
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(pe < 1, (po - pe) / (1 - pe), np.nan)


def pop_kappa_hh(prev: float, e_h: float) -> float:
    return float(kappa(pattern_probs(prev, e_h, 0.0)[None, :], 0, 1)[0])


def pop_D(prev: float, e_h: float, e_j: float) -> float:
    p = pattern_probs(prev, e_h, e_j)[None, :]
    return float((kappa(p, 2, 0)[0] + kappa(p, 2, 1)[0]) / 2 - kappa(p, 0, 1)[0])


def solve(f, lo: float, hi: float, target: float, iters: int = 80) -> float:
    """Bisection for a monotone-decreasing f."""
    for _ in range(iters):
        mid = (lo + hi) / 2
        if f(mid) > target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


# ------------------------------------------------------------ simulation
def run_cell(prev, ceiling, e_j_factor, n, reps, boots, margin, rng, e_j_abs=None):
    e_h = solve(lambda e: pop_kappa_hh(prev, e), 1e-6, 0.4999, ceiling)
    e_j = e_j_abs if e_j_abs is not None else e_h * e_j_factor
    p = pattern_probs(prev, e_h, e_j)
    s1_k = s1_a = s2 = 0
    for _ in range(reps):
        study = rng.multinomial(n, p)
        bs = rng.multinomial(n, study / n, size=boots)
        k_ab = kappa(bs, 0, 1)
        a_ab = ac1(bs, 0, 1)
        d = (kappa(bs, 2, 0) + kappa(bs, 2, 1)) / 2 - k_ab
        if np.isnan(k_ab).mean() < 0.5:
            s1_k += np.nanpercentile(k_ab, 2.5) >= 0.61
        if np.isnan(a_ab).mean() < 0.5:
            s1_a += np.nanpercentile(a_ab, 2.5) >= 0.61
        if np.isnan(d).mean() < 0.5:
            s2 += np.nanpercentile(d, 5.0) > -margin
    return {
        "prevalence": prev, "ceiling_kappa": ceiling, "n": n,
        "e_human": round(e_h, 4), "e_judge": round(e_j, 4),
        "true_D": round(pop_D(prev, e_h, e_j), 4),
        "p_S1_kappa": round(float(s1_k) / reps, 3),
        "p_S1_ac1": round(float(s1_a) / reps, 3),
        "p_S2_noninferior": round(float(s2) / reps, 3),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", type=int, default=2000)
    ap.add_argument("--boots", type=int, default=2000)
    ap.add_argument("--margin", type=float, default=0.10)
    ap.add_argument("--prev", type=float, nargs="*", default=[0.70, 0.77, 0.50],
                    help="prevalences to simulate in this call (parts are cached)")
    ap.add_argument("--out", default=os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "protocol"))
    args = ap.parse_args()
    ns = [30, 60, 86, 120, 200, 242, 300, 400, 500]
    os.makedirs(args.out, exist_ok=True)
    part = lambda pv: os.path.join(args.out, f".power_part_{pv:.2f}.json")
    for prev in args.prev:
        # one independent, reproducible stream per prevalence, so the grid can
        # be run in pieces and still give the same numbers
        rng = np.random.default_rng([SEED, int(round(prev * 100))])
        rows = []
        for ceiling in (0.70, 0.75, 0.80):
            e_h = solve(lambda e: pop_kappa_hh(prev, e), 1e-6, 0.4999, ceiling)
            # judge exactly at the margin: the null. Rejection rate here is the
            # type-I error of the S2 test and should sit near 0.05.
            e_null = solve(lambda e: pop_D(prev, e_h, e), e_h, 0.4999, -args.margin)
            scenarios = [("judge = human", 1.0, None),
                         ("judge 30% fewer errors", 0.7, None),
                         ("judge at the margin (null)", None, e_null)]
            for label, factor, e_abs in scenarios:
                for n in ns:
                    r = run_cell(prev, ceiling, factor, n, args.reps, args.boots,
                                 args.margin, rng, e_j_abs=e_abs)
                    r["scenario"] = label
                    rows.append(r)
                    print(r, flush=True)
        with open(part(prev), "w") as fh:
            json.dump(rows, fh)

    all_prev = (0.70, 0.77, 0.50)
    if not all(os.path.exists(part(pv)) for pv in all_prev):
        print("parts so far:", [pv for pv in all_prev if os.path.exists(part(pv))])
        return
    rows = []
    for pv in all_prev:
        rows += json.load(open(part(pv)))

    os.makedirs(args.out, exist_ok=True)
    meta = {"seed": SEED, "reps": args.reps, "boots": args.boots,
            "margin": args.margin, "note": "SIMULATION, not observed agreement"}
    with open(os.path.join(args.out, "power_results.json"), "w") as fh:
        json.dump({"meta": meta, "rows": rows}, fh, indent=1)

    # ---- markdown summary
    md = ["# Power simulation results (S1, S2)", "",
          "**Simulation, not data.** Produced by `docs/expose/power_sim.py` "
          f"(seed {SEED}, {args.reps} studies x {args.boots} bootstrap resamples, "
          f"margin {args.margin}). Independent symmetric errors: every figure is a floor on n.", ""]
    for prev in (0.70, 0.77, 0.50):
        md += [f"## Prevalence of `adequate` = {prev:.2f}", ""]
        for ceiling in (0.70, 0.75, 0.80):
            md += [f"### Human ceiling kappa = {ceiling:.2f}", "",
                   "| n | P(S1: kappa LB >= 0.61) | P(S1: AC1 LB >= 0.61) | "
                   "P(S2) judge = human | P(S2) judge 30% better | P(S2) at margin (type I) |",
                   "|---|---|---|---|---|---|"]
            for n in ns:
                sel = {r["scenario"]: r for r in rows
                       if r["prevalence"] == prev and r["ceiling_kappa"] == ceiling and r["n"] == n}
                a = sel["judge = human"]
                md.append(f"| {n} | {a['p_S1_kappa']:.2f} | {a['p_S1_ac1']:.2f} | "
                          f"{a['p_S2_noninferior']:.2f} | "
                          f"{sel['judge 30% fewer errors']['p_S2_noninferior']:.2f} | "
                          f"{sel['judge at the margin (null)']['p_S2_noninferior']:.2f} |")
            md.append("")
    with open(os.path.join(args.out, "power_results.md"), "w") as fh:
        fh.write("\n".join(md) + "\n")
    print("written", args.out)


if __name__ == "__main__":
    main()
