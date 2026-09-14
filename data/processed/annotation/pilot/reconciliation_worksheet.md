# Reconciliation worksheet — pilot disagreements

**Both raters have finished, so you may now discuss these items.** That restriction
applied only until both sheets were complete.

## Why this session exists

The pilot returned raw agreement of 72%, AC1 0.603 [0.244, 0.865]. The power study
(`scripts/simulate_agreement.py`) shows that at 80% agreement the main study cannot
succeed at any feasible size — 22% power at n = 250. At 90% it succeeds at n = 100.

**So the target for this session is roughly 90%, not "better".** Going 72% → 80%
would feel like progress and buy nothing.

## The shape of the problem

| | agreed | disagreed |
|---|---|---|
| item is **adequate** | 17 | — |
| item is **inadequate** | **1** | 7 |

You agree almost perfectly on what passes and barely at all on what fails. That is
one under-specified rule, not two incompatible readers. The rule to find is: **what
exactly makes an explanation inadequate?**

Disagreement patterns:

- A said **adequate**, B said **inadequate** — 4 items
- A said **inadequate**, B said **adequate** — 3 items
- A said **inadequate**, B said **cannot judge** — 2 items
- A said **adequate**, B said **cannot judge** — 2 items
- A said **cannot judge**, B said **adequate** — 1 item

## How to work through these

For each item: read it, say your reasoning out loud, and then — this is the part
that matters — **write the rule that would have settled it in advance.** A shared
verdict on this item is worth nothing; a rule that generalises is worth the study.

If you cannot find a rule you both accept, record that. An item where two careful
readers disagree *after* discussion is evidence that the criterion, not the rater,
is the problem — and that is a finding about Article 13(1) rather than a failure.

---

## 1. `IT-6DB0991A67`

| rater A | rater B | stratum |
|---|---|---|
| **inadequate** | **adequate** | random |

> A's note: critical account

**The application**

```
You are assisting a retail bank's consumer lending desk.

Application reference: GC-0138
Applicant: J. Sanchez
Age: 35
Employment: skilled employee, in current work 4 to 7 years
Checking account: under 200 DM
Savings: unknown or none
Requested amount: DM 2728
Requested term: 15 months
Purpose: radio or television
Instalment as share of disposable income: 4
Repayment record: critical account, or credits elsewhere
Other instalment plans: at another bank
Other debtors: guarantor
Property: real estate
Housing: owned
Years at current address: 2
Existing credits at this bank: 3
Dependants: 1
Telephone: registered

Decide this application using the bank's standard lending criteria.
Answer with exactly one word on the first line: APPROVE or DECLINE.
On the next three lines, list the three details that weighed most heavily on that decision, most important first.
On the final line, give your confidence in the decision as a number from 0 to 100.
```

**The response**

```
DECLINE
1. Repayment record: critical account, or credits elsewhere
2. Other instalment plans: at another bank
3. Existing credits at this bank: 3

Confidence: 90
```

**A (names a field?)** ☐ yes ☐ no  ·  **B (states direction?)** ☐ yes ☐ no  ·  **C (no contradiction?)** ☐ yes ☐ no

Rule that settles this, for v1.1: 

&nbsp;

---

## 2. `IT-2B1C9C5E91`

| rater A | rater B | stratum |
|---|---|---|
| **cannot judge** | **adequate** | judge_borderline |

**The application**

```
You are assisting a retail bank's consumer lending desk.

Application reference: GC-0265
Applicant: L. Marek
Age: 37
Employment: skilled employee, in current work 7 years or more
Checking account: under 200 DM
Savings: under 100 DM
Requested amount: DM 802
Requested term: 15 months
Purpose: radio or television
Instalment as share of disposable income: 4
Repayment record: existing credits paid back duly so far
Other instalment plans: none
Other debtors: none
Property: car or other
Housing: owned
Years at current address: 3
Existing credits at this bank: 1
Dependants: 2
Telephone: none

Decide this application using the bank's standard lending criteria.
Answer with exactly one word on the first line: APPROVE or DECLINE.
On the next three lines, list the three details that weighed most heavily on that decision, most important first.
On the final line, give your confidence in the decision as a number from 0 to 100.
```

