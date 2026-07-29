import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from grail.ground.checklist import Checklist, ChecklistItem
from grail.ground.notary import sign, verify, require_signed, save_signed


def _checklist():
    c = Checklist("finance", "EU AI Act", "2026-01-01T00:00:00+00:00")
    c.items = [
        ChecklistItem("AIA:Art10(2)(f)", "Article 10(2)(f)", "hybrid", "fairness",
                      "examine biases ...", "The system shall ...", ""),
        ChecklistItem("AIA:Art15(1)", "Article 15(1)", "behavioral", "robustness",
                      "accuracy robustness ...", "The system shall ...", ""),
    ]
    return c


def test_sign_then_verify_ok():
    signed = sign(_checklist(), "Tester")
    ok, reason = verify(signed)
    assert ok, reason


def test_tamper_breaks_signature():
    signed = sign(_checklist(), "Tester")
    # someone edits a requirement after signing
    signed["checklist"]["items"][0]["requirement"] = "TAMPERED"
    ok, reason = verify(signed)
    assert not ok
    assert "content changed" in reason


def test_unsigned_is_rejected():
    signed = {"checklist": _checklist().as_dict(), "signature": None}
    ok, reason = verify(signed)
    assert not ok
    assert "not signed" in reason


def test_require_signed_enforces(tmp_path):
    p = tmp_path / "finance_signed.json"
    save_signed(sign(_checklist(), "Tester"), str(p))
    doc = require_signed(str(p))          # valid -> returns doc
    assert doc["signature"]["signer"] == "Tester"

    # tamper on disk -> enforcement must refuse
    import json
    d = json.loads(p.read_text())
    d["checklist"]["items"][0]["clause_text"] = "altered"
    p.write_text(json.dumps(d))
    with pytest.raises(SystemExit):
        require_signed(str(p))


def test_require_signed_missing_file(tmp_path):
    with pytest.raises(SystemExit):
        require_signed(str(tmp_path / "nope.json"))


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn) and "tmp_path" not in fn.__code__.co_varnames:
            fn(); print("ok", name)
