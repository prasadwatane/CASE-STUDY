"""Sign and FREEZE a reviewed draft checklist (the notary gate).

Signing hashes the exact content the human approved. Any later edit breaks the
signature, so the frozen file is tamper-evident. Downstream audit stages call
grail.ground.notary.require_signed() and refuse to run without a valid signature.

Run:  python scripts/sign_checklist.py finance "Prasad Watane"
Verify later:  python scripts/sign_checklist.py finance --verify
"""
from __future__ import annotations
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import CHECKLIST_DIR
from grail.ground.checklist import Checklist
from grail.ground.notary import sign, save_signed, load_signed, verify


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("usage: sign_checklist.py <domain> <signer> | <domain> --verify")
    domain = sys.argv[1]
    draft = os.path.join(CHECKLIST_DIR, f"{domain}_draft.json")
    signed_path = os.path.join(CHECKLIST_DIR, f"{domain}_signed.json")

    if len(sys.argv) >= 3 and sys.argv[2] == "--verify":
        ok, reason = verify(load_signed(signed_path))
        print(("VALID: " if ok else "INVALID: ") + reason)
        raise SystemExit(0 if ok else 1)

    signer = sys.argv[2] if len(sys.argv) > 2 else ""
    if not signer:
        raise SystemExit("Provide a signer name: sign_checklist.py finance \"Your Name\"")
    if not os.path.exists(draft):
        raise SystemExit(f"No draft at {draft}. Run derive_checklist.py {domain} first.")

    checklist = Checklist.load(draft)
    signed = sign(checklist, signer, note="notary gate — reviewed and frozen")
    save_signed(signed, signed_path)
    print(f"SIGNED and FROZEN -> {signed_path}")
    print(f"  signer: {signer}")
    print(f"  sha256: {signed['signature']['content_sha256'][:16]}…")
    print(f"  {len(checklist.items)} requirements frozen. Audits may now run on this checklist.")


if __name__ == "__main__":
    main()
