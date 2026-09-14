"""How many double-annotated items does the ceiling need? A power study.

NOT DATA. Nothing this script writes is an observation, and it never produces a
rater sheet. It answers one question — *if* two raters agreed at some rate, what
would the study see? — by simulating pairs of labels under a known truth and
reading off the interval.

    python scripts/simulate_agreement.py
    python scripts/simulate_agreement.py --prevalence 0.77 --reps 4000

Two things make this worth running rather than reading off a table.

**The prevalence is measured, not assumed.** The Article 13(1) docket is heavily
skewed toward 'adequate' — the pilot returned 77% from one rater and 70% from the
other. Sample-size tables for kappa assume balanced marginals, and at this skew
they are wrong by a wide margin. The simulation uses the observed prevalence, so
the answer applies to the docket that exists.

**The criterion is on the LOWER BOUND.** A point estimate clearing 0.61 with an
interval spanning it is a small sample, not a validated instrument. So what is
computed here is the probability that the lower bound clears the threshold —
which is the only question the pre-registered criterion asks.

The outputs belong in the methods chapter as a sizing justification. They must
never be presented as agreement that was observed.
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from grail.probe.schema import derive_rng

ADEQUATE, INADEQUATE = "adequate", "inadequate"


def simulate_pair(n: int, agree_rate: float, prevalence: float, rng) -> tuple:
    """One simulated study: n items, two raters agreeing at `agree_rate`.

    The generative model is deliberately simple and stated rather than buried.
    A latent truth is drawn at `prevalence`; rater A reports it; rater B reports
    it with probability `agree_rate` and flips otherwise. This makes the raters
    exchangeable and their disagreement symmetric, which is the optimistic case —
    real raters differ in severity, and a severity difference lowers agreement
    further. So these sample sizes are a FLOOR, not a forecast.
    """
    a, b = [], []
    for _ in range(n):
        truth = ADEQUATE if rng.random() < prevalence else INADEQUATE
        a.append(truth)
        if rng.random() < agree_rate:
            b.append(truth)
        else:
            b.append(INADEQUATE if truth == ADEQUATE else ADEQUATE)
    return a, b


def _stats(pairs: list[tuple]) -> tuple:
    """(kappa, AC1) computed straight from the pairs. Two labels only.

    grail.annotate.agreement is the implementation of record and is what scores
    the real study. This is a stripped copy for the inner loop only: the
    simulation evaluates hundreds of thousands of resamples, and going through
    the full Agreement object — which builds confusion tables and its own
    bootstrap — is three orders of magnitude too slow. A test asserts the two
    agree, so this cannot drift into being a second definition.
    """
    n = len(pairs)
    if not n:
        return None, None
    po = sum(1 for x, y in pairs if x == y) / n
    pa = sum(1 for x, _ in pairs if x == ADEQUATE) / n
    pb = sum(1 for _, y in pairs if y == ADEQUATE) / n

    pe_k = pa * pb + (1 - pa) * (1 - pb)          # Cohen: product of marginals
    kappa = None if pe_k >= 1 else (po - pe_k) / (1 - pe_k)

    pi = (pa + pb) / 2                            # Gwet: chance agreement on a
    pe_g = 2 * pi * (1 - pi)                      # randomly-chosen category
    ac1 = None if pe_g >= 1 else (po - pe_g) / (1 - pe_g)
    return kappa, ac1


def _lower_bounds(pairs: list[tuple], rng, iterations: int) -> tuple:
    """Percentile bootstrap lower bounds for (kappa, AC1)."""
    n = len(pairs)
    ks, gs = [], []
    for _ in range(iterations):
        sample = [pairs[int(rng.random() * n)] for _ in range(n)]
        k, g = _stats(sample)
        if k is not None:
            ks.append(k)
        if g is not None:
            gs.append(g)
    lo = lambda xs: sorted(xs)[int(0.025 * len(xs))] if xs else None
    return lo(ks), lo(gs)


def power_at(n: int, agree_rate: float, prevalence: float, threshold: float,
             reps: int, seed: int, iterations: int = 300) -> dict:
    """Share of simulated studies whose LOWER BOUND clears the threshold."""
    rng = derive_rng(seed, "agreement_sim", n, int(agree_rate * 1000))
    ac1_hits = kappa_hits = 0
    ac1_pts, kappa_pts = [], []
    for _ in range(reps):
        a, b = simulate_pair(n, agree_rate, prevalence, rng)
        pairs = list(zip(a, b))
        k, g = _stats(pairs)
        klo, glo = _lower_bounds(pairs, rng, iterations)
        if g is not None:
            ac1_pts.append(g)
            if glo is not None and glo >= threshold:
                ac1_hits += 1
        if k is not None:
            kappa_pts.append(k)
            if klo is not None and klo >= threshold:
                kappa_hits += 1
    mean = lambda xs: sum(xs) / len(xs) if xs else float("nan")
    return {"n": n, "agree_rate": agree_rate,
            "ac1_power": ac1_hits / reps, "kappa_power": kappa_hits / reps,
            "ac1_mean": mean(ac1_pts), "kappa_mean": mean(kappa_pts)}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--prevalence", type=float, default=0.77,
                    help="share of items truly 'adequate'; pilot measured 0.77")
    ap.add_argument("--threshold", type=float, default=0.61)
    ap.add_argument("--reps", type=int, default=1500)
    ap.add_argument("--seed", type=int, default=20260914)
    ap.add_argument("--rates", type=float, nargs="*",
                    default=[0.95, 0.90, 0.85, 0.80, 0.72])
    ap.add_argument("--sizes", type=int, nargs="*",
                    default=[30, 60, 100, 150, 200, 300])
    args = ap.parse_args()

    print("=" * 78)
    print("  SIMULATION — NOT OBSERVED DATA")
    print("  No rater sheet is produced. Nothing here is an annotation.")
    print("=" * 78)
    print(f"  prevalence of 'adequate' : {args.prevalence:.2f}  (pilot: A 0.77, B 0.70)")
    print(f"  criterion                : LOWER BOUND of AC1 >= {args.threshold:.2f}")
    print(f"  replications per cell    : {args.reps}\n")

    print("Probability the criterion is met, by true raw agreement and sample size")
    print("(AC1 power / kappa power)\n")
    head = "  agree" + "".join(f"{n:>15}" for n in args.sizes)
    print(head)
    print("  " + "-" * (len(head) - 2))

    rows = []
    for rate in args.rates:
        cells = []
        for n in args.sizes:
            r = power_at(n, rate, args.prevalence, args.threshold,
                         args.reps, args.seed)
            rows.append(r)
            cells.append(f"{r['ac1_power']:>7.0%} /{r['kappa_power']:>5.0%}")
        print(f"  {rate:>5.0%}" + "".join(f"{c:>15}" for c in cells))

    print("\nMean point estimate by true agreement (n = 150):")
    for rate in args.rates:
        r = next(x for x in rows if x["agree_rate"] == rate and x["n"] == 150)
        print(f"  raw {rate:.0%}  ->  AC1 {r['ac1_mean']:.2f}   kappa {r['kappa_mean']:.2f}")

    print(f"""
READING THIS

  The kappa column is the amendment's argument in numbers. At a prevalence of
  {args.prevalence:.2f}, kappa's mean estimate sits far below AC1's for the same
  raw agreement, and its power to clear {args.threshold:.2f} stays low at every
  sample size shown. A study sized on kappa at this skew is a study designed to
  fail.

  The pilot's observed raw agreement was 72%. Read that row: no sample size in
  this table rescues it. More annotation cannot fix a guidelines problem, which
  is why the next step is a revision and a re-pilot rather than the main study.

  Find the row matching the agreement you expect AFTER revising the guidelines,
  and read off the smallest n whose power is acceptable. That is the sizing
  justification, and it is the only thing in this output that belongs in the
  thesis.

  These sizes are a FLOOR. The simulation makes the two raters exchangeable with
  symmetric disagreement; real raters differ in severity, which lowers agreement
  and raises the requirement.""")


if __name__ == "__main__":
    main()
