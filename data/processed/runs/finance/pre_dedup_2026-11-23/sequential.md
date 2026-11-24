# RQ3 — sequential allocation results

Domain `finance` · 16 requirements · full budget 58,220 prompts · 40 replay seeds. Produced by `scripts/eval_sequential.py`.

## 1. Error rates under a known truth (simulation)

Share of simulated audits ending in a **false** determinate verdict. `fairness_null0`: true difference 0, any FAIL is false (nominal 0.05). `fairness_margin`: true difference = margin, any PASS is false (nominal 0.05). `robustness_tol`: true flip rate = tolerance, PASS and FAIL both false (nominal 0.05 per side, 0.10 total).

| truth | n | static | adaptive (uncorrected) | adaptive + CS | adaptive + OBF spending | adaptive + Pocock spending |
|---|---|---|---|---|---|---|
| fairness_null0 | 948 | 0.045 | 0.197 | 0.001 | 0.015 | 0.036 |
| fairness_margin | 948 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| robustness_tol | 725 | 0.101 | 0.293 | 0.001 | 0.036 | 0.053 |

Share of the same audits reaching **any** determinate verdict (how often each rule commits at all):

| truth | static | adaptive | CS | OBF | Pocock |
|---|---|---|---|---|---|
| fairness_null0 | 0.057 | 0.209 | 0.001 | 0.015 | 0.036 |
| fairness_margin | 0.303 | 0.448 | 0.003 | 0.159 | 0.138 |
| robustness_tol | 0.101 | 0.293 | 0.001 | 0.036 | 0.053 |

## 2. Replay over the logged responses

Mean over seeds, with the 2.5–97.5% range over seeds in brackets. Fidelity is against the static full-budget verdict. S4: corrected fidelity ≥ 0.90 × static AND spend ≤ 0.80 × static, judged on the seed-range bounds.

