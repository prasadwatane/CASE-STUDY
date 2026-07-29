"""Generate the CORE probe set for a domain from its SIGNED checklist.

The notary gate runs first: without a valid signature nothing is generated.
Output is written to data/processed/probes/<domain>/ as probes.jsonl plus a
manifest recording the seed, the generator version, the checklist signature and a
content hash. Probes are immutable — regenerating an identical set is fine, but
overwriting a different one requires --force.

Run:
    python scripts/generate_probes.py finance
    python scripts/generate_probes.py finance --seed 123 --only fairness
    python scripts/generate_probes.py finance --verify
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import CHECKLIST_DIR, PROBE_CORE_N, PROBE_DIR, PROBE_SEED
from grail.probe.generate import generate_probeset
from grail.probe.schema import save_probeset


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("domain", nargs="?", default="finance")
    ap.add_argument("--seed", type=int, default=PROBE_SEED)
    ap.add_argument("--only", nargs="*", default=None,
                    help="restrict to these dimensions")
    ap.add_argument("--out", default=None)
    ap.add_argument("--force", action="store_true",
                    help="re-freeze over an existing, different probe set")
    ap.add_argument("--verify", action="store_true",
                    help="regenerate and check the content hash still matches")
    args = ap.parse_args()

    signed_path = os.path.join(CHECKLIST_DIR, f"{args.domain}_signed.json")
    out_dir = args.out or os.path.join(PROBE_DIR, args.domain)

    ps, notes = generate_probeset(signed_path, seed=args.seed, only=args.only)

    if args.verify:
        manifest_path = os.path.join(out_dir, "manifest.json")
        if not os.path.exists(manifest_path):
            raise SystemExit(f"No probe set at {out_dir} to verify.")
        with open(manifest_path, encoding="utf-8") as fh:
            on_disk = json.load(fh)
        now = ps.content_hash()
        ok = on_disk.get("content_sha256") == now
        print(("VALID: " if ok else "INVALID: ")
              + f"regenerated {now[:16]}… vs on disk "
                f"{str(on_disk.get('content_sha256'))[:16]}…")
        raise SystemExit(0 if ok else 1)

    manifest = save_probeset(ps, out_dir, targets=PROBE_CORE_N, notes=notes,
                             force=args.force)

    print(f"Probe set -> {out_dir}")
    print(f"  domain      : {manifest['domain']}")
    print(f"  checklist   : signed by {manifest['checklist_signer']} "
          f"({manifest['checklist_sha256'][:12]}…)")
    print(f"  generator   : {manifest['generator_version']}  seed {manifest['seed']}")
    print(f"  probes      : {manifest['n_probes']}")
    print(f"  content hash: {manifest['content_sha256'][:16]}…")
    for dim, c in sorted(manifest["counts"].items()):
        fams = ", ".join(f"{k}={v}" for k, v in sorted(c["families"].items()))
        print(f"    • {dim:<13} {c['total']:>5} prompts / {c['cases']:>4} cases  ({fams})")
    if manifest["underpowered"]:
        print("  UNDERPOWERED:")
        for dim, d in manifest["underpowered"].items():
            print(f"    • {dim}: {d['actual_cases']} cases, target {d['target']}")
    if notes:
        print("  notes:")
        for n in notes:
            print(f"    - {n}")


if __name__ == "__main__":
    main()
