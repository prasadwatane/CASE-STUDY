"""The response log — append-only, hash-chained, and cached.

Model responses are the only expensive thing in this pipeline and the only thing
that cannot be regenerated: probes come back from a seed, golds come back from a
formula, but a response is a purchase. So the log is treated as evidence rather
than as a cache file that happens to persist.

* **Append-only and hash-chained**, with a `.head` anchor, same construction as
  the gold ledger — edits, reordering and truncation are all detectable.
* **Keyed by (probe content hash, model id, params hash)**, so re-running skips
  what is already paid for and a changed probe or a changed temperature is a
  different record rather than a silent overwrite.
* **Raw text always retained.** Parsing happens downstream and can be redone
  without spending anything.

The probe hash rather than the probe id is what keys a record. If a probe is
regenerated with different content under the same id, its old responses no longer
match it, which is the behaviour you want: they were answers to a different
question.
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

GENESIS = "0" * 64


@dataclass
class ResponseRecord:
    probe_id: str
    probe_sha256: str            # keyed on content, not id
    domain: str
    dimension: str
    model_id: str
    params_hash: str
    params: dict
    response: str                # raw, always
    run_id: str
    latency_ms: int = 0
    error: str = ""
    created_utc: str = ""
    prev_sha256: str = GENESIS
    sha256: str = ""

    def __post_init__(self) -> None:
        if not self.created_utc:
            self.created_utc = datetime.now(timezone.utc).isoformat(timespec="seconds")

    def key(self) -> tuple[str, str, str]:
        return (self.probe_sha256, self.model_id, self.params_hash)

    def payload(self) -> dict:
        d = asdict(self)
        d.pop("sha256", None)
        return d

    def compute_hash(self) -> str:
        body = json.dumps(self.payload(), ensure_ascii=False, sort_keys=True,
                          separators=(",", ":"))
        return hashlib.sha256((self.prev_sha256 + body).encode("utf-8")).hexdigest()

    def seal(self, prev: str) -> "ResponseRecord":
        self.prev_sha256 = prev
        self.sha256 = self.compute_hash()
        return self

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)

    @staticmethod
    def from_json(line: str) -> "ResponseRecord":
        return ResponseRecord(**json.loads(line))


def verify_chain(records: list[ResponseRecord]) -> tuple[bool, str]:
    prev = GENESIS
    for i, rec in enumerate(records):
        if rec.prev_sha256 != prev:
            return False, (f"response log broken at row {i} ({rec.probe_id}): "
                           "a row was edited, removed or reordered")
        if rec.compute_hash() != rec.sha256:
            return False, (f"response log broken at row {i} ({rec.probe_id}): "
                           "content no longer matches its hash")
        prev = rec.sha256
    return True, f"{len(records)} responses, chain intact"


def head_path(path: str) -> str:
    return path + ".head"


def load(path: str) -> list[ResponseRecord]:
    if not os.path.exists(path):
        return []
    out = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                out.append(ResponseRecord.from_json(line))
    return out


def _write_head(path: str, records: list[ResponseRecord]) -> None:
    with open(head_path(path), "w", encoding="utf-8") as fh:
        json.dump({"n_records": len(records),
                   "head_sha256": records[-1].sha256 if records else GENESIS},
                  fh, indent=2)


def append(path: str, records: list[ResponseRecord]) -> list[ResponseRecord]:
    """Append, continuing the chain. Refuses to write onto a damaged log."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    existing = load(path)
    if existing:
        ok, reason = verify_chain(existing)
        if not ok:
            raise SystemExit(f"RESPONSE LOG: refusing to append — {reason}")
        if os.path.exists(head_path(path)):
            with open(head_path(path), encoding="utf-8") as fh:
                anchor = json.load(fh)
            if (anchor["head_sha256"] != existing[-1].sha256
                    or anchor["n_records"] != len(existing)):
                raise SystemExit(
                    "RESPONSE LOG: refusing to append — the log no longer matches "
                    f"its anchor (expected {anchor['n_records']} records, found "
                    f"{len(existing)}). Rows were removed from the end.")

    prev = existing[-1].sha256 if existing else GENESIS
    for rec in records:
        rec.seal(prev)
        prev = rec.sha256
    combined = existing + records
    with open(path, "w", encoding="utf-8") as fh:
        for rec in combined:
            fh.write(rec.to_json() + "\n")
    _write_head(path, combined)
    return combined


def cached_keys(records: list[ResponseRecord]) -> set:
    """What has already been paid for."""
    return {r.key() for r in records if not r.error}
