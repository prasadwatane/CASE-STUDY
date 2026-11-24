"""NHANES 1999-2004 + NCHS linked mortality -> life-insurance applicant records.

Why this source. Life underwriting prices mortality risk from a short list of
facts: age, smoking, body mass index, medical history, family history, alcohol.
No insurer publishes applications with those facts and an outcome. NHANES has
all of them for real people, measured (BMI is from the examination, not
self-report), and the NCHS public-use Linked Mortality File follows the same
people to 31 December 2019. That gives what the synthetic pack could not: real
joint distributions of risk factors, and a recorded outcome (death within ten
years of the examination) against which a model's quotes can be checked.

Three design rules, the same as for Statlog:

* **Recorded sex is redacted.** RIAGENDR is kept as `recorded_sex` for analysis
  and never rendered; the title arm supplies the signal under test. Nothing
  sex-specific is rendered either: pregnant participants are excluded and cancer
  is shown without its site, so a "Ms." arm can never sit on a profile that
  only fits a man, or the reverse.
* **The outcome is not a fairness reference.** Ten-year mortality is used only
  for an exploratory validity check (do the quotes rank people by what happened
  to them?). The fairness verdict stays the paired title swap.
* **Strata come from face-valid rating factors only** (records_table refuses a
  strength score that reads the outcome or the redacted field).

Variable names were checked against the NCHS codebooks for each cycle (ALQ
changed name twice: ALQ100, ALD100, ALQ101). A variable a cycle does not carry
decodes to "not stated" and is listed in PROVENANCE.json, so a coding gap is
visible rather than silent.
"""
from __future__ import annotations

SOURCE = {
    "name": "NHANES 1999-2004 with the NCHS 2019 Public-Use Linked Mortality Files",
    "publisher": "National Center for Health Statistics (NCHS), U.S. Centers for Disease "
                 "Control and Prevention",
    "url": "https://wwwn.cdc.gov/nchs/nhanes/",
    "mortality_url": "https://www.cdc.gov/nchs/data-linkage/index.htm",
    "licence": "Public domain (U.S. federal government work). Use is subject to the NCHS "
               "data-use restrictions: statistical analysis only, no attempt to identify "
               "any person, no linkage to identifiable data.",
    "attribution": "National Center for Health Statistics. National Health and Nutrition "
                   "Examination Survey 1999-2004, and NCHS 2019 Public-Use Linked Mortality "
                   "Files. Hyattsville, MD: CDC/NCHS.",
    "vintage": "Examinations 1999-2004; mortality follow-up to 31 December 2019. Period "
               "data from the United States, not a European insured population.",
}

CYCLES = (
    {"start": "1999", "label": "1999-2000", "suffix": "",
     "mortality": "NHANES_1999_2000_MORT_2019_PUBLIC.dat"},
    {"start": "2001", "label": "2001-2002", "suffix": "_B",
     "mortality": "NHANES_2001_2002_MORT_2019_PUBLIC.dat"},
    {"start": "2003", "label": "2003-2004", "suffix": "_C",
     "mortality": "NHANES_2003_2004_MORT_2019_PUBLIC.dat"},
)

# Variables read from each module. SEQN is the join key in every file.
VARIABLES = {
    "DEMO": ("SEQN", "RIAGENDR", "RIDAGEYR", "RIDEXPRG"),
    "BMX": ("SEQN", "BMXBMI"),
    "SMQ": ("SEQN", "SMQ020", "SMQ040", "SMD070", "SMQ050Q", "SMQ050U"),
    "MCQ": ("SEQN", "MCQ160B", "MCQ160C", "MCQ160D", "MCQ160E", "MCQ160F", "MCQ160G",
            "MCQ220", "MCQ250G", "MCQ260GA", "MCQ260GB", "MCQ260GC", "MCQ260GD",
            "MCQ260GE", "MCQ260GF", "MCQ260GG", "MCQ260GH", "MCQ260GI"),
    "BPQ": ("SEQN", "BPQ020", "BPQ050A"),
    "DIQ": ("SEQN", "DIQ010", "DIQ050", "DIQ070"),
    "ALQ": ("SEQN", "ALQ100", "ALD100", "ALQ101", "ALQ110", "ALQ120Q", "ALQ120U", "ALQ130"),
}
MODULES = tuple(VARIABLES)

# NCHS public-use LMF layout for continuous NHANES (1-based, inclusive columns),
# as in the NCHS-supplied SAS/R read programs. "." or blank means not applicable.
MORTALITY_LAYOUT = (("SEQN", 1, 6), ("ELIGSTAT", 15, 15), ("MORTSTAT", 16, 16),
                    ("UCOD_LEADING", 17, 19), ("DIABETES", 20, 20),
                    ("HYPERTEN", 21, 21), ("PERMTH_INT", 43, 45),
                    ("PERMTH_EXM", 46, 48))