| budget | policy | coverage | fidelity | contradictions (mean / max) | spend | fidelity ÷ static | spend ÷ static | S4 |
|---|---|---|---|---|---|---|---|---|
| 5% | adaptive | 0.22 [0.06, 0.44] | 0.75 [0.00, 1.00] | 0.90 / 3 | 2,592 | 0.92 [0.00, 1.71] | 0.90 [0.88, 0.90] | not met |
| 5% | adaptive_cs | 0.01 [0.00, 0.06] | 1.00 [1.00, 1.00] | 0.00 / 0 | 2,559 | 1.28 [1.00, 2.00] | 0.88 [0.88, 0.90] | not met |
| 5% | adaptive_obf | 0.04 [0.00, 0.12] | 0.97 [0.50, 1.00] | 0.05 / 1 | 2,562 | 1.25 [0.50, 2.00] | 0.88 [0.88, 0.89] | not met |
| 5% | adaptive_pocock | 0.03 [0.00, 0.12] | 1.00 [1.00, 1.00] | 0.00 / 0 | 2,563 | 1.28 [1.00, 2.00] | 0.89 [0.88, 0.90] | not met |
| 5% | static | 0.15 [0.00, 0.31] | 0.85 [0.33, 1.00] | 0.40 / 2 | 2,896 | — | — | — |
| 10% | adaptive | 0.41 [0.25, 0.56] | 0.84 [0.50, 1.00] | 1.12 / 4 | 5,262 | 0.92 [0.57, 1.11] | 0.91 [0.90, 0.91] | not met |
| 10% | adaptive_cs | 0.02 [0.00, 0.06] | 0.97 [0.00, 1.00] | 0.03 / 1 | 5,223 | 1.08 [0.00, 1.33] | 0.90 [0.90, 0.91] | not met |
| 10% | adaptive_obf | 0.14 [0.00, 0.25] | 0.97 [0.67, 1.00] | 0.10 / 1 | 5,232 | 1.07 [0.83, 1.33] | 0.90 [0.90, 0.91] | not met |
| 10% | adaptive_pocock | 0.11 [0.00, 0.25] | 0.96 [0.00, 1.00] | 0.10 / 1 | 5,241 | 1.06 [0.00, 1.33] | 0.90 [0.90, 0.91] | not met |
| 10% | static | 0.30 [0.19, 0.38] | 0.92 [0.67, 1.00] | 0.42 / 2 | 5,792 | — | — | — |
| 20% | adaptive | 0.57 [0.44, 0.75] | 0.80 [0.60, 1.00] | 1.90 / 4 | 10,609 | 0.92 [0.60, 1.07] | 0.91 [0.91, 0.91] | not met |
| 20% | adaptive_cs | 0.07 [0.00, 0.12] | 0.99 [0.50, 1.00] | 0.03 / 1 | 10,562 | 1.14 [0.60, 1.50] | 0.91 [0.91, 0.91] | not met |
| 20% | adaptive_obf | 0.35 [0.25, 0.44] | 0.96 [0.80, 1.00] | 0.23 / 1 | 10,575 | 1.11 [0.83, 1.50] | 0.91 [0.91, 0.91] | not met |
| 20% | adaptive_pocock | 0.30 [0.19, 0.38] | 0.96 [0.75, 1.00] | 0.23 / 1 | 10,574 | 1.10 [0.91, 1.50] | 0.91 [0.91, 0.91] | not met |
| 20% | static | 0.42 [0.25, 0.56] | 0.88 [0.57, 1.00] | 0.85 / 3 | 11,628 | — | — | — |
| 30% | adaptive | 0.59 [0.44, 0.69] | 0.79 [0.64, 0.89] | 2.10 / 4 | 15,922 | 0.92 [0.67, 1.14] | 0.91 [0.90, 0.91] | not met |
| 30% | adaptive_cs | 0.14 [0.06, 0.25] | 0.98 [0.67, 1.00] | 0.05 / 1 | 15,901 | 1.15 [0.86, 1.50] | 0.91 [0.91, 0.91] | not met |
| 30% | adaptive_obf | 0.42 [0.31, 0.50] | 0.97 [0.83, 1.00] | 0.25 / 1 | 15,907 | 1.13 [0.95, 1.43] | 0.91 [0.91, 0.91] | not met |
| 30% | adaptive_pocock | 0.41 [0.31, 0.50] | 0.96 [0.78, 1.00] | 0.33 / 2 | 15,907 | 1.12 [0.97, 1.50] | 0.91 [0.91, 0.91] | not met |
| 30% | static | 0.48 [0.31, 0.62] | 0.86 [0.67, 1.00] | 1.10 / 3 | 17,444 | — | — | — |
| 50% | adaptive | 0.62 [0.50, 0.75] | 0.80 [0.67, 0.89] | 2.05 / 4 | 26,060 | 0.88 [0.67, 1.07] | 0.90 [0.81, 0.91] | not met |
| 50% | adaptive_cs | 0.25 [0.19, 0.31] | 0.99 [0.80, 1.00] | 0.05 / 1 | 26,540 | 1.08 [1.00, 1.28] | 0.91 [0.90, 0.91] | not met |
| 50% | adaptive_obf | 0.49 [0.38, 0.56] | 0.94 [0.86, 1.00] | 0.50 / 1 | 26,438 | 1.02 [0.86, 1.17] | 0.91 [0.90, 0.91] | not met |
| 50% | adaptive_pocock | 0.48 [0.38, 0.56] | 0.95 [0.88, 1.00] | 0.42 / 1 | 26,411 | 1.03 [0.88, 1.17] | 0.91 [0.90, 0.91] | not met |
| 50% | static | 0.48 [0.38, 0.56] | 0.92 [0.62, 1.00] | 0.62 / 3 | 29,096 | — | — | — |
| 75% | adaptive | 0.62 [0.50, 0.75] | 0.81 [0.67, 1.00] | 1.98 / 4 | 30,699 | 0.88 [0.67, 1.03] | 0.70 [0.54, 0.83] | undetermined |
| 75% | adaptive_cs | 0.32 [0.31, 0.38] | 0.99 [0.80, 1.00] | 0.05 / 1 | 39,609 | 1.08 [0.91, 1.25] | 0.91 [0.90, 0.91] | not met |
| 75% | adaptive_obf | 0.51 [0.44, 0.56] | 0.97 [0.89, 1.00] | 0.28 / 1 | 39,675 | 1.06 [0.89, 1.14] | 0.91 [0.87, 0.91] | not met |
| 75% | adaptive_pocock | 0.53 [0.44, 0.56] | 0.95 [0.89, 1.00] | 0.47 / 1 | 37,489 | 1.03 [0.89, 1.14] | 0.86 [0.75, 0.91] | undetermined |
| 75% | static | 0.51 [0.44, 0.56] | 0.92 [0.78, 1.00] | 0.68 / 2 | 43,644 | — | — | — |
| 100% | adaptive | 0.60 [0.50, 0.69] | 0.84 [0.67, 1.00] | 1.65 / 4 | 32,248 | 0.84 [0.67, 1.00] | 0.55 [0.45, 0.66] | undetermined |
| 100% | adaptive_cs | 0.32 [0.31, 0.38] | 1.00 [0.83, 1.00] | 0.03 / 1 | 46,388 | 1.00 [0.83, 1.00] | 0.80 [0.73, 0.82] | undetermined |
| 100% | adaptive_obf | 0.51 [0.50, 0.56] | 0.99 [0.89, 1.00] | 0.12 / 1 | 45,186 | 0.99 [0.89, 1.00] | 0.78 [0.72, 0.81] | undetermined |
| 100% | adaptive_pocock | 0.53 [0.50, 0.56] | 0.95 [0.80, 1.00] | 0.47 / 2 | 38,467 | 0.95 [0.80, 1.00] | 0.66 [0.57, 0.75] | undetermined |
| 100% | static | 0.50 [0.50, 0.50] | 1.00 [1.00, 1.00] | 0.00 / 0 | 58,220 | — | — | — |

