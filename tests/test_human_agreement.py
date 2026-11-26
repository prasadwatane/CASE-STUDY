"""Insurance human-agreement study (guideline v2.0): draw, sheets, checks, scoring."""
import csv
import json
import os
import random
import sys
from collections import Counter
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from grail.annotate import insurance_study as S
from grail.annotate.packet import packet

MODELS = ["m/a", "m/b", "m/c", "m/d"]
BANDS = ["low_risk"] * 15 + ["borderline"] * 46 + ["high_risk"] * 15   # 76 per family


def _probes_and_responses(models=MODELS):
    probes, responses = [], []
    for fam in ("explanation_request", "counterfactual_request"):
        for i, band in enumerate(BANDS):
            p = SimpleNamespace(id=f"t-{fam[:3]}-{i:03d}", dimension="transparency", variant=fam,
                                stratum=band, prompt=f"application {i} ({fam})",
                                content_sha256=f"sha-{fam}-{i}")
            probes.append(p)
            for m in models:
                responses.append(SimpleNamespace(probe_sha256=p.content_sha256, model_id=m,
                                                 response=f"answer {i} v{models.index(m)}", error=""))
    probes.append(SimpleNamespace(id="f-1", dimension="fairness", variant="Ms.", stratum="borderline",
                                  prompt="x", content_sha256="sha-f"))
    return probes, responses


def _study(tmp_path):
    probes, responses = _probes_and_responses()
    cands = S.candidates(probes, responses)
    design = S.Design(guideline_sha256="g" * 64)
    main, calib, short = S.draw(cands, design)
    paths = S.write_study(main, calib, design, str(tmp_path))
    return cands, main, calib, short, paths


def test_candidates_are_transparency_only_one_per_probe_and_model():
    probes, responses = _probes_and_responses()
    responses.append(SimpleNamespace(probe_sha256="sha-explanation_request-0", model_id="m/a",
                                     response="second answer", error=""))
    cands = S.candidates(probes, responses)
    assert len(cands) == 152 * 4
    assert {c["request"] for c in cands} == {"explanation", "counterfactual"}
    first = [c for c in cands if c["probe_id"] == "t-exp-000" and c["model_id"] == "m/a"]
    assert len(first) == 1 and first[0]["response"] == "answer 0 v0"


def test_main_sample_is_30_per_cell_with_bands_in_proportion(tmp_path):
    _, main, calib, short, _ = _study(tmp_path)
    assert len(main) == 240 and not short
    cells = Counter((c["model_id"], c["request"]) for c in main)
    assert set(cells.values()) == {30}
    bands = Counter(c["stratum"] for c in main)
    # 30 of 76 per cell: 6 low, 18 borderline, 6 high -> same inclusion probability everywhere
    assert bands == {"borderline": 18 * 8, "low_risk": 6 * 8, "high_risk": 6 * 8}


def test_calibration_items_are_outside_the_main_sample_and_spread(tmp_path):
    _, main, calib, _, _ = _study(tmp_path)
    assert len(calib) == 20
    ids = {(c["probe_id"], c["model_id"]) for c in main}
    assert not ids & {(c["probe_id"], c["model_id"]) for c in calib}
    per_cell = Counter((c["model_id"], c["request"]) for c in calib)
    assert max(per_cell.values()) - min(per_cell.values()) <= 1


def test_draw_is_deterministic(tmp_path):
    probes, responses = _probes_and_responses()
    cands = S.candidates(probes, responses)
    a = S.draw(cands, S.Design())
    b = S.draw(cands, S.Design())
    assert [c["probe_id"] + c["model_id"] for c in a[0]] == [c["probe_id"] + c["model_id"] for c in b[0]]


def test_sheets_are_blind_and_ordered_differently(tmp_path):
    _, main, _, _, paths = _study(tmp_path)
    rows_a = list(csv.DictReader(open(paths["rater_A"])))
    rows_b = list(csv.DictReader(open(paths["rater_B"])))
    assert list(rows_a[0].keys()) == S.SHEET_COLUMNS
    assert {r["item"] for r in rows_a} == {r["item"] for r in rows_b}
    assert [r["item"] for r in rows_a] != [r["item"] for r in rows_b]
    text = open(paths["rater_A"]).read()
    assert not any(m in text for m in MODELS) and "t-exp-" not in text
    key = json.load(open(paths["key"]))
    assert key["n_main"] == 240 and key["design"]["guideline_sha256"] == "g" * 64
    with pytest.raises(FileExistsError):
        S.write_study(main, [], S.Design(), str(tmp_path))


def _fill(path, labeler):
    rows = list(csv.DictReader(open(path)))
    for r in rows:
        r.update(labeler(r))
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=S.SHEET_COLUMNS)
        w.writeheader()
        w.writerows(rows)


