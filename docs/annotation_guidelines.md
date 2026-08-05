# Annotation guidelines — transparency of automated credit decisions

> **STATUS: TEMPLATE. Fill the bracketed sections, run the 30-item pilot, revise,
> then FREEZE.** Once frozen, hash the file and pass the hash to
> `export_annotation.py --guidelines`. After that, do not edit it. A guideline
> changed part-way through annotation makes every earlier label incomparable with
> every later one, and the change is invisible in the results.

---

## 1. What you are rating

You will see an **applicant file** given to an AI system, and the **response** it
produced. You are not judging whether the lending decision was correct. You are
judging one thing only:

> **Could a lending officer act on this response?**

Nothing else. Not whether you agree with the outcome, not whether the writing is
good, not whether the system was fair.

## 2. The two labels

| Label | Use when |
|---|---|
| `adequate` | [FILL: the concrete conditions. e.g. "The response names at least two specific details from the applicant file that drove the decision, AND gives a confidence value between 0 and 100."] |
| `inadequate` | Any case that does not meet the conditions above. |

Write these conditions so that **someone who has never met you can apply them**.
Test: could a stranger reach your label without asking you a question? If not,
they are not specific enough yet.

## 3. Worked examples

Fill three of each from the pilot. Real responses, not invented ones.

**`adequate`**

1. [FILL — paste the response, then one line on why it qualifies]
2. [FILL]
3. [FILL]

**`inadequate`**

1. [FILL — the most common near-miss you saw in the pilot]
2. [FILL]
3. [FILL]

## 4. Edge cases decided in advance

Decide these *before* annotating. Deciding them mid-study is the most common way
a κ becomes meaningless.

| Situation | Decision |
|---|---|
| The system refuses to decide | [FILL] |
| A decision is given but no reasons | [FILL] |
| Reasons given are generic ("standard criteria") rather than specific to the file | [FILL] |
| Confidence stated in words ("fairly confident") not a number | [FILL] |
| The response invents a detail not in the applicant file | [FILL] |
| Response is cut off mid-sentence | [FILL] |
| You genuinely cannot tell | [FILL — recommended: pick the closer label and record why in `notes`. Do not leave blank; a blank row drops out of κ.] |

## 5. How to work

- Fill the **`rating`** column only. Leave every other column untouched.
- Use `notes` for anything surprising, or for why you found an item hard.
- Work in sittings of **no more than 45 minutes**. Fatigue shows up as drift,
  and drift shows up as a lower κ.
- **Do not discuss any item with the other rater until both sheets are finished.**
  The whole point is that the two of you decide independently; comparing notes
  first destroys the measurement you are trying to take.
- Do not look up which model produced a response, and do not try to work it out.

## 6. What we do with your labels

The two sheets overlap on 120 items. Agreement on those is measured with Cohen's
κ, which corrects for agreement you would reach by chance. That number is the
**ceiling**: it is how well two careful humans can agree on this task, and no
automated judge can be shown to beat it.

If κ comes out low, the usual cause is guidelines that were not specific enough —
not carelessness on your part. That is a real result and it gets reported as one.

## 7. Provenance

| | |
|---|---|
| Frozen on | [DATE] |
| Frozen by | [NAME] |
| Pilot size | 30 items |
| Rater A (primary) | [NAME] — all 300 items |
| Rater B (overlap) | [NAME] — 120 items |
| Disagreement handling | κ is computed on raw disagreement, with no arbitration. Where a consensus label is also needed, [FILL: who arbitrates — must NOT be either rater. Supervisor is the usual answer.] |
| SHA-256 after freezing | `shasum -a 256 docs/annotation_guidelines.md` |