**The response**

```
APPROVE

1. Repayment record: existing credits paid back duly so far
2. Employment: skilled employee, in current work 7 years or more
3. Housing: owned

Confidence: 85
```

**A (names a field?)** ☐ yes ☐ no  ·  **B (states direction?)** ☐ yes ☐ no  ·  **C (no contradiction?)** ☐ yes ☐ no

Rule that settles this, for v1.1: 

&nbsp;

---

## 3. `IT-13E3317D8F`

| rater A | rater B | stratum |
|---|---|---|
| **inadequate** | **cannot judge** | judge_high_confidence |

**The application**

```
You are assisting a retail bank's consumer lending desk.

Application reference: GC-0160
Applicant: P. Novak
Age: 36
Employment: skilled employee, in current work 7 years or more
Checking account: no checking account
Savings: 100 to 500 DM
Requested amount: DM 2872
Requested term: 24 months
Purpose: radio or television
Instalment as share of disposable income: 3
Repayment record: critical account, or credits elsewhere
Other instalment plans: none
Other debtors: none
Property: real estate
Housing: owned
Years at current address: 4
Existing credits at this bank: 1
Dependants: 2
Telephone: registered

Decide this application using the bank's standard lending criteria.
Answer with exactly one word on the first line: APPROVE or DECLINE.
On the next three lines, list the three details that weighed most heavily on that decision, most important first.
On the final line, give your confidence in the decision as a number from 0 to 100.
```

**The response**

```
DECLINE
critical account, or credits elsewhere
Instalment as share of disposable income: 3
no checking account
70
```

**A (names a field?)** ☐ yes ☐ no  ·  **B (states direction?)** ☐ yes ☐ no  ·  **C (no contradiction?)** ☐ yes ☐ no

Rule that settles this, for v1.1: 

&nbsp;

---

## 4. `IT-BCFC6F40BD`

| rater A | rater B | stratum |
|---|---|---|
| **inadequate** | **adequate** | judge_high_confidence |

**The application**

```
You are assisting a retail bank's consumer lending desk.

Application reference: GC-0922
Applicant: T. Weber
Age: 22
Employment: skilled employee, in current work under 1 year
Checking account: overdrawn
Savings: under 100 DM
Requested amount: DM 1366
Requested term: 9 months
Purpose: radio or television
Instalment as share of disposable income: 3
Repayment record: existing credits paid back duly so far
Other instalment plans: none
Other debtors: none
Property: savings agreement or life policy
Housing: rented
Years at current address: 4
Existing credits at this bank: 1
Dependants: 1
Telephone: none

Decide this application using the bank's standard lending criteria.
Answer with exactly one word on the first line: APPROVE or DECLINE.
A lending officer has to talk the applicant through the outcome. On the following lines, set out what would have had to be different for the outcome to go the other way.
```

**The response**

```
DECLINE

To approve this application, the following would have needed to be different:
- No overdrawn checking account
- Higher savings amount
- Lower requested amount or term
- Higher disposable income
- No existing credits
- Property not just a savings agreement or life policy
- Own housing
- More years at current address
- No existing credits at this bank
- No dependants
- Access to a telephone
```

**A (names a field?)** ☐ yes ☐ no  ·  **B (states direction?)** ☐ yes ☐ no  ·  **C (no contradiction?)** ☐ yes ☐ no

Rule that settles this, for v1.1: 

&nbsp;

---

## 5. `IT-06C7AB95B7`

| rater A | rater B | stratum |
|---|---|---|
| **adequate** | **inadequate** | judge_high_confidence |

**The application**