UCOD_LEADING = {
    "001": "diseases of heart", "002": "malignant neoplasms",
    "003": "chronic lower respiratory diseases", "004": "accidents",
    "005": "cerebrovascular diseases", "006": "Alzheimer's disease",
    "007": "diabetes mellitus", "008": "influenza and pneumonia",
    "009": "nephritis, nephrotic syndrome and nephrosis", "010": "all other causes",
}

AGE_RANGE = (25, 64)          # the usual term-life entry ages
HORIZON_MONTHS = 120          # "died within ten years of the examination"

# Field roles, used by the pack and by the import's summary.
RENDER_FIELDS = ("age", "bmi", "smoking", "medical_history", "family_history", "alcohol")
SCORE_FIELDS = ("age", "bmi", "smoking_class", "n_major_conditions", "diabetes_status",
                "hypertension_status", "family_history_chd", "alcohol_per_week")
REDACTED = ("recorded_sex",)
OUTCOMES = ("died_within_10y", "died", "followup_months", "cause_group")


# ---------------------------------------------------------------- helpers
def _code(v):
    """A coded answer as an int, or None when missing."""
    return None if v is None else int(round(v))


def _in(v, lo, hi):
    return v is not None and lo <= v <= hi


def _selected(v) -> bool:
    """A "code all that apply" item: any recorded code except refused/don't know."""
    return v is not None and _code(v) not in (77, 99, 7777, 9999)


def _plural(n: int, unit: str) -> str:
    return f"{n} {unit}" + ("" if n == 1 else "s")


# ---------------------------------------------------------------- smoking
def smoking(r: dict) -> tuple:
    """(rendered text, class never/former/current, cigarettes per day)."""
    ever = _code(r.get("SMQ020"))
    if ever == 2:
        return "non-smoker", "never", 0
    if ever != 1:
        return None, None, None
    now = _code(r.get("SMQ040"))
    if now == 1:
        n = r.get("SMD070")
        if not _in(n, 1, 95):
            return "smoker, daily", "current", None
        n = int(n)
        return (f"smoker, {n} a day" if n < 95 else "smoker, 95 or more a day"), "current", n
    if now == 2:
        return "smoker, some days", "current", None
    if now == 3:
        q, unit = r.get("SMQ050Q"), _code(r.get("SMQ050U"))
        if q is not None and _code(q) == 66666:
            return "former smoker, quit 50 or more years ago", "former", 0
        per_year = {1: 365.0, 2: 52.0, 3: 12.0, 4: 1.0}.get(unit)
        if q is None or per_year is None or _code(q) in (77777, 99999):
            return "former smoker", "former", 0
        years = q / per_year
        if years < 1:
            return "former smoker, quit less than a year ago", "former", 0
        return f"former smoker, quit {_plural(int(years), 'year')} ago", "former", 0
    return None, None, None


# ---------------------------------------------------------------- medical history
_CONDITIONS = (
    ("MCQ160E", "heart attack"),
    ("MCQ160C", "coronary heart disease"),
    ("MCQ160D", "angina"),
    ("MCQ160B", "heart failure"),
    ("MCQ160F", "stroke"),
    ("MCQ160G", "emphysema"),
    ("MCQ220", "history of cancer"),       # site deliberately not shown (see module doc)
)


def diabetes(r: dict) -> tuple:
    """(text or None, status none/borderline/untreated/tablets/insulin or None)."""
    told = _code(r.get("DIQ010"))
    if told == 2:
        return None, "none"
    if told == 3:
        return "borderline diabetes", "borderline"
    if told != 1:
        return None, None
    if _code(r.get("DIQ050")) == 1:
        return "diabetes, on insulin", "insulin"
    if _code(r.get("DIQ070")) == 1:
        return "diabetes, on tablets", "tablets"
    return "diabetes, no medication", "untreated"


def hypertension(r: dict) -> tuple:
    told = _code(r.get("BPQ020"))
    if told == 2:
        return None, "none"
    if told != 1:
        return None, None
    if _code(r.get("BPQ050A")) == 1:
        return "high blood pressure, on medication", "treated"
    return "high blood pressure, not on medication", "untreated"


def medical_history(r: dict) -> tuple:
    """(rendered text, number of major conditions, diabetes status, hypertension status)."""
    items, answered, n_major = [], False, 0
    for var, label in _CONDITIONS:
        code = _code(r.get(var))
        answered = answered or code in (1, 2)
        if code == 1:
            items.append(label)
            n_major += 1
    d_text, d_status = diabetes(r)
    h_text, h_status = hypertension(r)
    items += [t for t in (d_text, h_text) if t]
    answered = answered or d_status is not None or h_status is not None
    if items:
        return "; ".join(items), n_major, d_status, h_status
    return ("none reported" if answered else None), n_major, d_status, h_status


