"""Download the NHANES files the life-insurance records are built from.

Run once, on a machine with internet access, from the grail-audit folder:

    python3 scripts/fetch_nhanes.py            # download what is missing
    python3 scripts/fetch_nhanes.py --verify   # re-hash and compare with the manifest
    python3 scripts/fetch_nhanes.py --force    # download everything again

What it fetches (about 40 MB, public domain, NCHS):

* 21 SAS transport files: DEMO, BMX, SMQ, MCQ, BPQ, DIQ, ALQ for the three
  survey cycles 1999-2000, 2001-2002 and 2003-2004;
* 3 public-use Linked Mortality Files (follow-up to 31 Dec 2019), one per cycle.

Files land in data/records/nhanes/raw/ with MANIFEST.json (URL, size, SHA-256,
time). Nothing is decoded here; scripts/import_nhanes.py does that and can be
re-run offline as often as needed.

Standard library only. It uses curl when available (it is on every Mac and
uses the system certificates) and falls back to urllib. Each XPT file is
checked for the SAS transport header and each mortality file for its fixed-width
layout, so a web page served in place of a data file is caught here.

By downloading you accept the NCHS data-use restrictions: statistical analysis
only, no attempt to identify anyone, no linkage to identifiable data.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from grail.probe.nhanes import CYCLES, MODULES  # noqa: E402

RAW = os.path.join(ROOT, "data", "records", "nhanes", "raw")
XPT_MAGIC = b"HEADER RECORD*******LIBRARY HEADER RECORD!!!!!!!"
MORT_BASE = "https://ftp.cdc.gov/pub/Health_Statistics/NCHS/datalinkage/linked_mortality/"


def targets() -> list[dict]:
    out = []
    for c in CYCLES:
        for mod in MODULES:
            name = f"{mod}{c['suffix']}"
            out.append({
                "file": f"{name}.xpt", "kind": "xpt", "cycle": c["label"], "module": mod,
                "urls": [
                    f"https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/{c['start']}/DataFiles/{name}.xpt",
                    f"https://wwwn.cdc.gov/Nchs/Nhanes/{c['label']}/{name}.XPT",
                ]})
        out.append({"file": c["mortality"], "kind": "mortality", "cycle": c["label"],
                    "module": "MORT", "urls": [MORT_BASE + c["mortality"]]})
    return out


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def looks_right(path: str, kind: str) -> str | None:
    """None if the file looks like what it should be, else the reason it does not."""
    with open(path, "rb") as fh:
        head = fh.read(4096)
    if kind == "xpt":
        return None if head.startswith(XPT_MAGIC) else "not a SAS transport file"
    first = head.split(b"\n", 1)[0].rstrip(b"\r")
    # SEQN in columns 1-6, ELIGSTAT (a digit) in column 15
    if len(first) < 16 or not first[:6].strip().isdigit() or not first[14:15].isdigit():
        return "not the fixed-width mortality layout"
    return None


def download(url: str, dest: str) -> str | None:
    """Fetch url to dest. Returns None on success, else an error message."""
    tmp = dest + ".part"
    if shutil.which("curl"):
        cmd = ["curl", "-fsSL", "--retry", "3", "--connect-timeout", "30",
               "-A", "grail-audit/1.0 (research; NHANES public-use download)",
               "-o", tmp, url]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode == 0:
            os.replace(tmp, dest)
            return None
        err = f"curl exit {res.returncode}: {res.stderr.strip()[:200]}"
    else:
        err = "curl not found"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "grail-audit/1.0"})
        with urllib.request.urlopen(req, timeout=120) as resp, open(tmp, "wb") as fh:
            shutil.copyfileobj(resp, fh)
        os.replace(tmp, dest)
        return None
    except Exception as exc:                      # noqa: BLE001 — report, then try the next URL
        if os.path.exists(tmp):
            os.remove(tmp)
        return f"{err}; urllib: {exc}"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--verify", action="store_true", help="re-hash files against MANIFEST.json")
    ap.add_argument("--force", action="store_true", help="download even if present")
    args = ap.parse_args()

    os.makedirs(RAW, exist_ok=True)
    manifest_path = os.path.join(RAW, "MANIFEST.json")
    manifest = {}
    if os.path.exists(manifest_path):
        with open(manifest_path, encoding="utf-8") as fh:
            manifest = json.load(fh)
    files = manifest.setdefault("files", {})

    if args.verify:
        bad = 0
        for t in targets():
            path = os.path.join(RAW, t["file"])
            rec = files.get(t["file"])
            ok = rec and os.path.exists(path) and sha256(path) == rec["sha256"]
            bad += not ok
            print(("ok       " if ok else "MISMATCH ") + t["file"])
        raise SystemExit(1 if bad else 0)

    failed = []
    for t in targets():
        path = os.path.join(RAW, t["file"])
        if os.path.exists(path) and not args.force and looks_right(path, t["kind"]) is None:
            print(f"have     {t['file']}")
            continue
        errors = []
        for url in t["urls"]:
            err = download(url, path)
            if err is None:
                err = looks_right(path, t["kind"])
                if err:
                    os.remove(path)
            if err is None:
                files[t["file"]] = {
                    "url": url, "cycle": t["cycle"], "module": t["module"],
                    "bytes": os.path.getsize(path), "sha256": sha256(path),
                    "fetched_utc": datetime.now(timezone.utc).isoformat(timespec="seconds")}
                print(f"fetched  {t['file']:<44} {files[t['file']]['bytes']:>10,} bytes")
                break
            errors.append(f"{url}: {err}")
        else:
            failed.append((t["file"], errors))
            print(f"FAILED   {t['file']}")

    manifest.update({
        "dataset": "NHANES 1999-2004 + NCHS 2019 Public-Use Linked Mortality Files",
        "note": "Raw files exactly as served by NCHS. Decoded by scripts/import_nhanes.py.",
        "data_use": "NCHS data-use restrictions apply: statistical analysis only, no attempt "
                    "to identify any person, no linkage to identifiable data."})
    with open(manifest_path, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2, sort_keys=True)

    if failed:
        print("\nSome files could not be fetched:")
        for name, errors in failed:
            print(f"  {name}")
            for e in errors:
                print(f"     {e}")
        print("\nIf a URL has moved, download the file in a browser from the NHANES page "
              "for that cycle and save it under data/records/nhanes/raw/ with the name above.")
        raise SystemExit(1)
    print(f"\nAll {len(targets())} files are in data/records/nhanes/raw/.")
    print("Next: python3 scripts/import_nhanes.py")


if __name__ == "__main__":
    main()