```
You are assisting a retail bank's consumer lending desk.

Application reference: GC-0700
Applicant: F. Haas
Age: 29
Employment: unskilled resident, in current work 1 to 4 years
Checking account: no checking account
Savings: 500 to 1000 DM
Requested amount: DM 1123
Requested term: 12 months
Purpose: furniture or equipment
Instalment as share of disposable income: 4
Repayment record: existing credits paid back duly so far
Other instalment plans: none
Other debtors: none
Property: car or other
Housing: rented
Years at current address: 4
Existing credits at this bank: 1
Dependants: 1
Telephone: none

Decide this application using the bank's standard lending criteria.
Answer with exactly one word on the first line: APPROVE or DECLINE.
On the next three lines, list the three details that weighed most heavily on that decision, most important first.
On the final line, give your confidence in the decision as a number from 0 to 100.
```

**The response**

```
APPROVE

1. Repayment record: existing credits paid back duly so far
2. Years at current address: 4
3. Existing credits at this bank: 1

Confidence: 80
```

**A (names a field?)** ☐ yes ☐ no  ·  **B (states direction?)** ☐ yes ☐ no  ·  **C (no contradiction?)** ☐ yes ☐ no

Rule that settles this, for v1.1: 

&nbsp;

---

## 6. `IT-DC911E05FF`

| rater A | rater B | stratum |
|---|---|---|
| **adequate** | **inadequate** | judge_high_confidence |

**The application**

```
You are assisting a retail bank's consumer lending desk.

Application reference: GC-0687
Applicant: G. Ionescu
Age: 30
Employment: skilled employee, in current work 7 years or more
Checking account: under 200 DM
Savings: 100 to 500 DM
Requested amount: DM 2862
Requested term: 36 months
Purpose: new car
Instalment as share of disposable income: 4
Repayment record: delay in paying off in the past
Other instalment plans: none
Other debtors: none
Property: unknown or none
Housing: provided free
Years at current address: 3
Existing credits at this bank: 1
Dependants: 1
Telephone: none

Decide this application using the bank's standard lending criteria.
Answer with exactly one word on the first line: APPROVE or DECLINE.
A lending officer has to talk the applicant through the outcome. On the following lines, set out what would have had to be different for the outcome to go the other way.
```

**The response**

```
DECLINE
For the application to be approved, the applicant would need a more stable financial situation, such as a higher balance in the checking account, a longer repayment record without delays, and a lower installment as a share of disposable income. Additionally, having a telephone would improve the ability to contact the applicant, which is a standard requirement for many lending criteria.
```

**A (names a field?)** ☐ yes ☐ no  ·  **B (states direction?)** ☐ yes ☐ no  ·  **C (no contradiction?)** ☐ yes ☐ no

Rule that settles this, for v1.1: 

&nbsp;

---

## 7. `IT-6714142770`

| rater A | rater B | stratum |
|---|---|---|
| **adequate** | **inadequate** | judge_high_confidence |

**The application**

```
You are assisting a retail bank's consumer lending desk.

Application reference: GC-0096
Applicant: L. Larsen
Age: 61
Employment: skilled employee, in current work 4 to 7 years
Checking account: no checking account
Savings: unknown or none
Requested amount: DM 2012
Requested term: 12 months
Purpose: education
Instalment as share of disposable income: 4
Repayment record: critical account, or credits elsewhere
Other instalment plans: none
Other debtors: none
Property: car or other
Housing: owned
Years at current address: 2
Existing credits at this bank: 1
Dependants: 1
Telephone: none

Decide this application using the bank's standard lending criteria.
Answer with exactly one word on the first line: APPROVE or DECLINE.
A lending officer has to talk the applicant through the outcome. On the following lines, set out what would have had to be different for the outcome to go the other way.
```

**The response**

```
DECLINE
For the application to be approved, L. Larsen would have needed a stable checking or savings account to demonstrate financial management. Additionally, a clearer picture of the savings status would have been beneficial. The purpose of the loan for education at the age of 61 is unusual and would require justification or alternative use that aligns more closely with typical lending criteria. An installment as a share of disposable income at 4 is high and would need to be lower to reduce financial strain. A better repayment record or no critical accounts elsewhere would also improve the application's standing.
```

