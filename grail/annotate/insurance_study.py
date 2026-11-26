"""Human-agreement study on life-insurance premium explanations (guideline v2.0).

Two raters label the same explanations, blind to the model and to each other,
under `docs/annotation/guideline_insurance_v2.0.md`. This module does the four
mechanical steps and nothing else:

1. **draw**   - 240 main items and 20 calibration items from the transparency
               responses. Main: 30 per (model, request type), risk bands in
               proportion, so every explanation has the same chance of being
               drawn (self-weighting). Calibration: 20 other items.
2. **sheets** - one blinded CSV per rater, rows in a different random order for
               each rater, plus a key file the raters never see.
3. **check**  - a rater's calibration sheet against the arbiter's key (pass: 18
               of 20 by default).
4. **score**  - agreement between the two raters, overall and broken down by
               request type, model, risk band and failed check, so the report
               shows WHERE the raters agree and where they do not.

Labels are `adequate` / `inadequate`. Every `inadequate` carries one reason
code (E1-E3 for explanation items, C1-C4 for counterfactual items); note codes
(title, invented, format, immutable) are recorded but never decide the label.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass

from grail.annotate.agreement import cohen_kappa, gwet_ac1
from grail.annotate.judge_validation import bca_bounds
from grail.probe.schema import derive_rng

LABELS = ("adequate", "inadequate")
REQUEST = {"explanation_request": "explanation",
           "counterfactual_request": "counterfactual"}
REASONS = {"explanation": ("E1", "E2", "E3"),
           "counterfactual": ("C1", "C2", "C3", "C4")}
NOTE_CODES = ("title", "invented", "format", "immutable")
SHEET_COLUMNS = ["item", "request", "prompt", "response",
                 "label", "reason", "note_codes", "notes"]
KEY_FILE = "KEY_do_not_open_until_scored.json"
AC1_GATE = 0.61


@dataclass
class Design:
    per_cell: int = 30          # items per (model, request type) in the main sample
    calibration: int = 20       # items outside the main sample
    calibration_pass: float = 0.90   # 18 of 20
    seed: int = 20261125
    guideline_sha256: str = ""


# --------------------------------------------------------------------- draw

def token_for(probe_id: str, seed: int, model_id: str = "") -> str:
    """The blinded item id a rater sees, from the probe AND the model: one probe
    answered by four models is four things to rate, never one."""
    h = hashlib.blake2b(f"{seed}|{probe_id}|{model_id}".encode(), digest_size=5).hexdigest()
    return f"IT-{h.upper()}"


def candidates(probes: list, responses: list, models: list[str] | None = None) -> list[dict]:
    """One candidate per (transparency probe, model), matched by content hash.

    Matching on the probe's content hash rather than its id means a response is
    never shown next to a prompt it did not answer. If a model answered the same
    probe twice, the first logged answer is used.
    """
    first: dict[tuple[str, str], object] = {}
    for r in responses:
        if getattr(r, "error", None) or not (r.response or "").strip():
            continue
        if models and r.model_id not in models:
            continue
        first.setdefault((r.probe_sha256, r.model_id), r)
    out = []
    for p in probes:
        if p.dimension != "transparency" or p.variant not in REQUEST:
            continue
        for (sha, model), r in first.items():
            if sha != p.content_sha256:
                continue
            out.append({"probe_id": p.id, "model_id": model,
                        "request": REQUEST[p.variant], "stratum": p.stratum,
                        "prompt": p.prompt, "response": r.response})
    out.sort(key=lambda c: (c["model_id"], c["request"], c["probe_id"]))
    return out


def proportional(sizes: dict[str, int], k: int) -> dict[str, int]:
    """Split k over groups in proportion to their sizes (largest remainder)."""
    total = sum(sizes.values())
    if total == 0 or k <= 0:
        return {g: 0 for g in sizes}
    k = min(k, total)
    exact = {g: k * n / total for g, n in sizes.items()}
    alloc = {g: min(sizes[g], int(v)) for g, v in exact.items()}
    order = sorted(sizes, key=lambda g: (-(exact[g] - int(exact[g])), g))
    i = 0
    while sum(alloc.values()) < k:
        g = order[i % len(order)]
        if alloc[g] < sizes[g]:
            alloc[g] += 1
        i += 1
    return alloc


def draw(cands: list[dict], design: Design) -> tuple[list[dict], list[dict], dict]:
    """(main items, calibration items, shortfall per cell)."""
    rng = derive_rng(design.seed, "insurance_v2_draw")
    cells: dict[tuple, list] = defaultdict(list)
    for c in cands:
        cells[(c["model_id"], c["request"])].append(c)
    main, shortfall = [], {}
    for cell in sorted(cells):
        items = cells[cell]
        bands: dict[str, list] = defaultdict(list)
        for c in items:
            bands[c["stratum"]].append(c)
        alloc = proportional({b: len(v) for b, v in bands.items()}, design.per_cell)
        for b in sorted(bands):
            pool = sorted(bands[b], key=lambda c: c["probe_id"])
            main.extend(rng.sample(pool, alloc[b]))
        if len(items) < design.per_cell:
            shortfall[f"{cell[0]} / {cell[1]}"] = design.per_cell - len(items)
    chosen = {(c["probe_id"], c["model_id"]) for c in main}
    rest = [c for c in cands if (c["probe_id"], c["model_id"]) not in chosen]
    calib = _spread(rest, design.calibration, rng)
    return main, calib, shortfall


def _spread(pool: list[dict], k: int, rng) -> list[dict]:
    """k items spread as evenly as possible over (model, request) cells."""
    cells: dict[tuple, list] = defaultdict(list)
    for c in pool:
        cells[(c["model_id"], c["request"])].append(c)
    for v in cells.values():
        rng.shuffle(v)
    out, keys = [], sorted(cells)
    while len(out) < k and any(cells[c] for c in keys):
        for c in keys:
            if cells[c] and len(out) < k:
                out.append(cells[c].pop())
    return out


# ------------------------------------------------------------------- sheets

def _write_sheet(path: str, rows: list[dict]) -> None:
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=SHEET_COLUMNS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in SHEET_COLUMNS})


def _rows(items: list[dict], seed: int, order_salt: str) -> list[dict]:
    rows = [{"item": token_for(c["probe_id"], seed, c["model_id"]),
             "request": c["request"], "prompt": c["prompt"],
             "response": c["response"]} for c in items]
    rows.sort(key=lambda r: r["item"])
    derive_rng(seed, "order", order_salt).shuffle(rows)
    return rows


def write_study(main: list[dict], calib: list[dict], design: Design, out_dir: str,
                raters: tuple[str, ...] = ("A", "B")) -> dict:
    """Blinded sheets for each rater and the arbiter, plus the key file."""
    os.makedirs(out_dir, exist_ok=True)
    key_path = os.path.join(out_dir, KEY_FILE)
    if os.path.exists(key_path):
        raise FileExistsError(
            f"{key_path} exists. A study is drawn once; delete the folder only if "
            "no rater has started.")
    paths = {}
    for r in raters:
        paths[f"rater_{r}"] = os.path.join(out_dir, f"rater_{r}.csv")
        _write_sheet(paths[f"rater_{r}"], _rows(main, design.seed, f"main-{r}"))
        paths[f"calibration_{r}"] = os.path.join(out_dir, f"calibration_rater_{r}.csv")
        _write_sheet(paths[f"calibration_{r}"], _rows(calib, design.seed, f"cal-{r}"))
    paths["calibration_key"] = os.path.join(out_dir, "calibration_arbiter_key.csv")
    _write_sheet(paths["calibration_key"], _rows(calib, design.seed, "cal-key"))

    def meta(c, part):
        return {"probe_id": c["probe_id"], "model_id": c["model_id"],
                "request": c["request"], "stratum": c["stratum"], "part": part}
    items = {token_for(c["probe_id"], design.seed, c["model_id"]): meta(c, "main") for c in main}
    items.update({token_for(c["probe_id"], design.seed, c["model_id"]): meta(c, "calibration")
                  for c in calib})
    key = {"design": asdict(design), "n_main": len(main), "n_calibration": len(calib),
           "labels": list(LABELS), "reasons": {k: list(v) for k, v in REASONS.items()},
           "note_codes": list(NOTE_CODES), "items": items}
    with open(key_path, "w", encoding="utf-8") as fh:
        json.dump(key, fh, indent=2, ensure_ascii=False)
    paths["key"] = key_path
    return paths


# ------------------------------------------------------------- load + check

class SheetError(ValueError):
    pass


def load_sheet(path: str, require_complete: bool = True) -> dict[str, dict]:
    """{item: {label, reason, note_codes, notes, request}} with the v2.0 rules checked."""
    with open(path, encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    out, problems = {}, []
    for r in rows:
        item = r["item"].strip()
        label = (r.get("label") or "").strip().lower()
        request = (r.get("request") or "").strip()
        reason = (r.get("reason") or "").strip().upper()
        notes_c = [n.strip().lower() for n in (r.get("note_codes") or "").replace(";", ",").split(",")
                   if n.strip()]
        if not label:
            if require_complete:
                problems.append(f"{item}: no label")
            continue
        if label not in LABELS:
            problems.append(f"{item}: label '{label}' is not adequate/inadequate")
        if label == "inadequate" and reason not in REASONS.get(request, ()):
            problems.append(f"{item}: inadequate needs a reason code from "
                            f"{'/'.join(REASONS.get(request, ()))}, got '{reason}'")
        if label == "adequate" and reason:
            problems.append(f"{item}: adequate must not carry a reason code ('{reason}')")
        bad = [n for n in notes_c if n not in NOTE_CODES]
        if bad:
            problems.append(f"{item}: unknown note code(s) {bad}")
        out[item] = {"label": label, "reason": reason if label == "inadequate" else "",
                     "note_codes": sorted(set(notes_c)), "notes": r.get("notes", ""),
                     "request": request}
    if problems:
        raise SheetError(f"{os.path.basename(path)}: " + "; ".join(problems[:20])
                         + (f" (+{len(problems) - 20} more)" if len(problems) > 20 else ""))
    return out


def sha256_file(path: str) -> str:
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def check_calibration(rater: dict, key: dict, pass_share: float = 0.90) -> dict:
    items = sorted(set(rater) & set(key))
    if len(items) != len(key):
        raise SheetError(f"calibration sheet covers {len(items)} of {len(key)} key items")
    hits = [i for i in items if rater[i]["label"] == key[i]["label"]]
    misses = [{"item": i, "rater": rater[i]["label"] + (f" ({rater[i]['reason']})" if rater[i]["reason"] else ""),
               "key": key[i]["label"] + (f" ({key[i]['reason']})" if key[i]["reason"] else ""),
               "request": key[i]["request"]} for i in items if i not in hits]
    need = -(-int(round(pass_share * len(items) * 100)) // 100)  # ceil
    return {"n": len(items), "correct": len(hits), "needed": need,
            "passed": len(hits) >= need, "misses": misses}


# -------------------------------------------------------------------- score

def _pi_bi(a: list[str], b: list[str]) -> tuple[float, float]:
    n = len(a)
    both_ad = sum(1 for x, y in zip(a, b) if x == y == "adequate")
    both_in = sum(1 for x, y in zip(a, b) if x == y == "inadequate")
    a_only = sum(1 for x, y in zip(a, b) if x == "adequate" and y == "inadequate")
    b_only = sum(1 for x, y in zip(a, b) if x == "inadequate" and y == "adequate")
    return abs(both_ad - both_in) / n, abs(a_only - b_only) / n


def _ac1(a, b):
    return gwet_ac1(a, b)[0]


def summary(a: list[str], b: list[str], bootstrap: bool = True,
            iterations: int = 4000, seed: int = 20261125) -> dict:
    n = len(a)
    if n == 0:
        return {"n": 0}
    kappa, po, pe, _ = cohen_kappa(a, b)
    ac1 = _ac1(a, b)
    pi, bi = _pi_bi(a, b)
    out = {"n": n, "agree": sum(1 for x, y in zip(a, b) if x == y),
           "p_o": round(po, 4), "kappa": None if kappa is None else round(kappa, 4),
           "ac1": None if ac1 is None else round(ac1, 4),
           "PI": round(pi, 4), "BI": round(bi, 4),
           "adequate_A": round(a.count("adequate") / n, 4),
           "adequate_B": round(b.count("adequate") / n, 4)}
    if bootstrap and n >= 10:
        # Two-sided 95%: each one-sided bound at alpha = 0.025.
        _, lo, hi = bca_bounds(_ac1, [a, b], iterations=iterations, seed=seed, alpha=0.025)
        out["ac1_ci95"] = [None if lo is None else round(lo, 4),
                           None if hi is None else round(hi, 4)]
    return out


def score(sheet_a: dict, sheet_b: dict, key: dict, iterations: int = 4000) -> dict:
    """Where do the two raters agree? Overall, by subgroup, and by failed check."""
    meta = {k: v for k, v in key["items"].items() if v["part"] == "main"}
    items = sorted(set(sheet_a) & set(sheet_b) & set(meta))
    missing = sorted(set(meta) - set(items))
    a = [sheet_a[i]["label"] for i in items]
    b = [sheet_b[i]["label"] for i in items]
    seed = key["design"]["seed"]
    overall = summary(a, b, iterations=iterations, seed=seed)
    lo = (overall.get("ac1_ci95") or [None])[0]
    gate = {"threshold": AC1_GATE, "ac1_lower_95": lo,
            "result": ("met" if lo is not None and lo >= AC1_GATE else
                       "not met" if overall.get("ac1_ci95", [None, None])[1] is not None
                       and overall["ac1_ci95"][1] < AC1_GATE else "undetermined")}

    def by(field):
        groups = defaultdict(list)
        for i in items:
            groups[meta[i][field]].append(i)
        return {g: summary([sheet_a[i]["label"] for i in ids],
                           [sheet_b[i]["label"] for i in ids],
                           bootstrap=len(ids) >= 30, iterations=min(iterations, 2000), seed=seed)
                for g, ids in sorted(groups.items())}

    both_in = [i for i in items if sheet_a[i]["label"] == sheet_b[i]["label"] == "inadequate"]
    same_reason = sum(1 for i in both_in if sheet_a[i]["reason"] == sheet_b[i]["reason"])
    split = [i for i in items if sheet_a[i]["label"] != sheet_b[i]["label"]]
    split_reasons = Counter((sheet_a[i]["reason"] or sheet_b[i]["reason"]) for i in split)
    reasons = {"A": Counter(sheet_a[i]["reason"] for i in items if sheet_a[i]["reason"]),
               "B": Counter(sheet_b[i]["reason"] for i in items if sheet_b[i]["reason"])}
    checks = {}
    for code in sorted({c for v in REASONS.values() for c in v}):
        fa = [sheet_a[i]["reason"] == code for i in items]
        fb = [sheet_b[i]["reason"] == code for i in items]
        checks[code] = {"A": sum(fa), "B": sum(fb), "both": sum(x and y for x, y in zip(fa, fb)),
                        "only_one": sum(x != y for x, y in zip(fa, fb))}
    notes = {}
    for code in NOTE_CODES:
        fa = [code in sheet_a[i]["note_codes"] for i in items]
        fb = [code in sheet_b[i]["note_codes"] for i in items]
        notes[code] = {"A": sum(fa), "B": sum(fb), "both": sum(x and y for x, y in zip(fa, fb))}
    disagreements = [{"item": i, "request": meta[i]["request"], "stratum": meta[i]["stratum"],
                      "A": sheet_a[i]["label"] + (f" {sheet_a[i]['reason']}" if sheet_a[i]["reason"] else ""),
                      "B": sheet_b[i]["label"] + (f" {sheet_b[i]['reason']}" if sheet_b[i]["reason"] else "")}
                     for i in split]
    return {"n_items": len(items), "missing": missing, "overall": overall, "gate": gate,
            "by_request": by("request"), "by_model": by("model_id"), "by_band": by("stratum"),
            "both_inadequate": len(both_in), "same_reason_when_both_inadequate": same_reason,
            "reason_codes": {k: dict(v) for k, v in reasons.items()},
            "checks": checks, "disagreement_driven_by": dict(split_reasons),
            "note_codes": notes, "disagreements": disagreements}


def _plain(rep: dict) -> str:
    """The subgroup results in words: highest and lowest agreement, and the
    check the raters split on most."""
    o = rep["overall"]
    parts = [f"The two raters gave the same label on {o['agree']} of {o['n']} explanations "
             f"({o['p_o']:.0%})."]
    for name, key in (("request type", "by_request"), ("model", "by_model"), ("risk band", "by_band")):
        groups = [(g, s) for g, s in rep[key].items() if s.get("n") and s.get("ac1") is not None]
        if len(groups) < 2:
            continue
        hi = max(groups, key=lambda x: x[1]["ac1"])
        lo = min(groups, key=lambda x: x[1]["ac1"])
        parts.append(f"By {name}, agreement is highest for {hi[0]} (AC1 {hi[1]['ac1']:.2f}, "
                     f"{hi[1]['p_o']:.0%} same label) and lowest for {lo[0]} "
                     f"(AC1 {lo[1]['ac1']:.2f}, {lo[1]['p_o']:.0%}).")
    split = rep["disagreement_driven_by"]
    if split:
        code, k = max(split.items(), key=lambda x: x[1])
        parts.append(f"Of the {sum(split.values())} split items, {k} were failed on check "
                     f"{code or '(none given)'} by one rater and passed by the other, so that rule "
                     "is the first to clarify.")
    if rep["both_inadequate"]:
        parts.append(f"When both raters failed an explanation they named the same check in "
                     f"{rep['same_reason_when_both_inadequate']} of {rep['both_inadequate']} cases.")
    return " ".join(parts)


def _f(x, nd=2):
    return "-" if x is None else f"{x:.{nd}f}"


def render(rep: dict, title: str = "Human agreement - insurance explanations (guideline v2.0)") -> str:
    o, g = rep["overall"], rep["gate"]
    ci = o.get("ac1_ci95") or [None, None]
    L = [f"# {title}", "",
         f"Items rated by both raters: **{rep['n_items']}**"
         + (f" ({len(rep['missing'])} main items still missing)" if rep["missing"] else ""), "",
         "## Overall", "",
         "| Raw agreement | Cohen's kappa | Gwet's AC1 [95% BCa] | PI | BI | adequate A / B |",
         "|---|---|---|---|---|---|",
         f"| {o['agree']}/{o['n']} = {_f(o['p_o'])} | {_f(o['kappa'])} | {_f(o['ac1'])} "
         f"[{_f(ci[0])}, {_f(ci[1])}] | {_f(o['PI'])} | {_f(o['BI'])} | "
         f"{_f(o['adequate_A'])} / {_f(o['adequate_B'])} |", "",
         f"Reliability gate (lower 95% bound of AC1 >= {g['threshold']}): **{g['result']}**", ""]
    L += ["## Where the raters agree, in one paragraph", "", _plain(rep), ""]
    for name, key in (("request type", "by_request"), ("model", "by_model"), ("risk band", "by_band")):
        L += [f"## By {name}", "", "| Group | n | Raw agreement | kappa | AC1 | adequate A / B |",
              "|---|---|---|---|---|---|"]
        for grp, s in rep[key].items():
            L.append(f"| {grp} | {s['n']} | {_f(s['p_o'])} | {_f(s['kappa'])} | {_f(s['ac1'])} | "
                     f"{_f(s['adequate_A'])} / {_f(s['adequate_B'])} |")
        L.append("")
    L += ["## Which checks fail, and do the raters fail the same ones?", "",
          f"Both raters said inadequate on {rep['both_inadequate']} items; they gave the same "
          f"reason code on {rep['same_reason_when_both_inadequate']} of them.", "",
          "| Check | Rater A | Rater B | Both | Only one |", "|---|---|---|---|---|"]
    for code, c in rep["checks"].items():
        if c["A"] or c["B"]:
            L.append(f"| {code} | {c['A']} | {c['B']} | {c['both']} | {c['only_one']} |")
    L += ["", "Disagreements, by the reason code of the rater who said inadequate: "
          + (", ".join(f"{k or 'none'} {v}" for k, v in sorted(rep["disagreement_driven_by"].items()))
             or "none"), "",
          "## Note codes (recorded, never decide the label)", "",
          "| Code | Rater A | Rater B | Both |", "|---|---|---|---|"]
    for code, c in rep["note_codes"].items():
        L.append(f"| {code} | {c['A']} | {c['B']} | {c['both']} |")
    L += ["", f"## Items the raters disagree on ({len(rep['disagreements'])}) - go to the arbiter", "",
          "| Item | Request | Band | Rater A | Rater B |", "|---|---|---|---|---|"]
    for d in rep["disagreements"]:
        L.append(f"| {d['item']} | {d['request']} | {d['stratum']} | {d['A']} | {d['B']} |")
    return "\n".join(L) + "\n"


def write_arbiter_sheet(rep: dict, rows_source: str, out_path: str) -> int:
    """Disputed items, with both labels hidden, in the rater-sheet format."""
    disputed = {d["item"] for d in rep["disagreements"]}
    with open(rows_source, encoding="utf-8") as fh:
        rows = [r for r in csv.DictReader(fh) if r["item"] in disputed]
    for r in rows:
        for k in ("label", "reason", "note_codes", "notes"):
            r[k] = ""
    _write_sheet(out_path, rows)
    return len(rows)


def reference(sheet_a: dict, sheet_b: dict, arbiter: dict, key: dict) -> dict:
    """R*: the agreed label, or the arbiter's where the raters differ."""
    out = {}
    for i, m in key["items"].items():
        if m["part"] != "main" or i not in sheet_a or i not in sheet_b:
            continue
        if sheet_a[i]["label"] == sheet_b[i]["label"]:
            out[i] = {"label": sheet_a[i]["label"], "source": "agreed"}
        elif i in arbiter:
            out[i] = {"label": arbiter[i]["label"], "source": "arbiter",
                      "reason": arbiter[i]["reason"]}
        else:
            out[i] = {"label": None, "source": "awaiting arbiter"}
        out[i].update({"probe_id": m["probe_id"], "model_id": m["model_id"]})
    return out
