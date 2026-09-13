"""The audit ledger — append-only, hash-chained, and refuses untraceable findings.

A number becomes audit evidence when someone else can say where it came from and
what it is allowed to support. Three facts do that work, and this module refuses
an entry that is missing any of them:

**Which obligation.** Every entry names at least one clause of the Act. A
measurement with no clause is a benchmark score: possibly interesting, not a
finding about conformity. This is the invariant that stops the audit drifting
into general model evaluation, and it is enforced at write time because a
convention that is merely documented gets broken the first week someone is busy.

**What kind of evidence.** `deterministic` means arithmetic over counts — no
model was consulted and the number is reproducible from the log. `judged` means
a language model read something, and carries the judge's identity and the
validation state of that judge. `human` means a person labelled it. These are
not interchangeable and the report must not present them as though they were, so
the distinction is carried rather than inferred.

**What kind of sample.** `core` is the pre-registered sample that headline
statistics are computed on. `control` is an instrument check — a planted effect
that the method must detect, or a null that it must not. `adaptive` is anything
added after seeing data. Only `core` may support a headline claim; the other two
exist so that the report can say how the instrument behaved without letting
instrument behaviour leak into the result.

**Append-only and hash-chained**, same construction as the response log: each
entry carries the hash of the one before it, so a deleted or reordered or
quietly-edited finding is detectable. An audit whose findings can be revised
without trace is not an audit, and the discipline matters most precisely when a
result is inconvenient — which is when the temptation to revise arrives.

Nothing here decides whether a finding is TRUE. The jury and the judge do that
upstream. This decides whether a finding is ADMISSIBLE, which is a different and
narrower question: does it carry what a reader needs in order to check it.
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

GENESIS = "0" * 64

# Deliberately closed sets. A new evidence type or sample kind is a change to
# what the audit claims it can know, and should require editing this file and
# arguing for it — not passing a new string at a call site.
EVIDENCE_TYPES = ("deterministic", "judged", "human")
SAMPLE_KINDS = ("core", "control", "adaptive")

VERDICTS = ("PASS", "FAIL", "UNDETERMINED", "PARTIAL", "NOT_ASSESSED")


class UntraceableFinding(ValueError):
    """Raised when a finding cannot be admitted because its trace is incomplete.

    Deliberately its own exception. Callers should not be able to catch this
    with a bare `except ValueError` intended for something else and carry on
    with an unadmitted finding they believe was recorded.
    """


@dataclass
class Entry:
    """One admitted finding, with everything needed to check it."""
    clause_ids: list[str]         # which obligations this speaks to
    dimension: str                # fairness | robustness | transparency | ...
    estimand: str                 # what was measured, in words
    evidence_type: str            # deterministic | judged | human
    sample_kind: str              # core | control | adaptive
    verdict: str                  # PASS | FAIL | UNDETERMINED | PARTIAL | NOT_ASSESSED
    n: int
    estimate: float | None = None
    ci_low: float | None = None
    ci_high: float | None = None
    method: str = ""
    p_value: float | None = None
    model_id: str = ""            # the AUDITED model
    judge_id: str = ""            # set iff evidence_type == "judged"
    judge_validated: bool = False  # judge measured against the human ceiling?
    stratum: str = ""
    checklist_sha256: str = ""    # which signed checklist this was scored under
    detail: dict = field(default_factory=dict)
    note: str = ""
    created_utc: str = ""
    prev_sha256: str = GENESIS
    sha256: str = ""

    def __post_init__(self) -> None:
        if not self.created_utc:
            self.created_utc = datetime.now(timezone.utc).isoformat(timespec="seconds")

    # --- admissibility ---------------------------------------------------
    def check(self) -> None:
        """Refuse the entry unless it carries a complete trace. Raises."""
        if not self.clause_ids:
            raise UntraceableFinding(
                f"'{self.estimand}' names no clause. A measurement with no "
                "obligation behind it is a benchmark score, not a finding about "
                "conformity, and this ledger is not the place for it.")
        if self.evidence_type not in EVIDENCE_TYPES:
            raise UntraceableFinding(
                f"evidence_type '{self.evidence_type}' is not one of "
                f"{EVIDENCE_TYPES}. How a number was obtained determines what it "
                "can support, so it cannot be left unstated.")
        if self.sample_kind not in SAMPLE_KINDS:
            raise UntraceableFinding(
                f"sample_kind '{self.sample_kind}' is not one of {SAMPLE_KINDS}.")
        if self.verdict not in VERDICTS:
            raise UntraceableFinding(
                f"verdict '{self.verdict}' is not one of {VERDICTS}. "
                "UNDETERMINED is a verdict; absence of one is not.")
        if self.evidence_type == "judged" and not self.judge_id:
            raise UntraceableFinding(
                f"'{self.estimand}' is judged evidence with no judge named. A "
                "model verdict whose author is unrecorded cannot be checked, "
                "reproduced, or excluded if that judge is later found wanting.")
        if self.evidence_type != "judged" and self.judge_id:
            raise UntraceableFinding(
                f"'{self.estimand}' names judge '{self.judge_id}' but is typed "
                f"'{self.evidence_type}'. One of the two is wrong, and guessing "
                "which would be worse than refusing.")
        if self.n <= 0:
            raise UntraceableFinding(
                f"'{self.estimand}' has n={self.n}. A finding computed on no "
                "observations is not a weak finding, it is not a finding.")

    @property
    def headline_eligible(self) -> bool:
        """May this support a headline claim?

        Core sample, and — for judged evidence — a judge that has actually been
        measured against the human ceiling. An unvalidated judge's verdicts are
        an input to the validation study, not a result, and the difference is
        the whole reason the annotation study exists.
        """
        if self.sample_kind != "core":
            return False
        if self.evidence_type == "judged" and not self.judge_validated:
            return False
        return True

    def payload(self) -> dict:
        d = asdict(self)
        d.pop("sha256", None)
        return d

    def digest(self) -> str:
        return hashlib.sha256(
            json.dumps(self.payload(), sort_keys=True, ensure_ascii=False,
                       separators=(",", ":")).encode("utf-8")).hexdigest()

    def as_dict(self) -> dict:
        return asdict(self)


class Ledger:
    """An append-only, hash-chained file of admitted findings."""

    def __init__(self, path: str):
        self.path = path
        self.entries: list[Entry] = []
        self._head = GENESIS
        if os.path.exists(path):
            self._load()

    # --- reading ---------------------------------------------------------
    def _load(self) -> None:
        with open(self.path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    self.entries.append(Entry(**json.loads(line)))
        if self.entries:
            self._head = self.entries[-1].sha256

    def verify(self) -> tuple[bool, str]:
        """Recompute the chain. Returns (ok, reason)."""
        prev = GENESIS
        for i, e in enumerate(self.entries):
            if e.prev_sha256 != prev:
                return False, (f"entry {i} ('{e.estimand}') claims to follow "
                               f"{e.prev_sha256[:12]} but follows {prev[:12]}. "
                               "An entry has been removed, reordered or inserted.")
            if e.digest() != e.sha256:
                return False, (f"entry {i} ('{e.estimand}') does not hash to its "
                               "recorded digest — its content was edited after "
                               "it was written.")
            prev = e.sha256
        return True, f"{len(self.entries)} entries, chain intact"

    # --- writing ---------------------------------------------------------
    def append(self, entry: Entry) -> Entry:
        """Admit one finding. Raises UntraceableFinding rather than warning."""
        entry.check()
        entry.prev_sha256 = self._head
        entry.sha256 = entry.digest()
        os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry.as_dict(), ensure_ascii=False) + "\n")
            fh.flush()
            os.fsync(fh.fileno())
        self.entries.append(entry)
        self._head = entry.sha256
        return entry

    # --- views -----------------------------------------------------------
    def for_clause(self, clause_id: str) -> list[Entry]:
        return [e for e in self.entries if clause_id in e.clause_ids]

    def clauses(self) -> list[str]:
        seen: list[str] = []
        for e in self.entries:
            for c in e.clause_ids:
                if c not in seen:
                    seen.append(c)
        return seen

    def __len__(self) -> int:
        return len(self.entries)


def from_finding(finding, *, evidence_type: str, sample_kind: str, verdict: str,
                 model_id: str = "", judge_id: str = "",
                 judge_validated: bool = False,
                 checklist_sha256: str = "") -> Entry:
    """Adapt a jury `Finding` into a ledger `Entry`.

    The jury computes; the ledger admits. Keeping the adaptation explicit means
    the extra facts admissibility needs — what kind of evidence this is, which
    sample it came from, whether the judge behind it has been validated — are
    supplied deliberately at the call site rather than defaulted into existence.
    """
    role_to_sample = {"confirmatory": "core", "instrument": "control",
                      "exploratory": "adaptive"}
    return Entry(
        clause_ids=list(finding.clause_ids),
        dimension=finding.dimension,
        estimand=finding.estimand,
        evidence_type=evidence_type,
        sample_kind=sample_kind or role_to_sample.get(finding.role, "adaptive"),
        verdict=verdict,
        n=finding.n,
        estimate=finding.estimate,
        ci_low=finding.ci_low,
        ci_high=finding.ci_high,
        method=finding.method,
        p_value=finding.p_value,
        model_id=model_id,
        judge_id=judge_id,
        judge_validated=judge_validated,
        stratum=finding.stratum,
        checklist_sha256=checklist_sha256,
        detail=dict(finding.detail),
        note=finding.note)
