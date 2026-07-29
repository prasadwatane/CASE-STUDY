"""Gold records and the append-only ledger.

Every gold is stamped with how it was obtained, and there are only three
honest outcomes:

* **green** — obtained without trusting a model: computed by a solver whose
  formula and arguments are recorded, or extracted from a primary source with a
  locator a human signed off. Reproducible by hand.
* **amber** — proposed by a model and accepted by the conformal gate, carrying
  alpha, the certified error bound, the threshold and the raw proposals.
* **escalated** — the gate could not accept it. There is no gold yet, and the
  item is queued for a human. This is a normal outcome, not a failure.

There is deliberately no fourth status for "looks right". A record with no
provenance cannot be written.

The ledger is append-only and hash-chained: each record hashes its own content
together with the previous record's hash, so deleting, editing or reordering any
row breaks every hash after it. `verify_chain` is what makes the gold set
evidence rather than a file someone could have edited.
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

GREEN = "green"
AMBER = "amber"
ESCALATED = "escalated"

ROUTE_COMPUTED = "computed"
ROUTE_SOURCED = "sourced"
ROUTE_STRUCTURAL = "structural"

GENESIS = "0" * 64


@dataclass
class GoldRecord:
    item_id: str                 # the seed item / probe pair this gold answers
    domain: str
    dimension: str
    route: str                   # computed | sourced | structural
    status: str                  # green | amber | escalated
    answer: str | None           # None while escalated
    answer_kind: str             # value | behaviour | none
    provenance: dict             # always says how the answer was obtained
    probe_ids: list[str] = field(default_factory=list)
    proposals: list[str] = field(default_factory=list)
    agreement: float | None = None
    nonconformity: float | None = None
    threshold: float | None = None
    alpha: float | None = None
    error_bound: float | None = None
    escalation_reason: str = ""
    created_utc: str = ""
    prev_sha256: str = GENESIS
    sha256: str = ""

    def __post_init__(self) -> None:
        if self.status in (GREEN, AMBER) and not self.provenance:
            raise ValueError(
                f"gold {self.item_id} has status '{self.status}' with no provenance — "
                "a gold that cannot say where it came from is exactly the "
                "'trust me' gold the design rules out")
        if not self.created_utc:
            self.created_utc = datetime.now(timezone.utc).isoformat(timespec="seconds")

    def payload(self) -> dict:
        d = asdict(self)
        d.pop("sha256", None)
        return d

    def compute_hash(self) -> str:
        body = json.dumps(self.payload(), ensure_ascii=False, sort_keys=True,
                          separators=(",", ":"))
        return hashlib.sha256((self.prev_sha256 + body).encode("utf-8")).hexdigest()

    def seal(self, prev_sha256: str) -> "GoldRecord":
        self.prev_sha256 = prev_sha256
        self.sha256 = self.compute_hash()
        return self

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)

    @staticmethod
    def from_json(line: str) -> "GoldRecord":
        return GoldRecord(**json.loads(line))


def seal_chain(records: list[GoldRecord]) -> list[GoldRecord]:
    prev = GENESIS
    for rec in records:
        rec.seal(prev)
        prev = rec.sha256
    return records


def verify_chain(records: list[GoldRecord]) -> tuple[bool, str]:
    """(ok, reason). Detects any edit, deletion or reordering of the ledger."""
    prev = GENESIS
    for i, rec in enumerate(records):
        if rec.prev_sha256 != prev:
            return False, (f"ledger broken at row {i} ({rec.item_id}): expected "
                           f"previous hash {prev[:12]}…, found {rec.prev_sha256[:12]}… "
                           "— a row was edited, removed or reordered")
        if rec.compute_hash() != rec.sha256:
            return False, (f"ledger broken at row {i} ({rec.item_id}): content no "
                           "longer matches its hash")
        prev = rec.sha256
    return True, f"{len(records)} records, chain intact"


def head_path(path: str) -> str:
    return path + ".head"


def _write_head(path: str, records: list[GoldRecord]) -> None:
    """Anchor the ledger's tail outside the ledger itself.

    A hash chain detects edits and reordering, but not truncation: lopping rows
    off the end leaves a shorter chain that still verifies. Recording the head
    hash and row count separately is what closes that hole, so a ledger that has
    been shortened is detected on the next append.
    """
    with open(head_path(path), "w", encoding="utf-8") as fh:
        json.dump({"n_records": len(records),
                   "head_sha256": records[-1].sha256 if records else GENESIS},
                  fh, indent=2)


def save_ledger(records: list[GoldRecord], path: str, report: dict | None = None) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(rec.to_json() + "\n")
    _write_head(path, records)
    if report is not None:
        with open(os.path.join(os.path.dirname(path), "gold_report.json"), "w",
                  encoding="utf-8") as fh:
            json.dump(report, fh, ensure_ascii=False, indent=2)


def load_ledger(path: str) -> list[GoldRecord]:
    out = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                out.append(GoldRecord.from_json(line))
    return out


def append_ledger(path: str, records: list[GoldRecord]) -> list[GoldRecord]:
    """Append to an existing ledger, continuing its hash chain.

    Appending is the only permitted mutation. A human resolving an escalation
    adds a row; the earlier row stays, so the history of a gold is visible.
    """
    existing = load_ledger(path) if os.path.exists(path) else []
    ok, reason = (verify_chain(existing) if existing else (True, ""))
    if not ok:
        raise SystemExit(f"LEDGER: refusing to append — {reason}")

    if os.path.exists(head_path(path)):
        with open(head_path(path), encoding="utf-8") as fh:
            anchor = json.load(fh)
        actual = existing[-1].sha256 if existing else GENESIS
        if anchor["head_sha256"] != actual or anchor["n_records"] != len(existing):
            raise SystemExit(
                "LEDGER: refusing to append — the ledger no longer matches its "
                f"anchor (expected {anchor['n_records']} records ending "
                f"{anchor['head_sha256'][:12]}…, found {len(existing)} ending "
                f"{actual[:12]}…). Rows were removed from the end.")

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
