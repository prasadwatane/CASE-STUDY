"""Real life-insurance applicants: NHANES 1999-2004 + linked mortality (Amendment A1.1).

The raw data are not in the repository (scripts/fetch_nhanes.py downloads them),
so everything here runs on a synthetic fixture written in the same formats: SAS
transport files and the NCHS fixed-width mortality layout. What must hold:

  * our XPORT reader agrees with pandas, value for value;
  * the decoding rules say what the survey answers say, and nothing more;
  * the import is deterministic and accounts for every excluded participant;
  * the record-backed pack keeps recorded sex, the outcome and the survey id
    out of every prompt, and pairs still differ only in the title;
  * the strata cannot be built from the outcome or the protected attribute;
  * the validity check reads the quotes against recorded mortality, and stays
    silent for packs that carry no outcome.
"""
from __future__ import annotations

import copy
import json
import math
import os
import random
import re
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from config import STIMULUS_DIR  # noqa: E402
from grail.jury import continuous as C  # noqa: E402
from grail.jury.verdict import EXPLORATORY, Finding, deliberate  # noqa: E402
from grail.probe import nhanes  # noqa: E402
from grail.probe import records_table as RT  # noqa: E402
from grail.probe.generate import generate_probeset  # noqa: E402
from grail.probe.templates import load_pack, render, sample_case  # noqa: E402
from grail.probe.xport import read_xport, write_xport  # noqa: E402
from grail.run.client import StubModel  # noqa: E402
from grail.run.runner import run  # noqa: E402
from tests.test_insurance import _signed  # noqa: E402

PACK = "life_insurance_nhanes"
ALQ_NAME = {"": "ALQ100", "_B": "ALD100", "_C": "ALQ101"}   # as in the NCHS codebooks
SEQN_START = {"": 1, "_B": 9966, "_C": 21005}


# ---------------------------------------------------------------- fixture
def _participant(r: random.Random, seqn: int) -> dict:
    sex = r.choice([1, 2])
    age = r.randint(18, 80)
    smoker = r.random()
    row = {
        "SEQN": seqn, "RIAGENDR": sex, "RIDAGEYR": age,
        "RIDEXPRG": (1 if sex == 2 and age < 45 and r.random() < 0.08 else 2) if sex == 2 else None,
        "BMXBMI": None if r.random() < 0.04 else round(r.uniform(17, 46), 1),
        "SMQ020": 2 if smoker < 0.5 else 1,
        "SMQ040": None if smoker < 0.5 else (1 if smoker < 0.7 else 2 if smoker < 0.75 else 3),
    }
    row["SMD070"] = r.choice([5, 10, 20, 30, 999]) if row["SMQ040"] == 1 else None
    row["SMQ050Q"] = r.choice([3, 8, 15, 66666, 99999]) if row["SMQ040"] == 3 else None
    row["SMQ050U"] = r.choice([3, 4]) if row["SMQ040"] == 3 else None
    for v in ("MCQ160B", "MCQ160C", "MCQ160D", "MCQ160E", "MCQ160F", "MCQ160G", "MCQ220"):
        row[v] = 1 if r.random() < 0.05 + age / 1500 else r.choice([2, 2, 2, 2, 9])
    row["MCQ250G"] = r.choice([1, 2, 2, 2, 9])
    row["MCQ260GA"] = 1 if row["MCQ250G"] == 1 and r.random() < 0.5 else None
    row["MCQ260GC"] = 3 if row["MCQ250G"] == 1 and row["MCQ260GA"] is None and r.random() < 0.5 else None
    row["BPQ020"] = 1 if r.random() < 0.1 + age / 200 else 2
    row["BPQ050A"] = r.choice([1, 2]) if row["BPQ020"] == 1 else None
    row["DIQ010"] = 1 if r.random() < 0.03 + age / 800 else r.choice([2, 2, 2, 3])
    row["DIQ050"] = r.choice([1, 2]) if row["DIQ010"] == 1 else 2
    row["DIQ070"] = r.choice([1, 2]) if row["DIQ010"] == 1 else None
    a = r.random()
    row["ALQ_12_YEAR"] = 2 if a < 0.3 else 1
    row["ALQ110"] = r.choice([1, 2]) if row["ALQ_12_YEAR"] == 2 else None
    drinks = row["ALQ_12_YEAR"] == 1 or row["ALQ110"] == 1
    unit = r.choice([1, 2, 3])
    days = {1: [0, 1, 3, 6], 2: [0, 1, 4, 12], 3: [0, 2, 10, 52]}[unit]
    row["ALQ120Q"] = r.choice(days) if drinks else None
    row["ALQ120U"] = unit if row["ALQ120Q"] else None
    row["ALQ130"] = r.choice([1, 2, 4, 99]) if row["ALQ120Q"] else None
    risk = 0.01 + (age / 100) ** 3 + (0.08 if row["SMQ040"] in (1, 2) else 0)
    died = r.random() < risk
    row["_mort"] = {"ELIGSTAT": 1 if r.random() > 0.02 else 3, "MORTSTAT": int(died),
                    "UCOD": r.choice(["001", "002", "010"]) if died else None,
                    "PERMTH_EXM": r.randint(1, 200) if died else r.randint(181, 249)}
    return row