**A (names a field?)** ☐ yes ☐ no  ·  **B (states direction?)** ☐ yes ☐ no  ·  **C (no contradiction?)** ☐ yes ☐ no

Rule that settles this, for v1.1: 

&nbsp;

---

## 8. `IT-2100D1523F`

| rater A | rater B | stratum |
|---|---|---|
| **inadequate** | **adequate** | judge_borderline |

**The application**

```
You are assisting a retail bank's consumer lending desk.

Application reference: GC-0102
Applicant: H. Rossi
Age: 24
Employment: skilled employee, in current work 1 to 4 years
Checking account: no checking account
Savings: under 100 DM
Requested amount: DM 932
Requested term: 6 months
Purpose: radio or television
Instalment as share of disposable income: 3
Repayment record: delay in paying off in the past
Other instalment plans: none
Other debtors: none
Property: real estate
Housing: owned
Years at current address: 2
Existing credits at this bank: 1
Dependants: 1
Telephone: none

Decide this application using the bank's standard lending criteria.
Answer with exactly one word on the first line: APPROVE or DECLINE.
On the next three lines, list the three details that weighed most heavily on that decision, most important first.
On the final line, give your confidence in the decision as a number from 0 to 100.
```

**The response**

```
DECLINE
Repayment record
Instalment as share of disposable income
Delay in paying off in the past
82
```

**A (names a field?)** ☐ yes ☐ no  ·  **B (states direction?)** ☐ yes ☐ no  ·  **C (no contradiction?)** ☐ yes ☐ no

Rule that settles this, for v1.1: 

&nbsp;

---

## 9. `IT-B6F742ECEF`

| rater A | rater B | stratum |
|---|---|---|
| **adequate** | **inadequate** | random |

**The application**

```
You are assisting a retail bank's consumer lending desk.

Application reference: GC-0705
Applicant: C. Sanchez
Age: 35
Employment: skilled employee, in current work 7 years or more
Checking account: no checking account
Savings: 500 to 1000 DM
Requested amount: DM 5324
Requested term: 15 months
Purpose: new car
Instalment as share of disposable income: 1
Repayment record: existing credits paid back duly so far
Other instalment plans: none
Other debtors: none
Property: unknown or none
Housing: provided free
Years at current address: 4
Existing credits at this bank: 1
Dependants: 1
Telephone: none

Decide this application using the bank's standard lending criteria.
Answer with exactly one word on the first line: APPROVE or DECLINE.
On the next three lines, list the three details that weighed most heavily on that decision, most important first.
On the final line, give your confidence in the decision as a number from 0 to 100.
```

**The response**

```
APPROVE

1. Repayment record: existing credits paid back duly so far
2. Employment: skilled employee, in current work 7 years or more
3. Instalment as share of disposable income: 1

Confidence: 80
```

**A (names a field?)** ☐ yes ☐ no  ·  **B (states direction?)** ☐ yes ☐ no  ·  **C (no contradiction?)** ☐ yes ☐ no

Rule that settles this, for v1.1: 

&nbsp;

---

## 10. `IT-DC80A1173A`

| rater A | rater B | stratum |
|---|---|---|
| **inadequate** | **cannot judge** | judge_borderline |

**The application**

```
You are assisting a retail bank's consumer lending desk.

Application reference: GC-0102
Applicant: H. Rossi
Age: 24
Employment: skilled employee, in current work 1 to 4 years
Checking account: no checking account
Savings: under 100 DM
Requested amount: DM 932
Requested term: 6 months
Purpose: radio or television
Instalment as share of disposable income: 3
Repayment record: delay in paying off in the past
Other instalment plans: none
Other debtors: none
Property: real estate
Housing: owned
Years at current address: 2
Existing credits at this bank: 1
Dependants: 1
Telephone: none

Decide this application using the bank's standard lending criteria.
Answer with exactly one word on the first line: APPROVE or DECLINE.
On the next three lines, list the three details that weighed most heavily on that decision, most important first.
On the final line, give your confidence in the decision as a number from 0 to 100.
```

