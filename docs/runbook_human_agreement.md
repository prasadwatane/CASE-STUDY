# Runbook — human agreement on insurance explanations (CAL1)

Goal: two raters label the same 240 life-insurance premium explanations under
guideline v2.0, and `agreement.md` shows where they agree. Calibration of the
explanation check, not a research question (Amendment A2, revised 25 Nov 2026).

Time: about 1 hour of GPU work, then 2–4 working days for the raters.

## Before you start

- Push your local changes from the Mac first (`git push`), so the server gets this
  version.
- The pre-registration says the hypotheses are signed **before** any insurance
  response exists. Sign `docs/protocol/PREREGISTRATION.md` (you and both
  supervisors), or at least have the professor's written OK by e-mail and note
  the date in the record, before step 4.
- Freeze the guideline: from now on `docs/annotation/guideline_insurance_v2.0.md`
  is not edited. Its SHA-256 goes into the key file in step 5.

## On the server

```bash
# 0. code and environment
cd /home/jovyan/work && git pull
python3 scripts/bootstrap_server.py           # only if the container was recycled
source .venv/bin/activate

# 1. real applicants: NHANES 1999-2004 + linked mortality (about 40 MB)
python scripts/fetch_nhanes.py
python scripts/fetch_nhanes.py --verify
python scripts/import_nhanes.py               # writes data/records/nhanes/applicants.jsonl

# 2. checklist for Annex III 5(c): read the draft, then sign it yourself.
#    Easiest on the Mac, where the parsed Act already exists; then commit
#    data/processed/checklists/insurance_signed.json, push, and git pull here.
python scripts/derive_checklist.py insurance
python scripts/sign_checklist.py insurance "Prasad Devendra Watane"

# 3. the frozen probe set (14,825 per model; only the 152 explanation prompts run now)
python scripts/generate_probes.py insurance
#    check the output says:  stimulus pack 'life_insurance_nhanes'
#    and:  transparency 152 prompts (counterfactual_request=76, explanation_request=76)

# 3b. optional 10-second dry run, written outside the real log
python scripts/run_probes.py insurance --stub --dimension transparency --out /tmp/stubrun

# 4. the explanation prompts on the four models (152 each; 10–20 min per model, mostly loading)
HF_TOKEN=... GIT_TOKEN=... nohup bash scripts/run_models.sh insurance --dimension transparency \
    > logs/runs.log 2>&1 &
tail -f logs/runs.log                          # finished when logs/DONE exists

# 5. draw the sample and build the rater packets
python scripts/human_agreement.py export insurance
git add -A && git commit -m "Insurance explanations and rater packets" && git push
```

Step 5 writes `data/processed/annotation/insurance/`:

| File | Who | Items |
|---|---|---|
| `calibration_arbiter_key.html` | arbiter | 20 |
| `calibration_rater_A.html`, `calibration_rater_B.html` | raters | 20 each |
| `rater_A.html`, `rater_B.html` | raters | 240 each |
| `KEY_do_not_open_until_scored.json` | nobody until scoring | — |

Each HTML file opens in any browser, works offline, saves as the rater goes, and
ends with a **Download CSV** button. The rater sends back the CSV with the same
name; put it in the same folder.

## With the raters (on the Mac after `git pull`)

| Day | Step | Command |
|---|---|---|
| 1 | Arbiter fills `calibration_arbiter_key.html` (20 items) | — |
| 1–2 | Each rater does `calibration_rater_X.html` | `python scripts/human_agreement.py calibration insurance` (pass = 18 of 20) |
| 2–4 | Both raters do all 240 items (about 1 minute per item) | — |
| any time | Progress check on what is back so far | `python scripts/human_agreement.py score insurance --partial` |
| 4–5 | Agreement report | `python scripts/human_agreement.py score insurance` → `agreement.md` |
| 5 | Arbiter does `arbiter.html` (disputed items only, labels hidden) | `python scripts/human_agreement.py reference insurance` → `reference_labels.json` |

Rules that keep the result valid:

- Raters never see the model, the judge or each other's labels; the author
  neither rates nor arbitrates.
- A calibration miss is fixed by clarifying a **rule** (new guideline version, new
  hash), never by discussing the item. Then calibrate again on fresh items.
- Labels are not changed after a sheet is returned; doubts go in the note.

## What `agreement.md` contains

Raw agreement, Cohen's κ, Gwet's AC1 with a 95% BCa interval, PI and BI; the
same by request type (explanation / counterfactual), by model and by risk band;
which checks (E1–E3, C1–C4) each rater failed and whether they failed the same
ones; note codes; a one-paragraph summary of where the raters agree most and
least; and the list of disputed items. The gate is met when the lower 95% bound
of AC1 is at least 0.61.

## If something fails

| Problem | Fix |
|---|---|
| NHANES download blocked on the server | Run `fetch_nhanes.py` on the Mac, copy `data/records/nhanes/raw/` to the server, then run `import_nhanes.py` there. |
| Pack line says `life_insurance`, not `life_insurance_nhanes` | `import_nhanes.py` did not finish; rerun it and step 3 (`--force` only if no response exists yet). |
| `No parsed corpus. Run scripts/build_index.py first.` | Do step 2 on the Mac, or here: `pip install -r requirements.txt && python scripts/build_index.py`. |
| A model fails to load | The sweep continues with the next one; rerun step 4 later — finished models are cached and cost nothing. |
| `export` says a cell is short | A model produced errors or empty answers; check `logs/runs.log`, rerun step 4 for that model, then export again (delete the folder only if no rater has started). |