def build_raw(dirpath: str, n_per_cycle: int = 150, seed: int = 7) -> None:
    """Write 21 XPORT files and 3 mortality files shaped like the NCHS ones."""
    os.makedirs(dirpath, exist_ok=True)
    r = random.Random(seed)
    for c in nhanes.CYCLES:
        sfx = c["suffix"]
        people = [_participant(r, SEQN_START[sfx] + i) for i in range(n_per_cycle)]
        for mod, variables in nhanes.VARIABLES.items():
            cols = {}
            for v in variables:
                if mod == "ALQ" and v in ("ALQ100", "ALD100", "ALQ101"):
                    if v != ALQ_NAME[sfx]:
                        continue                  # each cycle carries one of the three
                    cols[v] = [p["ALQ_12_YEAR"] for p in people]
                    continue
                if v in ("MCQ260GB", "MCQ260GD", "MCQ260GE", "MCQ260GF", "MCQ260GG",
                         "MCQ260GH", "MCQ260GI"):
                    cols[v] = [None] * len(people)
                    continue
                cols[v] = [None if p.get(v) is None else float(p[v]) for p in people]
            write_xport(os.path.join(dirpath, f"{mod}{sfx}.xpt"), f"{mod}{sfx}"[:8], cols)
        with open(os.path.join(dirpath, c["mortality"]), "w", encoding="latin-1") as fh:
            for p in people:
                m = p["_mort"]
                elig = m["ELIGSTAT"]
                mort = str(m["MORTSTAT"]) if elig == 1 else "."
                ucod = (m["UCOD"] or "   ") if elig == 1 else "   "
                months = f"{m['PERMTH_EXM']:>3}" if elig == 1 else "  ."
                fh.write(f"{p['SEQN']:>6}{' ' * 8}{elig}{mort}{ucod}..{' ' * 21}{months}{months}\n")


@pytest.fixture(scope="module")
def imported(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("nhanes")
    raw, out = str(tmp / "raw"), str(tmp / "out")
    build_raw(raw)
    cmd = [sys.executable, os.path.join(ROOT, "scripts", "import_nhanes.py"),
           "--raw", raw, "--out", out]
    res = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)
    assert res.returncode == 0, res.stderr
    with open(os.path.join(out, "PROVENANCE.json"), encoding="utf-8") as fh:
        prov = json.load(fh)
    path = os.path.join(out, "applicants.jsonl")
    with open(path, encoding="utf-8") as fh:
        records = [json.loads(line) for line in fh]
    return {"raw": raw, "out": out, "path": path, "prov": prov, "records": records, "cmd": cmd}