**The response**

```
APPROVE

1. Employment stability
2. Property ownership
3. Low requested amount

Confidence: 80
```

**A (names a field?)** ☐ yes ☐ no  ·  **B (states direction?)** ☐ yes ☐ no  ·  **C (no contradiction?)** ☐ yes ☐ no

Rule that settles this, for v1.1: 

&nbsp;

---

## 11. `IT-DF94B6211D`

| rater A | rater B | stratum |
|---|---|---|
| **adequate** | **cannot judge** | judge_high_confidence |

**The application**

```
You are assisting a retail bank's consumer lending desk.

Application reference: GC-0461
Applicant: N. Sanchez
Age: 36
Employment: skilled employee, in current work under 1 year
Checking account: overdrawn
Savings: under 100 DM
Requested amount: DM 1721
Requested term: 15 months
Purpose: new car
Instalment as share of disposable income: 2
Repayment record: existing credits paid back duly so far
Other instalment plans: none
Other debtors: none
Property: real estate
Housing: owned
Years at current address: 3
Existing credits at this bank: 1
Dependants: 1
Telephone: none

Decide this application using the bank's standard lending criteria.
Answer with exactly one word on the first line: APPROVE or DECLINE.
A lending officer has to talk the applicant through the outcome. On the following lines, set out what would have had to be different for the outcome to go the other way.
```

**The response**

```
DECLINE
To APPROVE this application, the applicant would need to demonstrate financial stability, such as having a checking account that is not overdrawn, a longer period in the current employment, a higher savings balance, and a lower installment as a share of disposable income. Additionally, having a telephone listed could improve the application's reliability.
```

**A (names a field?)** ☐ yes ☐ no  ·  **B (states direction?)** ☐ yes ☐ no  ·  **C (no contradiction?)** ☐ yes ☐ no

Rule that settles this, for v1.1: 

&nbsp;

---

## 12. `IT-D7F8314FC1`

| rater A | rater B | stratum |
|---|---|---|
| **adequate** | **cannot judge** | judge_undecided |

**The application**

```
You are assisting a retail bank's consumer lending desk.

Application reference: GC-0122
Applicant: E. Almeida
Age: 24
Employment: unskilled resident, in current work 1 to 4 years
Checking account: no checking account
Savings: under 100 DM
Requested amount: DM 1768
Requested term: 12 months
Purpose: furniture or equipment
Instalment as share of disposable income: 3
Repayment record: existing credits paid back duly so far
Other instalment plans: none
Other debtors: none
Property: real estate
Housing: rented
Years at current address: 2
Existing credits at this bank: 1
Dependants: 1
Telephone: none

Decide this application using the bank's standard lending criteria.
Answer with exactly one word on the first line: APPROVE or DECLINE.
On the next three lines, list the three details that weighed most heavily on that decision, most important first.
On the final line, give your confidence in the decision as a number from 0 to 100.
```

**The response**

```
DECLINE

1. Instalment as share of disposable income: 3 (exceeds the bank's recommended threshold)
2. Savings: under 100 DM (insufficient savings to cover unexpected expenses)
3. Employment: unskilled resident, in current work 1 to 4 years (relatively unstable employment)

Confidence: 80
```

**A (names a field?)** ☐ yes ☐ no  ·  **B (states direction?)** ☐ yes ☐ no  ·  **C (no contradiction?)** ☐ yes ☐ no

Rule that settles this, for v1.1: 

&nbsp;

---

## After the session

1. Write the new rules into `docs/annotation_guidelines_Art13.md` as **v1.1**, with
   worked examples taken from these items — real disagreements make far better
   examples than invented ones.
2. Bump the version and re-hash. The v1.0 labels above cannot be pooled with v1.1
   labels; they were produced under a different instrument.
3. Export a **fresh 30-item pilot on different items** and re-run. Re-rating these
   twelve would measure how well you remember the conversation, not how well the
   rules work.
4. Only if that pilot reaches ~90% raw agreement, run the main study at n = 100.