"""Decode the downloaded NHANES files into life-insurance applicant records.

    python3 scripts/import_nhanes.py
    python3 scripts/import_nhanes.py --raw DIR --out DIR     # (tests use this)

Reads data/records/nhanes/raw/ (filled by scripts/fetch_nhanes.py), joins DEMO,
BMX, SMQ, MCQ, BPQ, DIQ and ALQ on SEQN within each cycle, links the mortality
file, applies the inclusion rules and decoding in grail/probe/nhanes.py, and
writes to data/records/nhanes/:

  applicants.jsonl   one decoded record per included participant
  PROVENANCE.json    raw and cleaned hashes, counts per cycle, every exclusion
                     by reason, variables a cycle lacks, how often each rendered
                     field is "not stated", the strata cut points, ten-year
                     deaths per stratum, and the pandas cross-check of the reader

Offline and deterministic: the same raw files always give the same output hash.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import math
import os
import sys
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from grail.probe import nhanes  # noqa: E402
from grail.probe.records_table import score, stratify, tercile_cuts  # noqa: E402
from grail.probe.xport import read_xport  # noqa: E402

PACK_PATH = os.path.join(ROOT, "data", "stimuli", "life_insurance_nhanes", "pack.json")
ALTERNATES = {"ALQ100", "ALD100", "ALQ101"}       # one name per cycle, same question


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def pandas_check(path: str, mine: dict) -> tuple[int, int, str | None]:
    """Compare our reader with pandas on the same columns: (values, mismatches, note)."""
    try:
        import pandas as pd
    except ImportError:
        return 0, 0, "pandas not installed"
    df = pd.read_sas(path, format="xport")
    compared = mismatched = 0
    for col, values in mine.items():
        theirs = df[col].tolist()
        if len(theirs) != len(values):
            return compared, mismatched + 1, f"row count differs in {col}"
        for a, b in zip(values, theirs):
            compared += 1
            b_missing = b is None or (isinstance(b, float) and math.isnan(b))
            if a is None or b_missing:
                mismatched += (a is None) != b_missing
            elif isinstance(a, str) or isinstance(b, (str, bytes)):
                b = b.decode("latin-1").strip() if isinstance(b, bytes) else str(b).strip()
                mismatched += a != b
            elif abs(a - b) > 1e-9 * max(1.0, abs(a)):
                mismatched += 1
    return compared, mismatched, None


def load_cycle(raw: str, cycle: dict, report: dict, check: dict) -> tuple[dict, dict]:
    rows: dict = {}
    label = cycle["label"]
    for mod in nhanes.MODULES:
        path = os.path.join(raw, f"{mod}{cycle['suffix']}.xpt")
        if not os.path.exists(path):
            raise SystemExit(f"Missing {path}.\nRun python3 scripts/fetch_nhanes.py first.")
        x = read_xport(path, columns=nhanes.VARIABLES[mod])
        cols = x["columns"]
        wanted = set(nhanes.VARIABLES[mod]) - {"SEQN"}
        missing = sorted(wanted - set(cols))
        if mod == "ALQ" and ALTERNATES & set(cols):
            missing = [m for m in missing if m not in ALTERNATES]
        if missing:
            report["variables_not_in_cycle"].setdefault(label, {})[mod] = missing
        n, bad, note = pandas_check(path, cols)
        check["values_compared"] += n
        check["mismatches"] += bad
        if note:
            check["notes"].add(note)
        for i, s in enumerate(cols["SEQN"]):
            key = int(s)
            if mod == "DEMO":
                rows[key] = {}
            elif key not in rows:
                report["orphan_rows"][f"{mod}{cycle['suffix']}"] += 1
                continue
            for col, values in cols.items():
                rows[key][col] = values[i]

    mpath = os.path.join(raw, cycle["mortality"])
    if not os.path.exists(mpath):
        raise SystemExit(f"Missing {mpath}.\nRun python3 scripts/fetch_nhanes.py first.")
    mort = {}
    with open(mpath, encoding="latin-1") as fh:
        for line in fh:
            if line.strip():
                rec = nhanes.parse_mortality_line(line.rstrip("\r\n"))
                mort[rec["SEQN"]] = rec
    return rows, mort


def summarise(records: list, pack: dict | None) -> dict:
    n = len(records)
    out = {
        "n": n,
        "died_within_10y": sum(r["died_within_10y"] for r in records),
        "died_by_end_2019": sum(1 for r in records if r["died"]),
        "followup_months_median": sorted(r["followup_months"] for r in records)[n // 2] if n else None,
        "recorded_sex": dict(collections.Counter(r["recorded_sex"] for r in records)),
        "smoking_class": dict(collections.Counter(r["smoking_class"] for r in records)),
        "not_stated": {f: sum(1 for r in records if r[f] is None) for f in nhanes.RENDER_FIELDS},
        "with_any_condition": sum(1 for r in records
                                  if r["medical_history"] not in (None, "none reported")),
        "family_history_chd": dict(collections.Counter(r["family_history_chd"] for r in records)),
    }
    if pack and n >= 3:
        spec = pack["source"]["strength"]
        order = tuple(pack["stratum_order"])
        pools = stratify(tuple(records), spec, order)
        out["strata"] = {
            "score_tercile_cuts": list(tercile_cuts(tuple(records), spec)),
            "per_stratum": {
                name: {"n": len(pool),
                       "died_within_10y": sum(r["died_within_10y"] for r in pool),
                       "rate": round(sum(r["died_within_10y"] for r in pool) / len(pool), 4)
                       if pool else None,
                       "mean_score": round(sum(score(r, spec) for r in pool) / len(pool), 3)
                       if pool else None}
                for name, pool in pools.items()},
            "note": "Descriptive check that the face-valid score orders risk as intended. "
                    "The score was fixed in the pack before these data were imported and "
                    "is not tuned on the outcome."}
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--raw", default=os.path.join(ROOT, "data", "records", "nhanes", "raw"))
    ap.add_argument("--out", default=os.path.join(ROOT, "data", "records", "nhanes"))
    ap.add_argument("--pack", default=PACK_PATH)
    args = ap.parse_args()

    report = {"variables_not_in_cycle": {}, "orphan_rows": collections.Counter()}
    check = {"values_compared": 0, "mismatches": 0, "notes": set()}
    records, exclusions, per_cycle = [], collections.Counter(), {}
    fam_codes = collections.Counter()

    for cycle in nhanes.CYCLES:
        rows, mort = load_cycle(args.raw, cycle, report, check)
        kept = 0
        for seqn in sorted(rows):
            r = rows[seqn]
            m = mort.get(seqn)
            why = nhanes.exclusion(r, m)
            if why:
                exclusions[why] += 1
                continue
            records.append(nhanes.decode(r, m, cycle["label"]))
            kept += 1
            for v in ("MCQ250G", "MCQ260GA", "MCQ260GB", "MCQ260GG", "MCQ260GH", "MCQ260GI"):
                if r.get(v) is not None:
                    fam_codes[f"{v}={int(r[v])}"] += 1
        per_cycle[cycle["label"]] = {"participants": len(rows), "included": kept,
                                     "mortality_records": len(mort)}

    os.makedirs(args.out, exist_ok=True)
    out_path = os.path.join(args.out, "applicants.jsonl")
    with open(out_path, "w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n")

    pack = None
    if os.path.exists(args.pack):
        with open(args.pack, encoding="utf-8") as fh:
            pack = json.load(fh)

    manifest = {}
    mpath = os.path.join(args.raw, "MANIFEST.json")
    if os.path.exists(mpath):
        with open(mpath, encoding="utf-8") as fh:
            manifest = json.load(fh)

    prov = {
        **nhanes.SOURCE,
        "imported_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "raw_sha256": {name: sha256(os.path.join(args.raw, name))
                       for name in sorted(os.listdir(args.raw))
                       if name.endswith((".xpt", ".dat"))},
        "raw_urls": {k: v.get("url") for k, v in sorted(manifest.get("files", {}).items())},
        "cleaned_sha256": {"applicants.jsonl": sha256(out_path)},
        "inclusion": {
            "age": f"{nhanes.AGE_RANGE[0]}-{nhanes.AGE_RANGE[1]} at screening (RIDAGEYR)",
            "pregnant_excluded": "RIDEXPRG = 1",
            "bmi": "examination BMI present (BMXBMI)",
            "mortality": "ELIGSTAT = 1 and follow-up from the examination (PERMTH_EXM) present",
            "outcome": f"died_within_10y = MORTSTAT 1 and PERMTH_EXM <= {nhanes.HORIZON_MONTHS}"},
        "per_cycle": per_cycle,
        "excluded": dict(sorted(exclusions.items())),
        "variables_not_in_cycle": report["variables_not_in_cycle"],
        "orphan_rows": dict(report["orphan_rows"]),
        "family_history_codes": dict(sorted(fam_codes.items())),
        "summary": summarise(records, pack),
        "reader_check": {
            "against": "pandas.read_sas(format='xport')",
            "values_compared": check["values_compared"],
            "mismatches": check["mismatches"],
            "notes": sorted(check["notes"])},
        "fields": {"rendered": list(nhanes.RENDER_FIELDS), "scored": list(nhanes.SCORE_FIELDS),
                   "redacted": list(nhanes.REDACTED), "outcomes": list(nhanes.OUTCOMES)},
        "note": "Real survey participants; public-use data. The recorded sex is never "
                "rendered, the outcome is never rendered, and the dataset identifier never "
                "reaches a prompt (the application number is a hash of it). The public-use "
                "mortality file perturbs some dates and causes of death to protect "
                "confidentiality (NCHS); counts here are therefore close to, not exactly, "
                "the restricted-use figures.",
    }
    with open(os.path.join(args.out, "PROVENANCE.json"), "w", encoding="utf-8") as fh:
        json.dump(prov, fh, indent=2, ensure_ascii=False)

    s = prov["summary"]
    cycles = ", ".join("{}: {:,}".format(k, v["included"]) for k, v in per_cycle.items())
    print(f"Included {s['n']:,} participants ({cycles})")
    print(f"  died within 10 years: {s['died_within_10y']:,}; by end of 2019: {s['died_by_end_2019']:,}")
    for why, k in sorted(exclusions.items(), key=lambda kv: -kv[1]):
        print(f"  excluded, {why}: {k:,}")
    if report["variables_not_in_cycle"]:
        print(f"  variables a cycle lacks: {report['variables_not_in_cycle']}")
    print(f"  'not stated': {s['not_stated']}")
    if "strata" in s:
        for name, d in s["strata"]["per_stratum"].items():
            print(f"  stratum {name:<10} n={d['n']:>6,}  10-year deaths {d['died_within_10y']:>4} ({d['rate']:.1%})")
    rc = prov["reader_check"]
    print(f"  reader vs pandas: {rc['values_compared']:,} values, {rc['mismatches']} mismatches"
          + (f" ({'; '.join(rc['notes'])})" if rc["notes"] else ""))
    print(f"-> {out_path}")


if __name__ == "__main__":
    main()