@pytest.fixture(scope="module")
def pack(imported):
    p = copy.deepcopy(load_pack(PACK, STIMULUS_DIR))
    p["source"]["path"] = imported["path"]
    return p


# ---------------------------------------------------------------- reader
def test_xport_reader_agrees_with_pandas(tmp_path):
    pd = pytest.importorskip("pandas")
    rng = random.Random(3)
    for n in (1, 7, 11, 240):
        cols = {"SEQN": [float(i + 1) for i in range(n)],
                "BMXBMI": [None if rng.random() < .1 else round(rng.uniform(15, 50), 1)
                           for _ in range(n)],
                "SMQ050Q": [rng.choice([1.0, 66666.0, 99999.0, None]) for _ in range(n)]}
        path = str(tmp_path / f"t{n}.xpt")
        write_xport(path, "T", cols)
        mine, theirs = read_xport(path), pd.read_sas(path, format="xport")
        assert mine["n"] == len(theirs) == n
        for c in cols:
            for a, b in zip(mine["columns"][c], theirs[c].tolist()):
                assert (a is None and math.isnan(b)) or a == pytest.approx(b, rel=1e-12)


def test_reader_returns_only_requested_columns_and_names_missing_ones(tmp_path):
    path = str(tmp_path / "t.xpt")
    write_xport(path, "T", {"SEQN": [1.0, 2.0], "A": [3.0, None]})
    got = read_xport(path, columns=("SEQN", "A", "NOT_THERE"))
    assert set(got["columns"]) == {"SEQN", "A"}
    assert got["columns"]["A"] == [3.0, None]


# ---------------------------------------------------------------- decoding
def test_smoking_rules():
    assert nhanes.smoking({"SMQ020": 2.0}) == ("non-smoker", "never", 0)
    assert nhanes.smoking({"SMQ020": 1.0, "SMQ040": 1.0, "SMD070": 20.0})[0] == "smoker, 20 a day"
    assert nhanes.smoking({"SMQ020": 1.0, "SMQ040": 1.0, "SMD070": 999.0})[0] == "smoker, daily"
    assert nhanes.smoking({"SMQ020": 1.0, "SMQ040": 2.0})[0] == "smoker, some days"
    quit3y = {"SMQ020": 1.0, "SMQ040": 3.0, "SMQ050Q": 3.0, "SMQ050U": 4.0}
    assert nhanes.smoking(quit3y)[:2] == ("former smoker, quit 3 years ago", "former")
    assert nhanes.smoking({**quit3y, "SMQ050Q": 8.0, "SMQ050U": 3.0})[0] == \
        "former smoker, quit less than a year ago"
    assert nhanes.smoking({**quit3y, "SMQ050Q": 18.0, "SMQ050U": 3.0})[0] == \
        "former smoker, quit 1 year ago"
    assert nhanes.smoking({**quit3y, "SMQ050Q": 66666.0})[0] == \
        "former smoker, quit 50 or more years ago"
    assert nhanes.smoking({**quit3y, "SMQ050Q": 99999.0})[0] == "former smoker"
    assert nhanes.smoking({"SMQ020": 9.0}) == (None, None, None)


def test_medical_history_lists_what_was_reported_and_only_that():
    r = {"MCQ160E": 1.0, "MCQ160C": 2.0, "MCQ220": 1.0, "DIQ010": 1.0, "DIQ050": 2.0,
         "DIQ070": 1.0, "BPQ020": 1.0, "BPQ050A": 1.0}
    text, n_major, d, h = nhanes.medical_history(r)
    assert text == ("heart attack; history of cancer; diabetes, on tablets; "
                    "high blood pressure, on medication")
    assert (n_major, d, h) == (2, "tablets", "treated")
    assert nhanes.medical_history({"MCQ160E": 2.0, "DIQ010": 2.0, "BPQ020": 2.0})[0] == \
        "none reported"
    assert nhanes.medical_history({})[0] is None          # nothing answered: "not stated"
    assert nhanes.medical_history({"DIQ010": 3.0})[0] == "borderline diabetes"
    assert nhanes.medical_history({"BPQ020": 1.0, "BPQ050A": 2.0})[0] == \
        "high blood pressure, not on medication"


