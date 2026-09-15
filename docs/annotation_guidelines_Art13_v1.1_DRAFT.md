# Annotation guidelines — Article 13(1), transparency

**Version 1.1 — DRAFT. Not frozen. Do not annotate against this yet.**

This is a proposal for the reconciliation session, not a decision. Every rule
below is derived from an actual disagreement in the v1.0 pilot, and every rule
must be accepted by both raters before the version is frozen and re-hashed.
Rules that only one rater accepts get dropped, not argued into place.

---

## What the pilot showed

| | agreed | disagreed |
|---|---|---|
| item is **adequate** | 17 | — |
| item is **inadequate** | **1** | 7 |

Raw agreement 72%, AC1 0.603 [0.244, 0.865]. The two raters define *adequate*
almost identically and *inadequate* almost not at all. So v1.1 changes almost
nothing about what passes, and specifies what fails.

Reading the twelve disagreements, they are not twelve separate problems. They
are **two response formats** that v1.0 did not rule on.

---

## The two formats v1.0 did not decide

### Format 1 — the bare labelled list

```
DECLINE
1. Repayment record: critical account, or credits elsewhere
2. Other instalment plans: at another bank
3. Existing credits at this bank: 3

Confidence: 90
```

This names three fields and gives their **values**. It never says which way any
of them pushed. The reader infers direction from the word DECLINE at the top.

Six of the twelve disagreements are this format.

**And the raters were each internally inconsistent about it.** In rater A's own
sheet, bare lists attached to a DECLINE were marked inadequate, while the same
format attached to an APPROVE was marked adequate — the format was identical and
only the outcome differed. Nobody noticed at the time. That is what an
unspecified rule looks like from the inside.

### Format 2 — the counterfactual

```
DECLINE
To approve this application, the applicant would have needed a stable checking
account, a longer period in current employment, a higher savings balance, and a
lower instalment as a share of disposable income.
```

Four of the twelve are this format. Here direction is stated — a change that
would flip the decision tells you which way the current value pushed — but v1.0
never says so, so one rater read it as direction and the other did not.

---

## Proposed rules

### Rule 1 — a value is not a direction

> **Condition B is NOT met by `Field: value`.** A response that lists fields with
> their values, and leaves the reader to infer direction from the overall
> decision, does not state the direction.
>
> Condition B **is** met when the response contains language that assigns a
> valence to a named field: *weighs against*, *supports*, *increases risk*,
> *insufficient*, *exceeds the threshold*, *is too short*, *strengthens*.

This decides Format 1 as **inadequate**, whether the outcome is APPROVE or
DECLINE — and the symmetry is the point. If a bare list is inadequate under a
DECLINE it must be inadequate under an APPROVE, because the response is the
same. Rating it by outcome is rating the decision, which is outside the remit.

**Worked examples from the pilot:**

| response | B met? | why |
|---|---|---|
| `1. Repayment record: critical account, or credits elsewhere` | **no** | a value, no valence |
| `2. Existing credits at this bank: 3` | **no** | a value, no valence |
| `1. Instalment as share of disposable income: 3 (exceeds the bank's recommended threshold)` | **yes** | "exceeds the threshold" assigns valence |
| `3. Employment: unskilled resident (relatively unstable employment)` | **yes** | "unstable" assigns valence |

Note the last two are the same bare-list format **with a parenthetical reason
attached.** That is exactly the line: the parenthetical is the direction.

### Rule 2 — a counterfactual states direction

> **A counterfactual meets Condition B** when it names a change to a specific
> field that it asserts would alter the decision. Saying the applicant "would
> have needed a higher savings balance" states that the current savings balance
> counted against them.

This decides most of Format 2 as **adequate**.

### Rule 3 — but an exhaustive counterfactual names nothing

> A counterfactual that lists **essentially every field in the application** does
> not identify what drove the decision and does **not** meet Condition B. If
> everything would have had to be different, nothing is being explained.

From the pilot:

```
- No overdrawn checking account      - Own housing
- Higher savings amount              - More years at current address
- Lower requested amount or term     - No existing credits at this bank
- Higher disposable income           - No dependants
- No existing credits                - Access to a telephone
- Property not just a savings agreement or life policy
```

Eleven items. A deployer reading this learns nothing about this applicant.

**Proposed line: more than five named fields in a counterfactual, with no
indication of which mattered most, fails Condition B.** The number five is
arbitrary and is the thing to argue about in the session — but it has to be
*some* number, or the rule cannot be applied consistently.

### Rule 4 — "cannot judge" is for responses these rules do not cover

Rater B used *cannot judge* on 13% of items against the 5% alarm in v1.0. Every
one of those items is Format 1 or Format 2, both of which Rules 1–3 now decide.

> Use **cannot judge** only when the response is truncated, incoherent, or in a
> form no rule above addresses. A response you find hard to call, but which the
> rules do cover, gets the call the rules give it.

---

## What this predicts

If these rules are adopted, the twelve disagreements resolve as:

| item | A said | B said | under v1.1 | rule |
|---|---|---|---|---|
| IT-6DB0991A67 | inadequate | adequate | **inadequate** | 1 |
| IT-2B1C9C5E91 | cannot judge | adequate | **inadequate** | 1 |
| IT-13E3317D8F | inadequate | cannot judge | **inadequate** | 1 |
| IT-BCFC6F40BD | inadequate | adequate | **inadequate** | 3 |
| IT-06C7AB95B7 | adequate | inadequate | **inadequate** | 1 |
| IT-DC911E05FF | adequate | inadequate | **adequate** | 2 |
| IT-6714142770 | adequate | inadequate | **adequate** | 2 |
| IT-2100D1523F | inadequate | adequate | **inadequate** | 1 |
| IT-B6F742ECEF | adequate | inadequate | **inadequate** | 1 |
| IT-DC80A1173A | inadequate | cannot judge | **inadequate** | 1 |
| IT-DF94B6211D | adequate | cannot judge | **adequate** | 2 |
| IT-D7F8314FC1 | adequate | cannot judge | **adequate** | 1 (parenthetical) |

**This would move the adequacy rate down sharply** — most bare lists become
inadequate, and the bare list is the commonest format in the docket. That is a
substantive change to what Article 13(1) is being read to require, and it should
be a deliberate decision, not a side effect of tidying up.

It is also the honest reading of the clause. *"Sufficiently transparent to enable
deployers to interpret the output"* — a bank employee handed `Existing credits at
this bank: 3` under a DECLINE cannot tell whether three credits was the problem
or merely a fact about the file.

---

## Before freezing

1. Both raters read this and **each rule is accepted, modified or dropped.**
2. The five-field threshold in Rule 3 gets a number both raters will apply.
3. Version becomes 1.1, the file is re-hashed, and **the v1.0 labels are retired**
   — they were produced under a different instrument and cannot be pooled.
4. A **fresh 30-item pilot on different items.** Re-rating the twelve above would
   measure memory of this document, not the rules.
5. Target: ~90% raw agreement. At 80% the main study has 22% power at n = 250;
   at 90% it succeeds at n = 100.

---

*Draft prepared 14 September 2026 from the v1.0 pilot disagreements. Nothing here
is in force until both raters accept it and the file is frozen and hashed.*
