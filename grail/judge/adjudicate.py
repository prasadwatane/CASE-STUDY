"""Run the judge k times, ground its quotations, and measure its self-agreement.

A single judge call is an opinion. What makes an opinion usable as audit evidence
is knowing how often it would have said something else, so every item is judged
k times and the spread is recorded rather than averaged away.

Four defences, in the order they fire:

**Family disjointness.** The judge must not come from the same family as any
model it grades. A model asked to assess its own output has a documented
self-preference, and the same weights under a different name is the same model.
`assert_disjoint` refuses the run rather than noting it in a limitations section.

**Span grounding, in code.** Every condition answer carries a quotation, and the
quotation is checked against the response by string matching. An answer whose
support was composed rather than found is discarded. This is the only check here
that catches invention, because a model confabulates the same plausible sentence
on every run — self-consistency is blind to it by construction.

**Self-consistency as a confidence signal, not a verdict.** k runs at a non-zero
temperature; the majority answer is taken and the agreement fraction recorded.
Low self-agreement does not become a quiet averaged score, it becomes an
escalation to a human.

**Deterministic conditions are never asked.** Whatever `judge.checks` can settle
is settled before the model is called and passed to it as context. The model's
error surface is the part of the criterion that genuinely needs reading.

Nothing here decides whether the judge is trustworthy. That is what the human
annotation study measures, against the human-human ceiling; this module only
produces the verdicts that study will be compared against.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import asdict, dataclass, field

from grail.judge import checks
from grail.judge.rubric import SYSTEM, Rubric, render

CANNOT_TELL = "cannot_tell"


def family_of(model_id: str) -> str:
    """Crude but deliberate: the vendor prefix, lowercased.

    Deliberately crude because the failure it guards against is gross — judging
    Qwen with Qwen — and a subtle definition would invite argument about edge
    cases while missing the obvious one.
    """
    name = model_id.split("/")[-1].lower()
    for fam in ("qwen", "llama", "mistral", "gemma", "phi", "gpt", "claude",
                "deepseek", "falcon", "olmo", "yi", "command"):
        if fam in name or fam in model_id.lower():
            return fam
    return model_id.lower()


def assert_disjoint(judge_id: str, audited: list[str]) -> None:
    judge_family = family_of(judge_id)
    clash = [m for m in audited if family_of(m) == judge_family]
    if clash:
        raise ValueError(
            f"the judge '{judge_id}' shares a family ('{judge_family}') with "
            f"{clash}. Self-preference is documented and the same weights under "
            "a different name are the same model, so this is refused rather "
            "than noted as a limitation. Choose a judge from another family.")


@dataclass
class ConditionVerdict:
    key: str
    answer: str                       # yes | no | cannot_tell
    agreement: float                  # share of runs giving the majority answer
    quote: str = ""
    grounded: bool = False
    settled_in_code: bool = False
    runs: list[str] = field(default_factory=list)


@dataclass
class ItemVerdict:
    probe_id: str
    clause_id: str
    judge_id: str
    k: int
    conditions: list[ConditionVerdict]
    adequate: bool | None             # None when any condition is undecided
    self_agreement: float             # lowest agreement across conditions
    ungrounded_quotes: int
    deterministic: dict = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return asdict(self)


def _parse(raw: str) -> dict:
    """Pull the JSON object out of a reply that may be wrapped in prose or fences."""
    text = raw.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    if fence:
        text = fence.group(1)
    else:
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            raise ValueError("no JSON object in the reply")
        text = text[start:end + 1]
    return json.loads(text)


def _reduce(rubric, probe, response, det, settled, per_condition, errors,
            judge_id, k) -> ItemVerdict:
    """Turn k runs into one verdict. Identical whether the runs were batched."""
    verdicts: list[ConditionVerdict] = []
    ungrounded = 0
    for c in rubric.conditions:
        runs = per_condition[c["key"]]

        # A condition settled in code is not put to a vote.
        if c["key"] in settled:
            verdicts.append(ConditionVerdict(
                key=c["key"], answer="yes" if settled[c["key"]] else "no",
                agreement=1.0, settled_in_code=True, grounded=True,
                runs=[a for a, _ in runs]))
            continue

        if not runs:
            verdicts.append(ConditionVerdict(c["key"], CANNOT_TELL, 0.0))
            continue

        # Ungrounded answers are dropped BEFORE the vote, so an invented
        # quotation cannot carry a majority.
        kept = []
        for answer, quote in runs:
            if answer == CANNOT_TELL or checks.quote_is_grounded(quote, response):
                kept.append((answer, quote))
            else:
                ungrounded += 1

        if not kept:
            verdicts.append(ConditionVerdict(
                c["key"], CANNOT_TELL, 0.0, runs=[a for a, _ in runs]))
            continue

        counts = Counter(a for a, _ in kept)
        answer, n = counts.most_common(1)[0]
        quote = next((q for a, q in kept if a == answer and q), "")
        verdicts.append(ConditionVerdict(
            key=c["key"], answer=answer, agreement=n / len(kept), quote=quote,
            grounded=bool(quote), runs=[a for a, _ in runs]))

    decided = [v for v in verdicts if v.answer != CANNOT_TELL]
    adequate = (all(v.answer == "yes" for v in verdicts)
                if len(decided) == len(verdicts) else None)

    return ItemVerdict(
        probe_id=probe.id, clause_id=rubric.clause_id, judge_id=judge_id, k=k,
        conditions=verdicts, adequate=adequate,
        self_agreement=min((v.agreement for v in verdicts), default=0.0),
        ungrounded_quotes=ungrounded, deterministic=det.as_dict(), errors=errors)


def judge_items(model, rubric: Rubric, items: list, k: int = 5,
                temperature: float = 0.3, on_progress=None) -> list[ItemVerdict]:
    """Judge many responses at once, putting every call through one GPU pass.

    `items` is a list of (probe, response) pairs.

    Batching matters more here than it looks. Judging is k runs per item, so a
    152-item docket at k = 5 is 760 inferences; issued one at a time on a 14B
    model that is roughly seventy-five minutes, and four audited models is most
    of a working day. The same prompts sent as one batch fill the KV cache and
    finish in about a tenth of the time.

    Nothing statistical changes. The k runs are independent draws either way and
    the reduction is the same function, so batching buys time and costs nothing.

    Falls back to sequential calls when the backend has no `generate_batch`, so
    an HTTP judge or the offline stub still works unchanged.
    """
    prepared = []
    for probe, response in items:
        det = checks.check(response, probe.slots)
        settled = det.settled
        prompt = f"{SYSTEM}\n\n{render(rubric, probe.slots, response, settled=settled)}"
        prepared.append((probe, response, det, settled, prompt))

    flat = [p[4] for p in prepared for _ in range(k)]   # (item0 x k), (item1 x k), …

    batch = getattr(model, "generate_batch", None)
    if batch is not None:
        replies = batch(flat, temperature=temperature)
        if len(replies) != len(flat):
            raise RuntimeError(
                f"judge returned {len(replies)} replies for {len(flat)} prompts. "
                "A misaligned batch would attribute answers to the wrong items, "
                "so it is refused rather than recorded.")
    else:
        replies = []
        for i, prompt in enumerate(flat):
            try:
                replies.append(model.generate(prompt, temperature=temperature))
            except Exception as exc:                   # noqa: BLE001
                replies.append(exc)
            if on_progress and (i + 1) % (k * 10) == 0:
                on_progress((i + 1) // k, len(prepared))

    out = []
    for idx, (probe, response, det, settled, _) in enumerate(prepared):
        per_condition = {c["key"]: [] for c in rubric.conditions}
        errors = []
        for raw in replies[idx * k:(idx + 1) * k]:
            if isinstance(raw, Exception):
                errors.append(f"{type(raw).__name__}: {raw}")
                continue
            try:
                parsed = _parse(raw)
            except Exception as exc:                   # noqa: BLE001
                errors.append(f"{type(exc).__name__}: {exc}")
                continue
            got = parsed.get("conditions", {})
            for c in rubric.conditions:
                entry = got.get(c["key"]) or {}
                answer = str(entry.get("answer", CANNOT_TELL)).strip().lower()
                if answer not in ("yes", "no", CANNOT_TELL):
                    answer = CANNOT_TELL
                per_condition[c["key"]].append((answer, str(entry.get("quote", ""))))
        out.append(_reduce(rubric, probe, response, det, settled,
                           per_condition, errors, model.id, k))
    if on_progress:
        on_progress(len(prepared), len(prepared))
    return out


def judge_item(model, rubric: Rubric, probe, response: str, k: int = 5,
               temperature: float = 0.3) -> ItemVerdict:
    """Judge a single response. Thin wrapper over the batched path."""
    return judge_items(model, rubric, [(probe, response)], k=k,
                       temperature=temperature)[0]