def test_cancer_site_is_never_shown():
    # a site (prostate, breast, ...) would tie a profile to one sex and break the swap
    assert "history of cancer" in dict(nhanes._CONDITIONS).values()
    assert all("MCQ230" not in v for v in nhanes.VARIABLES["MCQ"])


def test_family_history_rules():
    assert nhanes.family_history({"MCQ250G": 2.0}) == ("none known", "none")
    assert nhanes.family_history({"MCQ250G": 1.0, "MCQ260GA": 1.0})[1] == "first_degree"
    assert nhanes.family_history({"MCQ250G": 1.0, "MCQ260GC": 3.0})[1] == "other"
    assert nhanes.family_history({"MCQ250G": 1.0, "MCQ260GA": 99.0})[1] == "unspecified"
    assert nhanes.family_history({"MCQ250G": 9.0}) == (None, None)


def test_alcohol_rules():
    assert nhanes.drinks_per_week({"ALQ120Q": 0.0}) == 0.0
    assert nhanes.drinks_per_week({"ALQ120Q": 3.0, "ALQ120U": 1.0, "ALQ130": 2.0}) == 6.0
    assert nhanes.drinks_per_week({"ALQ120Q": 52.0, "ALQ120U": 3.0, "ALQ130": 2.0}) == 2.0
    month = nhanes.drinks_per_week({"ALQ120Q": 13.0, "ALQ120U": 2.0, "ALQ130": 1.0})
    assert month == pytest.approx(3.0, abs=0.01)
    assert nhanes.drinks_per_week({"ALQ120Q": 3.0, "ALQ120U": 1.0, "ALQ130": 99.0}) is None
    assert nhanes.drinks_per_week({"ALQ110": 2.0}) == 0.0     # under 12 drinks in a lifetime
    assert nhanes.alcohol_text(0.0) == "none" and nhanes.alcohol_text(0.4) == "less than 1"
    assert nhanes.alcohol_text(6.5) == "7" and nhanes.alcohol_text(None) is None


def test_mortality_line_layout():
    line = f"{12345:>6}{' ' * 8}11002..{' ' * 21}{57:>3}{55:>3}"
    m = nhanes.parse_mortality_line(line)
    assert m == {"SEQN": 12345, "ELIGSTAT": 1, "MORTSTAT": 1, "UCOD_LEADING": "002",
                 "DIABETES": None, "HYPERTEN": None, "PERMTH_INT": 57, "PERMTH_EXM": 55}


def test_exclusions_in_fixed_order():
    ok = {"RIDAGEYR": 40.0, "RIDEXPRG": 2.0, "BMXBMI": 25.0}
    mort = {"ELIGSTAT": 1, "MORTSTAT": 0, "PERMTH_EXM": 200}
    assert nhanes.exclusion(ok, mort) is None
    assert nhanes.exclusion({**ok, "RIDAGEYR": 70.0}, mort).startswith("age outside")
    assert nhanes.exclusion({**ok, "RIDEXPRG": 1.0}, mort) == "pregnant at the examination"
    assert nhanes.exclusion({**ok, "BMXBMI": None}, mort) == "no examination BMI"
    assert nhanes.exclusion(ok, {**mort, "ELIGSTAT": 3}) == "not eligible for mortality linkage"
    assert nhanes.exclusion(ok, None) == "not eligible for mortality linkage"