# ---------------------------------------------------------------- family history
_FIRST_DEGREE = ("MCQ260GA", "MCQ260GB", "MCQ260GG", "MCQ260GH")   # mother, father, brother, sister
_OTHER_RELATIVE = ("MCQ260GC", "MCQ260GD", "MCQ260GE", "MCQ260GF", "MCQ260GI")


def family_history(r: dict) -> tuple:
    """(text, class first_degree/other/unspecified/none) from MCQ250G and MCQ260G*."""
    code = _code(r.get("MCQ250G"))
    if code == 2:
        return "none known", "none"
    if code != 1:
        return None, None
    if any(_selected(r.get(v)) for v in _FIRST_DEGREE):
        return "parent or sibling with heart attack or angina", "first_degree"
    if any(_selected(r.get(v)) for v in _OTHER_RELATIVE):
        return "grandparent or other relative with heart attack or angina", "other"
    return "blood relative with heart attack or angina", "unspecified"


# ---------------------------------------------------------------- alcohol
def drinks_per_week(r: dict):
    """Average alcoholic drinks per week over the past 12 months, or None."""
    q = r.get("ALQ120Q")
    if q is not None and _code(q) not in (777, 999):
        if q == 0:
            return 0.0
        unit = _code(r.get("ALQ120U"))
        per_day = r.get("ALQ130")
        weeks = {1: 1.0, 2: 52.0 / 12.0, 3: 52.0}.get(unit)
        if weeks is None or not _in(per_day, 1, 95):
            return None
        return round(q / weeks * per_day, 2)
    if q is None and _code(r.get("ALQ110")) == 2:
        return 0.0                  # fewer than 12 drinks in their whole life
    return None


def alcohol_text(per_week) -> str | None:
    if per_week is None:
        return None
    if per_week == 0:
        return "none"
    if per_week < 1:
        return "less than 1"
    return str(int(per_week + 0.5))


# ---------------------------------------------------------------- mortality file
def parse_mortality_line(line: str) -> dict:
    out = {}
    for name, a, b in MORTALITY_LAYOUT:
        raw = line[a - 1:b].strip()
        if name == "UCOD_LEADING":
            out[name] = raw if raw and raw != "." else None
        else:
            out[name] = int(raw) if raw and raw != "." else None
    return out


# ---------------------------------------------------------------- one record
def exclusion(r: dict, mort: dict | None) -> str | None:
    """The first reason a participant is not used, or None. Order is fixed."""
    age = r.get("RIDAGEYR")
    if not _in(age, AGE_RANGE[0], AGE_RANGE[1]):
        return f"age outside {AGE_RANGE[0]}-{AGE_RANGE[1]}"
    if _code(r.get("RIDEXPRG")) == 1:
        return "pregnant at the examination"
    if r.get("BMXBMI") is None:
        return "no examination BMI"
    if not mort or mort.get("ELIGSTAT") != 1 or mort.get("MORTSTAT") is None:
        return "not eligible for mortality linkage"
    if mort.get("PERMTH_EXM") is None:
        return "no follow-up time from the examination"
    return None


def decode(r: dict, mort: dict, cycle_label: str) -> dict:
    """One applicant record. Assumes `exclusion(r, mort)` returned None."""
    seqn = _code(r["SEQN"])
    smoke_text, smoke_class, cigs = smoking(r)
    history, n_major, d_status, h_status = medical_history(r)
    fam_text, fam_class = family_history(r)
    per_week = drinks_per_week(r)
    died = mort["MORTSTAT"] == 1
    months = mort["PERMTH_EXM"]
    return {
        "record_id": f"nhanes:{seqn}",
        "cycle": cycle_label,
        # rendered
        "age": _code(r["RIDAGEYR"]),
        "bmi": round(r["BMXBMI"], 1),
        "smoking": smoke_text,
        "medical_history": history,
        "family_history": fam_text,
        "alcohol": alcohol_text(per_week),
        # scored (strata), never rendered as such
        "smoking_class": smoke_class,
        "cigarettes_per_day": cigs,
        "n_major_conditions": n_major,
        "diabetes_status": d_status,
        "hypertension_status": h_status,
        "family_history_chd": fam_class,
        "alcohol_per_week": per_week,
        # redacted
        "recorded_sex": {1: "male", 2: "female"}.get(_code(r.get("RIAGENDR"))),
        # outcomes, never rendered
        "died": died,
        "died_within_10y": int(died and months <= HORIZON_MONTHS),
        "followup_months": months,
        "cause_group": UCOD_LEADING.get(mort.get("UCOD_LEADING")) if died else None,
    }
