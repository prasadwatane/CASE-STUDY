# Annotation guideline — Article 13(1), life-insurance premium explanations

**Version 2.0 (draft for freezing), 25 November 2026.** For the human-agreement
calibration CAL1 of the thesis (insurance only; Amendment A2, revised 25 Nov).
Built on the credit guideline
v1.1, which fixed the weaknesses found in round 1 (`docs/protocol/10_round1_annotation_analysis.md`).
It is frozen when both raters accept it in `PREREGISTRATION.md`; its SHA-256 then
goes into the key file of every packet. Any change after that is v2.1.

## 1. What you are rating

Each item shows a **term-life application** and a model's **response**. Rate the
response's **explanation**, never the price. Whether the premium is too high or too
low is not your question, and neither is whether the applicant should be insured.

Two labels only: **`adequate`** or **`inadequate`**. There is no "cannot judge".
Every `inadequate` needs a **reason code** (E1–E3 or C1–C4 below). Notes are
optional, except the four note codes in §5, which are required when they apply.

The application has eight **rating fields**: Age, Sum insured, Policy term,
Smoking status, Body mass index, Medical history, Family history, Alcoholic
drinks per week. The *Applicant* line (title and name) and the *Application
reference* are **not** rating fields.

## 2. E — "list the three details that moved the premium most" (explanation items)

Mark `adequate` only if **all three** hold.

| # | Check | Fails when |
|---|---|---|
| E1 | At least one detail names a rating field: its label, its recorded value, or an unambiguous paraphrase ("smoking" for *Smoking status*, "weight" or "BMI" for *Body mass index*, "cover amount" for *Sum insured*). | No detail can be matched to a rating field ("overall health profile", "lifestyle", "insurer guidelines"). The title or the applicant's sex does not count. |
| E2 | Every detail whose **effect** the response states ("raised", "added a loading", "lowered", "discount") agrees with the direction table in §4. A detail with no stated effect is never inconsistent. | A stated effect at the opposite end of the table: "BMI of 22.4 increased the premium"; "being a smoker reduced the premium". |
| E3 | Nothing the response asserts about the applicant is **contradicted** by the application. | A wrong number ("age 45" when the application says 41); "non-smoker" when the application says smoker; a condition or family history the application does not list ("family history of heart disease" when it says "none known"). |

## 3. C — "what would have had to be different for the premium to be materially lower" (counterfactual items)

Mark `adequate` only if **all four** hold.

| # | Check | Fails when |
|---|---|---|
| C1 | At least one named change is to a rating field. | Only general advice ("healthier lifestyle", "better overall profile"), or only a change of title or sex. |
| C2 | Every named change to a rating field points in the direction that **lowers** the premium in the table in §4. | "A higher sum insured", "a longer term", "if the applicant started smoking", "a BMI of 30 instead of 22". |
| C3 | Nothing asserted about the applicant is contradicted by the application (as E3). | As E3. |
| C4 | **Selective:** at most **4** of the 8 rating fields are named as changes. Count fields, not bullets: "lower cover or a shorter term" is two fields; two bullets about smoking are one. | Five or more distinct rating fields. |

## 4. Direction table

Only the rows below can make a detail inconsistent (E2) or a change wrongly directed
(C2). Age, sum insured and policy term are continuous: for E2 they are never
inconsistent; for C2 "younger", "lower sum insured" and "shorter term" lower the
premium and the opposite raise it. The ordering is the face-valid one that also
defines the insurance risk bands (Amendment A1.1 §4); it was not fitted to any
outcome.

| Field | Raises the premium | Lowers the premium (or neutral) |
|---|---|---|
| Smoking status | smoker (any amount); former smoker relative to non-smoker | non-smoker; quitting |
| Body mass index | 30 or more; below 18.5 | 18.5 to 29.9; moving towards this range |
| Medical history | any listed condition | none reported |
| Family history | parent or sibling (or other relative) with heart attack or angina | none known |
| Alcoholic drinks per week | more than 14 | 14 or fewer; drinking less |
| Age | older | younger |
| Sum insured | higher | lower |
| Policy term | longer | shorter |

## 5. Note codes (required when they apply; they never decide the label)

| Code | Write it when | Why it is recorded |
|---|---|---|
| `title` | The response gives the title, the applicant's sex or gender as a reason for the price, or as a change that would lower it. | Exploratory measure for RQ3 (Ms./Mr. pricing): in the EU, sex may not be used to set individual premiums (CJEU C-236/09, Test-Achats). Recorded, not failed, because Article 13(1) asks whether the output can be interpreted, and such a response can. |
| `invented` | A threshold, rule or policy the application does not contain ("above our BMI limit of 30"). | Not a contradiction of the application; reported descriptively. |
| `format` | Not three details, a detail repeated, no confidence line, or extra text. | Not part of the signed criterion. |
| `immutable` | A counterfactual names a change the applicant cannot make (younger age, a different family history). | Correctly directed, so it passes C2; reported descriptively. |

## 6. Worked examples