def test_ten_year_outcome():
    r = {"SEQN": 5.0, "RIDAGEYR": 50.0, "RIAGENDR": 1.0, "BMXBMI": 28.04}
    died_early = nhanes.decode(r, {"MORTSTAT": 1, "PERMTH_EXM": 120, "UCOD_LEADING": "001"}, "x")
    died_late = nhanes.decode(r, {"MORTSTAT": 1, "PERMTH_EXM": 121, "UCOD_LEADING": "002"}, "x")
    alive = nhanes.decode(r, {"MORTSTAT": 0, "PERMTH_EXM": 200, "UCOD_LEADING": None}, "x")
    assert (died_early["died_within_10y"], died_late["died_within_10y"], alive["died_within_10y"]) == (1, 0, 0)
    assert died_early["cause_group"] == "diseases of heart" and alive["cause_group"] is None
    assert died_early["bmi"] == 28.0 and died_early["record_id"] == "nhanes:5"


# ---------------------------------------------------------------- the import
def test_import_accounts_for_every_participant(imported):
    prov = imported["prov"]
    total = sum(c["participants"] for c in prov["per_cycle"].values())
    assert total == 3 * 150
    assert len(imported["records"]) + sum(prov["excluded"].values()) == total
    assert prov["summary"]["n"] == len(imported["records"]) > 100
    assert all(25 <= r["age"] <= 64 for r in imported["records"])
    assert prov["variables_not_in_cycle"] == {}       # ALQ100/ALD100/ALQ101 are alternates
    assert set(prov["raw_sha256"]) >= {"DEMO.xpt", "ALQ_C.xpt", "NHANES_2003_2004_MORT_2019_PUBLIC.dat"}


def test_import_cross_checks_the_reader_against_pandas(imported):
    pytest.importorskip("pandas")
    check = imported["prov"]["reader_check"]
    assert check["values_compared"] > 10000 and check["mismatches"] == 0


def test_import_is_deterministic(imported):
    first = imported["prov"]["cleaned_sha256"]["applicants.jsonl"]
    res = subprocess.run(imported["cmd"], capture_output=True, text=True, cwd=ROOT)
    assert res.returncode == 0, res.stderr
    with open(os.path.join(imported["out"], "PROVENANCE.json"), encoding="utf-8") as fh:
        assert json.load(fh)["cleaned_sha256"]["applicants.jsonl"] == first


def test_strata_are_ordered_by_risk_in_the_fixture(imported):
    per = imported["prov"]["summary"]["strata"]["per_stratum"]
    assert per["low_risk"]["mean_score"] < per["borderline"]["mean_score"] < per["high_risk"]["mean_score"]


# ---------------------------------------------------------------- the pack
def test_pack_cannot_stratify_on_the_outcome_or_recorded_sex(pack):
    for field in ("died_within_10y", "recorded_sex"):
        bad = copy.deepcopy(pack["source"])
        bad["strength"][field] = {"map": {"1": 5}}
        with pytest.raises(SystemExit, match="stratifies on"):
            RT.check_spec(bad)
    leaky = copy.deepcopy(pack["source"])
    leaky["render_fields"] = leaky["render_fields"] + ["died_within_10y"]
    with pytest.raises(SystemExit, match="would render"):
        RT.check_spec(leaky)


def test_cases_keep_outcome_and_sex_out_of_the_prompt(pack):
    for i in range(30):
        for stratum in ("low_risk", "borderline", "high_risk"):
            slots = sample_case(pack, 11, "insurance", i, stratum)
            assert slots["_redacted_recorded_sex"] in ("male", "female")
            assert "_outcome_died_within_10y" in slots and "_score" in slots
            text = render(pack, dict(slots, title="Ms."))
            assert not re.search(r"\b(died|death|mortality|nhanes|male|female)\b", text.lower())
            assert "Ms." in text and "Mr." not in text
            # the application number is a hash of the record id, not the survey id
            ref = re.search(r"Application reference: LP-(\d+)", text).group(1)
            assert ref == RT.reference(slots["source_record"])


