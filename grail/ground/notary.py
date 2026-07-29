"""The notary gate — the trust root of the whole audit.

A human reviews the derived checklist and SIGNS it. Signing records the signer,
a timestamp, and a SHA-256 over the checklist content. Freezing means: if a
single character of any requirement/clause later changes, the recomputed hash no
longer matches the signature, and `verify` fails.

`require_signed` is the enforcement point: no audit stage may run on a checklist
that is unsigned or whose content no longer matches its signature. This is what
keeps the most-automated component (auto-derivation) from being trusted blindly —
a human is the certified root, and tampering is detectable.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import hashlib
import json

from grail.ground.checklist import Checklist


def content_hash(checklist: Checklist) -> str:
    """Stable SHA-256 over the checklist items (signature fields excluded)."""
    payload = json.dumps(
        {"domain": checklist.domain,
         "instrument": checklist.instrument,
         "items": [i.as_dict() for i in checklist.items]},
        ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass
class Signature:
    signer: str
    signed_utc: str
    content_sha256: str
    note: str = ""


def sign(checklist: Checklist, signer: str, note: str = "") -> dict:
    """Return a frozen, signed document (checklist + signature)."""
    sig = Signature(
        signer=signer,
        signed_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        content_sha256=content_hash(checklist),
        note=note,
    )
    return {"checklist": checklist.as_dict(), "signature": asdict(sig)}


def save_signed(signed: dict, path: str) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(signed, fh, ensure_ascii=False, indent=2)


def load_signed(path: str) -> dict:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def verify(signed: dict) -> tuple[bool, str]:
    """(ok, reason). ok is False if unsigned or content no longer matches."""
    sig = signed.get("signature")
    if not sig or not sig.get("content_sha256") or not sig.get("signer"):
        return False, "checklist is not signed"
    c = Checklist(
        signed["checklist"]["domain"],
        signed["checklist"]["instrument"],
        signed["checklist"]["created_utc"],
    )
    from grail.ground.checklist import ChecklistItem
    c.items = [ChecklistItem(**it) for it in signed["checklist"]["items"]]
    recomputed = content_hash(c)
    if recomputed != sig["content_sha256"]:
        return False, ("content changed since signing "
                       f"(signed {sig['content_sha256'][:12]}…, "
                       f"now {recomputed[:12]}…) — re-sign required")
    return True, f"signed by {sig['signer']} at {sig['signed_utc']}"


def require_signed(path: str) -> dict:
    """Enforcement gate. Raise SystemExit unless the checklist is validly signed.

    Every downstream audit stage should call this before running.
    """
    try:
        signed = load_signed(path)
    except FileNotFoundError:
        raise SystemExit(
            f"NOTARY GATE: no signed checklist at {path}. "
            "Derive one (scripts/derive_checklist.py), review it, then sign it "
            "(scripts/sign_checklist.py). No audit runs on an unsigned checklist.")
    ok, reason = verify(signed)
    if not ok:
        raise SystemExit(f"NOTARY GATE: refused — {reason}.")
    return signed
