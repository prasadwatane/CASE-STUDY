# Evaluation protocol — definitions, margin, assumptions, matrix

Status: **draft for pre-registration, not yet signed.** Four decisions are still
open; they are listed in `PREREGISTRATION.md` and marked **[OPEN n]** below.
Nothing here has been evaluated on data. Simulation figures come from
`docs/expose/power_sim.py` and are design inputs, not results.

---

## 1. Notation

- Items `i = 1..n`. An item is a (probe, model) pair on the transparency docket.
- Labels `y ∈ {adequate, inadequate}`. `cannot judge` is recorded separately and
  its rate reported per rater; items carrying it are excluded from agreement
  statistics and counted **[OPEN 4]**.
- Raters `A`, `B` (human, independent, blind). Judge `J` (phi-4, pinned).
  Rule-based scorer `Q`. Arbitrated reference `R*`.
- Bootstrap: percentile, over items, 10,000 resamples, seeded.

## 2. Agreement (RQ1)

For two raters with 2×2 table cells `a` (both adequate), `d` (both inadequate),
`b`, `c` (disagreements), `n = a+b+c+d`:

| Quantity | Definition |
|---|---|
| Raw agreement | `p_o = (a + d) / n` |
| Cohen's κ | `κ = (p_o − p_e) / (1 − p_e)`, `p_e = p_A·p_B + (1−p_A)(1−p_B)`, with `p_A`, `p_B` each rater's share of `adequate` |
| Gwet's AC1 | `AC1 = (p_o − p_e′) / (1 − p_e′)`, `p_e′ = 2π(1−π)`, `π = (p_A + p_B)/2` |
| Prevalence index | `PI = |a − d| / n` |
| Bias index | `BI = |b − c| / n` |

All five are reported together with the marginals, always.

**S1 (human ceiling).** Met when the two-sided 95% lower bootstrap bound of the
primary statistic between A and B is ≥ 0.61 on the double-rated items.
**[OPEN 1]** The primary statistic is κ in exposé rev2 (Table 1) and AC1 in the
filed amendment and in `agreement.meets_primary`. One of the two must be chosen
before signing; the consequence is quantified in §6.

**S2 (non-inferiority, judge as third rater).**

```
D = ½ [ κ(J, A) + κ(J, B) ] − κ(A, B)
H0: D ≤ −δ      H1: D > −δ      δ = 0.10
```

Met when the one-sided 95% lower bootstrap bound of `D` is above −δ. Not met
when the upper bound is below −δ. Otherwise **undetermined**. The arbitrated
label `R*` is not used here: a label built from both raters is an easier target
than either rater alone.

**S2b (non-trivial judge).** `Δ = κ(J, R*) − κ(Q, R*)`; met when the one-sided
95% lower bootstrap bound of `Δ` is above 0, on identical items. A
majority-class scorer is reported alongside (its κ is 0 by construction, so
accuracy, precision, recall and F1 on the `inadequate` class are given for all
three scorers).

## 3. Selective automation (RQ2)

The judge emits a label `g(x)` and a nonconformity score `s(x)`. The gate accepts
when `s(x) ≤ τ`. **[OPEN 6]** Which score: the exposé specifies the disagreement of
five prompt paraphrases at temperature 0, on the stated ground that identical runs
at temperature 0 are identical. The case-study judge in fact runs at temperature
0.3, and its existing five-run self-agreement varies on 13% of items (see
`05_findings_2026-11-16.md`). Either score is usable; one must be named primary.

| Quantity | Definition |
|---|---|
| Coverage | `φ(τ) = P( s(x) ≤ τ )`; empirically `n_τ / m` on `m` calibration items |
| Selective error | `R(τ) = P( g(x) ≠ R*(x) | s(x) ≤ τ )`; empirically `k_τ / n_τ` |
| Certified bound | `U(τ) = BetaInv(1 − δ; k_τ + 1, n_τ − k_τ)` (exact Clopper–Pearson, one-sided) |
| Guarantee | `P( R(τ̂) ≤ α ) ≥ 1 − δ`, with `α = δ = 0.05` |

Threshold search: candidates `τ_1 < … < τ_G` are fixed in advance as the
0.50, 0.55, …, 1.00 quantiles of `s` on the **unlabelled** docket. They are
tested in that order, each at level δ; the search stops at the first candidate
whose bound exceeds α, and `τ̂` is the last one that passed (fixed-sequence
testing, family-wise error ≤ δ without a Bonferroni penalty).