def test_policy_fields_are_fixed_per_person(pack):
    seen: dict = {}
    for seed in range(5):
        for i in range(40):
            s = sample_case(pack, seed, "insurance", i, "borderline")
            seen.setdefault(s["source_record"], set()).add((s["sum_insured"], s["term_years"]))
            assert 100000 <= s["sum_insured"] <= 500000 and s["sum_insured"] % 25000 == 0
            assert 10 <= s["term_years"] <= 25
    assert len(seen) < 200                       # people were drawn more than once ...
    assert all(len(v) == 1 for v in seen.values())   # ... and always with the same policy
    assert sample_case(pack, 1, "insurance", 0, "borderline") == \
        sample_case(pack, 1, "insurance", 0, "borderline")


def test_probe_set_on_real_records(pack, tmp_path):
    sizes = {"fairness": 30, "robustness": 6, "consistency": 4, "transparency": 3,
             "truthfulness": 300}
    ps, _ = generate_probeset(_signed(tmp_path, "insurance"), core_n=sizes, pack=pack)
    probes = ps.probes
    fair = [p for p in probes if p.dimension == "fairness"]
    assert fair and {p.family for p in fair} == {"premium_quotation_real"}
    pairs: dict = {}
    for p in fair:
        pairs.setdefault(p.pair_id, []).append(p)
    for members in pairs.values():
        a, b = members
        diff = [l for l, m in zip(a.prompt.splitlines(), b.prompt.splitlines()) if l != m]
        assert len(diff) == 1 and diff[0].startswith("Applicant:")
        assert a.slots["source_record"] == b.slots["source_record"]
    blob = "\n".join(p.prompt for p in probes)
    for term in ("died", "mortality", "NHANES", "SEQN", "nhanes:"):
        assert term not in blob
    assert {p.stratum for p in fair} == {"low_risk", "borderline", "high_risk"}
    # drawn without replacement: nobody sits in two pairs of the same stratum
    for stratum in ("low_risk", "borderline", "high_risk"):
        people = [p.slots["source_record"] for p in fair if p.stratum == stratum and p.arm == "female"]
        assert len(people) == len(set(people)) > 0


def test_a_used_up_pool_repeats_people_and_the_jury_counts_them_once(pack, tmp_path):
    # 200 pairs -> 120 borderline pairs from a fixture pool of ~91 people
    sizes = {"fairness": 200, "robustness": 4, "consistency": 3, "transparency": 2,
             "truthfulness": 300}
    ps, _ = generate_probeset(_signed(tmp_path, "insurance"), core_n=sizes, pack=pack)
    fair = [p for p in ps.probes if p.dimension == "fairness" and p.stratum == "borderline"]
    people = [p.slots["source_record"] for p in fair if p.arm == "female"]
    assert len(people) == 120 and len(set(people)) < 120      # the shuffle wrapped
    records, _ = run(ps.probes, StubModel(model_id="stub/hash"), str(tmp_path / "r.jsonl"),
                     allow_stub=True)
    res = deliberate(ps.probes, records, "stub/hash", primary_stratum="borderline")
    f = next(f for f in res["confirmatory"] if f["dimension"] == "fairness")
    assert f["detail"]["duplicate_pairs_counted_once"] == 120 - len(set(people))
    assert f["n"] == len(set(people))
    assert "counted once" in f["note"]


# ---------------------------------------------------------------- validity
def _people(n_died=40, n_alive=160, seed=0):
    r = random.Random(seed)
    return ([(1, r.randint(45, 64)) for _ in range(n_died)]
            + [(0, r.randint(25, 64)) for _ in range(n_alive)])


class _P:
    def __init__(self, i, y, age, dimension="fairness", arm="female"):
        self.dimension, self.family = dimension, "premium_quotation_real"
        self.slots = {"source_record": f"nhanes:{i}", "_outcome_died_within_10y": y, "age": age}
        self.arm, self.pair_id, self.stratum = arm, f"p{i}", "borderline"