### S4 under both readings, with coverage relative to static

`range` = per-seed 2.5–97.5% range (how one audit run could come out; the reading the code applies). `mean CI` = bootstrap CI of the mean over seeds (expected behaviour). Coverage ÷ static is the mean ratio with its CI — S4 does not constrain it, which is why it is shown.

**Primary (pre-registered, OPEN 5):** mean CI with a coverage condition (coverage ÷ static ≥ 0.90), primary policy `adaptive_obf`.

| budget | policy | **S4 primary** | S4 (range) | S4 (mean CI, no coverage) | fidelity ÷ static, mean CI | spend ÷ static, mean CI | coverage ÷ static |
|---|---|---|---|---|---|---|---|
| 5% | adaptive | **not met** | not met | not met | 0.92 [0.80, 1.03] | 0.90 [0.89, 0.90] | 1.58 [1.36, 1.83] |
| 5% | adaptive_cs | **not met** | not met | not met | 1.28 [1.15, 1.42] | 0.88 [0.88, 0.89] | 0.09 [0.03, 0.16] |
| 5% | adaptive_obf ◀ primary policy | **not met** | not met | not met | 1.25 [1.11, 1.40] | 0.88 [0.88, 0.89] | 0.27 [0.19, 0.36] |
| 5% | adaptive_pocock | **not met** | not met | not met | 1.28 [1.15, 1.42] | 0.89 [0.88, 0.89] | 0.18 [0.11, 0.26] |
| 10% | adaptive | **not met** | not met | not met | 0.92 [0.87, 0.96] | 0.91 [0.91, 0.91] | 1.41 [1.32, 1.51] |
| 10% | adaptive_cs | **not met** | not met | not met | 1.08 [1.01, 1.14] | 0.90 [0.90, 0.90] | 0.06 [0.03, 0.09] |
| 10% | adaptive_obf ◀ primary policy | **not met** | not met | not met | 1.07 [1.03, 1.12] | 0.90 [0.90, 0.90] | 0.50 [0.43, 0.56] |
| 10% | adaptive_pocock | **not met** | not met | not met | 1.06 [0.99, 1.12] | 0.90 [0.90, 0.91] | 0.38 [0.31, 0.46] |
| 20% | adaptive | **not met** | not met | not met | 0.92 [0.88, 0.95] | 0.91 [0.91, 0.91] | 1.40 [1.32, 1.49] |
| 20% | adaptive_cs | **not met** | not met | not met | 1.14 [1.08, 1.21] | 0.91 [0.91, 0.91] | 0.18 [0.15, 0.21] |
| 20% | adaptive_obf ◀ primary policy | **not met** | not met | not met | 1.11 [1.06, 1.17] | 0.91 [0.91, 0.91] | 0.85 [0.80, 0.90] |
| 20% | adaptive_pocock | **not met** | not met | not met | 1.10 [1.06, 1.16] | 0.91 [0.91, 0.91] | 0.73 [0.68, 0.79] |
| 30% | adaptive | **not met** | not met | not met | 0.92 [0.88, 0.95] | 0.91 [0.91, 0.91] | 1.26 [1.20, 1.33] |
| 30% | adaptive_cs | **not met** | not met | not met | 1.15 [1.11, 1.20] | 0.91 [0.91, 0.91] | 0.29 [0.26, 0.33] |
| 30% | adaptive_obf ◀ primary policy | **not met** | not met | not met | 1.13 [1.09, 1.18] | 0.91 [0.91, 0.91] | 0.89 [0.85, 0.94] |
| 30% | adaptive_pocock | **not met** | not met | not met | 1.12 [1.08, 1.17] | 0.91 [0.91, 0.91] | 0.87 [0.83, 0.92] |
| 50% | adaptive | **not met** | not met | not met | 0.88 [0.84, 0.91] | 0.90 [0.89, 0.90] | 1.32 [1.26, 1.39] |
| 50% | adaptive_cs | **not met** | not met | not met | 1.08 [1.05, 1.11] | 0.91 [0.91, 0.91] | 0.54 [0.51, 0.57] |
| 50% | adaptive_obf ◀ primary policy | **not met** | not met | not met | 1.02 [0.99, 1.06] | 0.91 [0.91, 0.91] | 1.03 [0.99, 1.07] |
| 50% | adaptive_pocock | **not met** | not met | not met | 1.03 [1.00, 1.07] | 0.91 [0.91, 0.91] | 1.00 [0.97, 1.04] |
| 75% | adaptive | **undetermined** | undetermined | undetermined | 0.88 [0.85, 0.92] | 0.70 [0.68, 0.73] | 1.23 [1.18, 1.28] |
| 75% | adaptive_cs | **not met** | not met | not met | 1.08 [1.06, 1.11] | 0.91 [0.91, 0.91] | 0.63 [0.61, 0.66] |
| 75% | adaptive_obf ◀ primary policy | **not met** | not met | not met | 1.06 [1.03, 1.08] | 0.91 [0.91, 0.91] | 1.02 [0.98, 1.05] |
| 75% | adaptive_pocock | **not met** | undetermined | not met | 1.03 [1.01, 1.06] | 0.86 [0.85, 0.87] | 1.05 [1.01, 1.08] |
| 100% | adaptive | **not met** | undetermined | not met | 0.84 [0.81, 0.87] | 0.55 [0.54, 0.57] | 1.20 [1.16, 1.24] |
| 100% | adaptive_cs | **not met** | undetermined | undetermined | 1.00 [0.99, 1.00] | 0.80 [0.79, 0.80] | 0.63 [0.62, 0.64] |
| 100% | adaptive_obf ◀ primary policy | **met** | undetermined | met | 0.99 [0.97, 1.00] | 0.78 [0.77, 0.78] | 1.02 [1.00, 1.03] |
| 100% | adaptive_pocock | **met** | undetermined | met | 0.95 [0.93, 0.97] | 0.66 [0.65, 0.68] | 1.06 [1.03, 1.08] |