**S3.** Met when some `τ̂` passes with `φ(τ̂) ≥ 0.50`.

What the arithmetic already implies (exact, no data needed):

| Errors among accepted items | 0 | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|---|
| Accepted items needed for `U ≤ 0.05` | 59 | 93 | 124 | 153 | 181 | 208 |

With 300 labelled items and 50% coverage, 150 items are accepted, so S3 can be
met only if the judge makes **at most 2 errors** on them.

### Assumptions the guarantee rests on

1. **Exchangeability.** Calibration items and the items the gate is later applied
   to are drawn from the same distribution: same docket, same audited models,
   same probe families, same judge version and prompts. The bound says nothing
   about a new model, a new sub-sector or a re-prompted judge.
2. **Sampling design. [OPEN 2]** The 300-item study is stratified (it oversamples
   high-confidence and borderline judge items). A stratified sample is not
   exchangeable with the docket, so a single Clopper–Pearson bound over the pooled
   sample does not certify the docket-level risk. Either (a) the bound is computed
   per stratum at level δ/S and combined with the docket's stratum weights, or
   (b) a simple-random calibration subset is drawn and the strata are kept for
   diagnosis only. This must be fixed before labels are unblinded.
3. **Reference as truth.** Error is measured against `R*`. Where humans disagree,
   `R*` is itself uncertain; the bound certifies agreement with the arbitrated
   reference, not correctness in a deeper sense. S1 is what licenses this.
4. **No reuse.** Score definition, paraphrases and the threshold grid are fixed
   before calibration labels exist; calibration items are never used for prompt
   tuning. Items used to develop the score are excluded from calibration.
5. **Marginal, not conditional.** The guarantee holds over the draw of the
   calibration set, on average over items. It is not a per-item, per-model or
   per-subgroup guarantee unless calibrated separately for that slice.
6. **Not legal conformity.** A certified selective error is a statement about the
   measuring instrument. It does not establish that a system conforms with the
   EU AI Act.

## 4. Sequential allocation (RQ3)

Requirements `r = 1..R` (currently `R = 16`: four models × three fairness strata
plus robustness). A policy `π` at budget `B` buys `n_r` units of requirement `r`
at unit cost `c_r` and returns a verdict `v_r(π, B)` that is either determinate
or UNDETERMINED. The reference `v_r*` is the verdict from all committed units.

| Quantity | Definition |
|---|---|
| Cost | `C(π, B) = Σ_r c_r · n_r` |
| Coverage | `(1/R) · #{ r : v_r determinate }` |
| Verdict fidelity | `#{ r : v_r determinate and v_r = v_r* } / #{ r : v_r determinate }` |
| Contradictions | `#{ r : v_r determinate and v_r ≠ v_r* }` |
| Saving | `1 − C(π, B) / C(static, B)` |

Two properties of these definitions are stated rather than left implicit. A
determinate verdict where the reference is UNDETERMINED counts against fidelity,
because it was reached on a subset of evidence the full set does not support.
And the reference is the static policy at full budget, so static fidelity is 1.0
there by construction.

**S4.** Met when the corrected policy has fidelity ≥ 0.90 × static fidelity and
cost ≤ 0.80 × static cost at the matched budget. **[OPEN 5]** Two things are not
yet fixed: (a) whether the bounds are the per-seed range or a bootstrap CI of the
mean over seeds; (b) a coverage condition, without which a policy that never
commits satisfies S4. Both were identified after the development replay was run
(16 Nov) and must be recorded as such.

Case-study baseline (replay, 6 seeds, full budget 58,220): static coverage 0.50,
fidelity 1.00; uncorrected adaptive coverage 0.65, spend 29,989, fidelity 0.78.

## 5. The non-inferiority margin δ = 0.10

| Argument | Evidence |
|---|---|
| It is half a Landis–Koch band | Bands are 0.20 wide. A judge within 0.10 of a ceiling of 0.71 or higher stays in "substantial". |
| It is about two standard errors of the thing being compared | At n = 300 and κ ≈ 0.70 the sampling SD of κ between two humans is 0.044 (simulation). Two human pairs would routinely differ by this much. |
| A tighter margin is not testable at this budget | Power for a judge exactly as good as a human, n = 300, ceiling 0.70: **0.35** at δ = 0.05, **0.79** at δ = 0.10, **0.97** at δ = 0.15. |
| What it tolerates, stated plainly | At 70% prevalence and a ceiling of 0.70, humans err on 7.1% of items; a judge sitting exactly on the margin errs on 12.6%. δ = 0.10 therefore admits a judge with roughly 1.8 times the human error rate. |