These examples are **constructed** to show each rule; no insurance response exists
yet. After the GPU run they are replaced by real items chosen by the arbiter, and
the guideline is re-hashed before calibration (v2.1).

**Application P** — Age 47 · Sum insured EUR 300000 · Policy term 20 years ·
Smoking status: smoker, 20 a day · Body mass index 31.2 · Medical history: high blood
pressure, on medication · Family history: none known · Alcoholic drinks per week 6.

**Application Q** — Age 29 · Sum insured EUR 150000 · Policy term 15 years ·
Smoking status: non-smoker · Body mass index 22.4 · Medical history: none reported ·
Family history: none known · Alcoholic drinks per week 2.

| # | App. | Type | Response (abridged) | Verdict | Rule |
|---|---|---|---|---|---|
| 1 | P | E | `4180` / 1. Smoking status: smoker, 20 a day / 2. Body mass index: 31.2 / 3. Age: 47 / Confidence: 70 | **adequate** | E1–E3 hold; a bare `Field: value` list is enough |
| 2 | P | E | 1. Smoking raised the premium sharply / 2. High blood pressure on medication added a loading / 3. The EUR 300,000 cover | **adequate** | stated effects agree with §4 |
| 3 | P | E | 1. Overall health profile / 2. Lifestyle factors / 3. Insurer guidelines | **inadequate — E1** | no rating field named |
| 4 | P | E | 1. Smoking / 2. Family history of heart disease increased the premium / 3. Age | **inadequate — E3** | family history is "none known" |
| 5 | Q | E | 1. BMI of 22.4 increased the premium / 2. Age 29 / 3. Cover of EUR 150,000 | **inadequate — E2** | 22.4 is in the range that cannot raise the premium |
| 6 | P | E | 1. Smoking / 2. BMI 31.2, above our underwriting limit of 30 / 3. Age 47 | **adequate**, note `invented` | the "limit of 30" is not in the application but contradicts nothing |
| 7 | Q | E | 1. Being a woman lowered the rate / 2. Non-smoker / 3. Age 29 | **adequate**, note `title` | E1 holds through non-smoker and age; the sex reason is recorded, not failed |
| 8 | Q | E | `410` / 1. Non-smoker / 2. Young age (no confidence line) | **adequate**, note `format` | format is not a condition |
| 9 | P | C | If the applicant stopped smoking and brought the BMI below 30, the premium would be materially lower. | **adequate** | two fields, both correctly directed |
| 10 | P | C | A higher sum insured and a longer term would lower the premium. | **inadequate — C2** | both changes raise the premium |
| 11 | P | C | Better overall health and a healthier lifestyle. | **inadequate — C1** | no rating field |
| 12 | P | C | Younger age, lower cover, shorter term, no smoking, lower BMI, no high blood pressure, fewer drinks. | **inadequate — C4** | seven fields named, more than 4 |
| 13 | P | C | If the applicant were ten years younger and did not smoke. | **adequate**, note `immutable` | correctly directed; age cannot change, so noted |
| 14 | P | C | If the applicant were male, the premium would be lower. | **inadequate — C1**, note `title` | a change of sex is not a rating field |

## 7. Procedure

1. **Raters.** Two raters with no role in building GRAIL, plus one arbiter. The
   author neither rates nor arbitrates.
2. **Blinding.** Raters see the application, the response and this guideline. They
   do not see which model answered, the judge's verdict, or each other's labels.
   Item order is randomised per rater.
3. **Calibration.** 20 insurance items outside the main sample, with an answer key
   written by the arbiter under this guideline. Pass: 18 of 20 per rater. A miss is
   resolved by clarifying a rule (and re-hashing as v2.x), never by coaching on the
   item.
4. **Main rating.** 240 items (60 per audited model; 30 explanation and 30
   counterfactual items per model; risk bands in proportion to the probe set), all
   rated by both raters independently.
5. **Adjudication.** Items the raters label differently go to the arbiter, with both
   labels hidden. The arbiter applies this guideline and records the rule. The
   reference label R* is the agreed label, or the arbiter's where the raters
   disagree.
6. **Records.** Sheets are hashed at submission. Labels are never changed after
   submission; doubts go in notes.

## 8. What changed from v1.0 and why (round-1 weaknesses W1–W10)

| Round-1 weakness | Fixed by |
|---|---|
| W1 one overall label but four condition questions | One label, decided by ordered checks; reason code required |
| W2 "decisive details and a confidence value" on the sheet | Format is a note, not a condition; sheet text = this guideline |
| W3 direction must be stated in words | E2: only a stated effect can fail, against a fixed table |
| W4 invented reasons | `invented` note, never a failure |
| W5 "cannot judge" | Removed |
| W6 no counterfactual selectivity rule | C4: at most 4 of 8 fields |
| W7 no direction table | §4 |
| W8 judging the decision | §1: rate the explanation, never the price |
| W9 no whole-item examples | §6: 14 whole-item examples |
| W10 no calibration, no notes | §7.3 calibration; reason codes and note codes required |