## 3. Full-budget reference verdicts

| requirement | verdict |
|---|---|
| Qwen2.5-7B-Instruct|fairness|marginal | FAIL |
| Qwen2.5-7B-Instruct|fairness|strong | FAIL |
| Qwen2.5-7B-Instruct|fairness|weak | FAIL |
| Qwen2.5-7B-Instruct|robustness|- | UNDETERMINED |
| Qwen2.5-32B-Instruct-AWQ|fairness|marginal | UNDETERMINED |
| Qwen2.5-32B-Instruct-AWQ|fairness|strong | UNDETERMINED |
| Qwen2.5-32B-Instruct-AWQ|fairness|weak | UNDETERMINED |
| Qwen2.5-32B-Instruct-AWQ|robustness|- | FAIL |
| Llama-3.1-8B-Instruct|fairness|marginal | FAIL |
| Llama-3.1-8B-Instruct|fairness|strong | UNDETERMINED |
| Llama-3.1-8B-Instruct|fairness|weak | FAIL |
| Llama-3.1-8B-Instruct|robustness|- | UNDETERMINED |
| Meta-Llama-3.1-70B-Instruct-AWQ-INT4|fairness|marginal | UNDETERMINED |
| Meta-Llama-3.1-70B-Instruct-AWQ-INT4|fairness|strong | FAIL |
| Meta-Llama-3.1-70B-Instruct-AWQ-INT4|fairness|weak | UNDETERMINED |
| Meta-Llama-3.1-70B-Instruct-AWQ-INT4|robustness|- | PASS |