class _O:
    def __init__(self, v):
        self.value = v


def _parsed(people, price):
    parsed = {}
    for i, (y, age) in enumerate(people):
        for arm in ("female", "male"):
            parsed[f"{i}:{arm}"] = (_P(i, y, age, arm=arm), _O(price(i, y, age)))
    return parsed


def test_validity_auc_reads_the_quotes_against_mortality():
    people = _people()
    perfect = C.risk_validity(_parsed(people, lambda i, y, a: 900 + 1000 * y), 0.05,
                              Finding, EXPLORATORY)[0]
    assert perfect.estimate == pytest.approx(1.0) and perfect.ci_high == 1.0
    assert perfect.dimension == "validity" and perfect.clause_ids == []
    flat = C.risk_validity(_parsed(people, lambda i, y, a: 500.0), 0.05, Finding, EXPLORATORY)[0]
    assert flat.estimate == pytest.approx(0.5) and flat.p_value == pytest.approx(1.0)
    by_age = C.risk_validity(_parsed(people, lambda i, y, a: 10.0 * a), 0.05,
                             Finding, EXPLORATORY)[0]
    assert by_age.estimate > 0.6                         # age alone already separates
    assert by_age.detail["age_adjusted_auc"] < by_age.estimate   # ... and adds little within bands
    assert by_age.detail["quotes_per_person"] == 2.0


def test_validity_auc_matches_a_brute_force_count():
    r = random.Random(5)
    pos = [r.choice([1.0, 2.0, 3.0]) for _ in range(30)]
    neg = [r.choice([1.0, 2.0, 3.0]) for _ in range(50)]
    brute = sum((p > n) + 0.5 * (p == n) for p in pos for n in neg) / (len(pos) * len(neg))
    assert C.auc(pos, neg) == pytest.approx(brute)


def test_validity_ignores_controls_and_packs_without_an_outcome():
    people = _people(5, 5)
    parsed = _parsed(people, lambda i, y, a: 900 + 1000 * y)
    # controls overwrite the record (a smoker swap, a best/worst profile), so a
    # control quote must never count: here it would invert the ranking
    for i, (y, age) in enumerate(people):
        parsed[f"control:{i}"] = (_P(i, y, age, dimension="control"), _O(5000.0 - 4000 * y))
    assert C.risk_validity(parsed, 0.05, Finding, EXPLORATORY)[0].estimate == pytest.approx(1.0)
    for p, _ in parsed.values():
        p.slots.pop("_outcome_died_within_10y")
    assert C.risk_validity(parsed, 0.05, Finding, EXPLORATORY) == []


def test_jury_reports_validity_for_the_record_pack(pack, tmp_path):
    sizes = {"fairness": 40, "robustness": 4, "consistency": 3, "transparency": 2,
             "truthfulness": 300}
    ps, _ = generate_probeset(_signed(tmp_path, "insurance"), core_n=sizes, pack=pack)
    probes = ps.probes

    def pricer(prompt: str) -> str:
        age = int(re.search(r"^(?:Age|Alter): (\d+)", prompt, re.M).group(1))
        smoker = "smoker," in prompt and "non-smoker" not in prompt
        return str(int(150 + 12 * age + (600 if smoker else 0)))

    records, _ = run(probes, StubModel(rule=pricer, model_id="stub/pricer"),
                     str(tmp_path / "r.jsonl"), allow_stub=True)
    res = deliberate(probes, records, "stub/pricer", primary_stratum="borderline")
    validity = [f for f in res["findings"] if f["dimension"] == "validity"]
    assert len(validity) == 1 and validity[0]["role"] == "exploratory"
    assert validity[0]["clause_ids"] == []
    fair = next(f for f in res["confirmatory"] if f["dimension"] == "fairness")
    assert fair["estimate"] == pytest.approx(0.0, abs=1e-12)   # title-blind pricer
