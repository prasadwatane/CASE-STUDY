"""Why did the judge's quotations fail to ground? Read the evidence, don't guess.

A high ungrounded count has two very different causes and they need opposite
responses:

  the judge invented support          -> the judge is unusable, say so
  the matcher rejected real support   -> the matcher is wrong, fix it

Telling them apart is a matter of looking at the near-misses. A quotation that
matches the response after stripping markdown, or after folding unicode
punctuation, was FOUND by the judge and LOST by the code. A quotation that
matches nothing under any normalisation was composed.

    python scripts/diagnose_judge.py finance --model Qwen/Qwen2.5-7B-Instruct

Prints a breakdown by cause and a sample of each, so the fix is chosen from
evidence rather than from a plausible story about what models do.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import unicodedata
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import PROBE_DIR, RUN_DIR
from grail.judge import checks
from grail.probe.schema import load_probes
from grail.run.store import load

# Progressively more forgiving normalisations. The FIRST one that makes a quote
# match names the cause, so order matters: least forgiving first.
PUNCT = {"‘": "'", "’": "'", "“": '"', "”": '"',
         "–": "-", "—": "-", "…": "...", " ": " "}


def fold_punct(s: str) -> str:
    for a, b in PUNCT.items():
        s = s.replace(a, b)
    return unicodedata.normalize("NFKC", s)


def strip_markdown(s: str) -> str:
    s = re.sub(r"\*\*|__|\*|_|`|#+\s*", "", s)
    return re.sub(r"^\s*[-+*]\s+", "", s, flags=re.M)


def alnum(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", s.lower())


LADDER = [
    ("exact (current matcher)", lambda s: " ".join(s.split()).lower()),
    ("unicode punctuation", lambda s: " ".join(fold_punct(s).split()).lower()),
    ("markdown stripped", lambda s: " ".join(strip_markdown(fold_punct(s)).split()).lower()),
    ("alphanumeric only", alnum),
]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("domain", nargs="?", default="finance")
    ap.add_argument("--model", required=True)
    ap.add_argument("--show", type=int, default=4, help="examples per cause")
    args = ap.parse_args()

    run_dir = os.path.join(RUN_DIR, args.domain)
    path = os.path.join(run_dir, f"judge_{args.model.replace('/', '_')}.json")
    verdicts = json.load(open(path, encoding="utf-8"))

    records = load(os.path.join(run_dir, "responses.jsonl"))
    probes = load_probes(os.path.join(PROBE_DIR, args.domain, "probes.jsonl"))
    by_hash = {p.content_sha256: p for p in probes}
    by_probe = {by_hash[r.probe_sha256].id: r
                for r in records
                if r.model_id == args.model and not r.error
                and r.probe_sha256 in by_hash}

    # --- why are conditions undecided? -------------------------------------
    undecided = Counter()
    for item in verdicts["items"]:
        if item["adequate"] is not None:
            continue
        for c in item["conditions"]:
            if c["answer"] == "cannot_tell":
                undecided[c["key"]] += 1

    print(f"items          : {len(verdicts['items'])}")
    print(f"undecided by condition:")
    for key, n in undecided.most_common():
        print(f"  {key:<20} {n}")

    # --- the deterministic layer: is it settling things wrongly? -----------
    contradicts = [i for i in verdicts["items"]
                   if i["deterministic"].get("contradicts")]
    print(f"\nflagged as contradicting the application : {len(contradicts)}")
    if contradicts:
        nums = Counter(n for i in contradicts
                       for n in i["deterministic"]["invented_numbers"])
        print("  most common 'invented' numbers:",
              ", ".join(f"{n} x{c}" for n, c in nums.most_common(8)))
        print("  -> if these look like fragments of real amounts (300 from")
        print("     '6,300'), the comma bug is firing and this is a false flag.")

    # --- where on the ladder does each failing quote land? ------------------
    causes = Counter()
    samples: dict[str, list] = {}
    for item in verdicts["items"]:
        rec = by_probe.get(item["probe_id"])
        if rec is None:
            continue
        response = rec.response
        for c in item["conditions"]:
            quote = c.get("quote", "")
            if not quote or c.get("settled_in_code"):
                continue
            if checks.quote_is_grounded(quote, response):
                continue
            cause = "not found under ANY normalisation"
            for label, norm in LADDER:
                if norm(quote) and norm(quote) in norm(response):
                    cause = f"recoverable: {label}"
                    break
            causes[cause] += 1
            samples.setdefault(cause, []).append((item["probe_id"], quote))

    print("\n=== ungrounded quotes, by cause ===")
    total = sum(causes.values())
    for cause, n in causes.most_common():
        print(f"  {n:>5}  ({n/total:.0%})  {cause}")
        for pid, q in samples[cause][:args.show]:
            print(f"           {pid}: {q[:110]!r}")

    print(f"\n{total} failing quotes examined.")
    print("Recoverable ones were FOUND by the judge and LOST by the matcher —")
    print("that is a code fix. Ones found under no normalisation were composed —")
    print("that is a judge finding, and belongs in the report.")


if __name__ == "__main__":
    main()