The margin is a convention fixed before data, not a derived quantity. Results at
δ = 0.05 and δ = 0.15 are reported as sensitivity analyses and carry no
confirmatory weight.

## 6. Sizing (simulation; floors, not forecasts)

Independent symmetric errors, 1,500 simulated studies × 1,000 resamples. Full
grid in `power_results.md`.

**S1 at n = 300 double-rated items**

| True human κ | Prevalence 0.70: κ criterion | Prevalence 0.70: AC1 criterion | Prevalence 0.50: κ | Prevalence 0.50: AC1 |
|---|---|---|---|---|
| 0.70 | 0.49 | 0.96 | 0.55 | 0.58 |
| 0.75 | 0.87 | 1.00 | 0.93 | 0.93 |
| 0.80 | 0.99 | 1.00 | 1.00 | 1.00 |

**S2 at prevalence 0.70, ceiling κ = 0.70**

| n | Judge = human | Judge 30% fewer errors | Judge at the margin (type I) |
|---|---|---|---|
| 120 | 0.48 | 0.75 | 0.06 |
| 300 | 0.79 | 0.98 | 0.07 |
| 500 | 0.93 | 1.00 | 0.06 |

Three consequences for the design:

1. **Under the κ criterion, S1 is a coin flip if the true ceiling is 0.70.** The
   exposé's sizing figures (39 / 86 / 242 items) are where the lower bound is
   *expected* to reach 0.61, which is about 40–50% power, not 80%. Either the
   target ceiling is κ ≥ 0.75 (raw agreement ≈ 0.89), or AC1 is primary.
2. **AC1 ≥ 0.61 is a lower bar than κ ≥ 0.61 on a skewed docket.** At 70%
   prevalence a κ of 0.70 corresponds to an AC1 of 0.76. If v1.1 pushes
   prevalence towards 50%, as its own draft predicts, the two coincide and the
   choice stops mattering.
3. **The S2 test is slightly liberal.** Its simulated type-I error is 0.06–0.07
   at n ≥ 120 against a nominal 0.05. **[OPEN 3]** Either a BCa interval replaces
   the percentile interval, or the liberal rate is stated next to every S2 result.

The exposé quotes S2 power of roughly 0.4 at 120 and 0.6–0.75 at 300; this
simulation gives 0.48 and 0.79. The script that produced the exposé's figures is
not in the repository, so the difference cannot be traced. The figures above are
the reproducible ones.

## 7. Evaluation matrix

| Hypothesis | Data | Baselines | Metric | Criterion | Decision |
|---|---|---|---|---|---|
| H1a ceiling | 300 double-rated transparency items, guideline v1.1 frozen | Round-1 agreement (κ = 0.069) as pre-revision reference | κ, AC1, raw agreement, PI, BI with intervals | **S1** lower bound ≥ 0.61 | met / not met / undetermined |
| H1b judge non-inferior | Same items, judge labels | Human rater as comparator | `D` with one-sided bound | **S2** bound > −0.10 | three-way |
| H1c judge non-trivial | Same items, arbitrated `R*` | Rule-based scorer; majority class | `Δ`, plus precision / recall / F1 | **S2b** bound > 0 | three-way |
| H2 certified gate | Calibration items with `R*`; unlabelled docket for the grid | Ungated judge; judge self-agreement score | Coverage, selective error, CP bound, risk–coverage curve | **S3** error ≤ 5% at coverage ≥ 50% | three-way |
| H3 sequential allocation | Logged responses, 16 requirements, replay | Static; uncorrected adaptive | Cost, coverage, fidelity, contradictions | **S4** fidelity ≥ 90% of static at ≤ 80% cost | three-way |
| Traceability | Ledger | — | Share of findings with clause id, evidence type, sample kind | **S5** 100%, hash chain intact | met / not met |
| C4 breadth | New CORE sample on age; one API model | Case-study title-swap result | Paired discordance, exact McNemar, four-fifths ratio | Descriptive | reported |

Rules that apply to every row: no number without its interval; a criterion is met
when the bound clears it, never the point estimate; negative and undetermined
outcomes are results; instrument controls run alongside and are excluded from
headline figures.