def test_sheet_rules_are_enforced(tmp_path):
    _, _, _, _, paths = _study(tmp_path)
    p = paths["calibration_A"]
    _fill(p, lambda r: {"label": "inadequate", "reason": ""})
    with pytest.raises(S.SheetError, match="needs a reason code"):
        S.load_sheet(p)
    _fill(p, lambda r: {"label": "inadequate", "reason": "C4" if r["request"] == "explanation" else "C1"})
    with pytest.raises(S.SheetError, match="E1/E2/E3"):
        S.load_sheet(p)
    _fill(p, lambda r: {"label": "adequate", "reason": "", "note_codes": "title;made-up"})
    with pytest.raises(S.SheetError, match="unknown note code"):
        S.load_sheet(p)
    _fill(p, lambda r: {"label": "", "reason": "", "note_codes": ""})
    with pytest.raises(S.SheetError, match="no label"):
        S.load_sheet(p)
    assert S.load_sheet(p, require_complete=False) == {}


def _truth(paths):
    key = json.load(open(paths["key"]))
    rng = random.Random(3)
    return {k: "adequate" if rng.random() < 0.7 else "inadequate" for k in key["items"]}


def _labeler(truth, flip=set()):
    def f(r):
        lab = truth[r["item"]]
        if r["item"] in flip:
            lab = "adequate" if lab == "inadequate" else "inadequate"
        code = ("E1" if r["request"] == "explanation" else "C2") if lab == "inadequate" else ""
        return {"label": lab, "reason": code, "note_codes": ""}
    return f


def test_calibration_pass_is_18_of_20(tmp_path):
    _, _, _, _, paths = _study(tmp_path)
    t = _truth(paths)
    _fill(paths["calibration_key"], _labeler(t))
    items = [r["item"] for r in csv.DictReader(open(paths["calibration_A"]))]
    _fill(paths["calibration_A"], _labeler(t, set(items[:2])))
    _fill(paths["calibration_B"], _labeler(t, set(items[:3])))
    key = S.load_sheet(paths["calibration_key"])
    ra = S.check_calibration(S.load_sheet(paths["calibration_A"]), key)
    rb = S.check_calibration(S.load_sheet(paths["calibration_B"]), key)
    assert (ra["correct"], ra["needed"], ra["passed"]) == (18, 18, True)
    assert (rb["correct"], rb["passed"], len(rb["misses"])) == (17, False, 3)


def test_score_reports_where_raters_agree_and_builds_the_reference(tmp_path):
    _, _, _, _, paths = _study(tmp_path)
    t = _truth(paths)
    items = [r["item"] for r in csv.DictReader(open(paths["rater_A"]))]
    _fill(paths["rater_A"], _labeler(t))
    _fill(paths["rater_B"], _labeler(t, set(items[:12])))
    key = json.load(open(paths["key"]))
    rep = S.score(S.load_sheet(paths["rater_A"]), S.load_sheet(paths["rater_B"]), key, iterations=400)
    assert rep["n_items"] == 240 and rep["overall"]["agree"] == 228
    assert len(rep["disagreements"]) == 12
    assert set(rep["by_request"]) == {"explanation", "counterfactual"}
    assert set(rep["by_model"]) == set(MODELS)
    assert rep["gate"]["result"] in {"met", "not met", "undetermined"}
    assert rep["overall"]["ac1_ci95"][0] <= rep["overall"]["ac1"] <= rep["overall"]["ac1_ci95"][1]
    md = S.render(rep)
    assert "Where the raters agree" in md and "go to the arbiter" in md

    arb = os.path.join(str(tmp_path), "arbiter.csv")
    assert S.write_arbiter_sheet(rep, paths["rater_A"], arb) == 12
    assert all(r["label"] == "" for r in csv.DictReader(open(arb)))
    _fill(arb, _labeler(t))
    ref = S.reference(S.load_sheet(paths["rater_A"]), S.load_sheet(paths["rater_B"]),
                      S.load_sheet(arb), key)
    assert len(ref) == 240 and all(v["label"] == t[k] for k, v in ref.items())
    assert Counter(v["source"] for v in ref.values()) == {"agreed": 228, "arbiter": 12}


def test_packet_is_self_contained_html(tmp_path):
    _, _, _, _, paths = _study(tmp_path)
    g = tmp_path / "g.md"
    g.write_text("# Guideline\n\n| a | b |\n|---|---|\n| E1 | rule |\n")
    out = packet(paths["calibration_A"], str(g), "Rater A - calibration")
    page = open(out, encoding="utf-8").read()
    assert page.startswith("<!DOCTYPE html>") and "http" not in page.split("<script>")[1]
    assert "calibration_rater_A.csv" in page and "<td>E1</td>" in page
    assert "m/a" not in page          # model identity never reaches the rater
