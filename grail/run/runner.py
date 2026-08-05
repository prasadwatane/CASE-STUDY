"""Put probes to a model and log what comes back.

The runner does as little as possible on purpose. It does not score, aggregate,
or interpret — it sends prompts, records raw responses, and stops. Everything
downstream reads the log.

Two properties worth stating:

* **Deterministic order, resumable.** Probes are visited in a seeded shuffle
  rather than file order, so an interrupted or truncated run is still a
  representative sample of the whole set rather than the first N fairness pairs.
  Anything already in the log is skipped, so resuming costs nothing.
* **Errors are recorded, not raised.** A failed call becomes a row with an
  `error` and an empty response. Losing an hour of paid calls because request 812
  timed out would be a bad trade, and a run with 3% errors is a fact worth
  keeping rather than hiding.

Sampling for a pilot is stratified across dimensions by default: 50 probes drawn
proportionally tells you about fairness, robustness and transparency at once,
where the first 50 rows of the file would all be fairness.
"""
from __future__ import annotations

import time
from dataclasses import dataclass

from grail.probe.schema import derive_rng
from grail.run.client import params_hash
from grail.run.store import ResponseRecord, append, cached_keys, load


@dataclass
class RunSummary:
    run_id: str
    model_id: str
    params: dict
    requested: int
    called: int
    cached: int
    errors: int
    seconds: float

    def as_dict(self) -> dict:
        from dataclasses import asdict
        return asdict(self)


def select(probes: list, limit: int | None, seed: int,
           stratify: bool = True) -> list:
    """Choose which probes to run — seeded, paired, and spread across dimensions.

    Two rules that a naive "take the first N" gets wrong, both learned from a dry
    run that could not answer half the questions it was for:

    * **Pairs are indivisible.** A robustness variant without its base, or one arm
      of a fairness pair, is an unusable observation — the comparison is the
      measurement. Sampling therefore draws whole pairs and sets, so `limit` is a
      budget rather than an exact count.
    * **Controls always run in full.** They are the answer to "would a null result
      mean anything", they are cheap, and a proportional sample of them lands one
      or two probes, which is worse than none because it looks like coverage.
      `limit` applies to the CORE budget; controls are additional.
    """
    from grail.probe.schema import CONTROL

    ordered = sorted(probes, key=lambda p: p.id)
    r = derive_rng(seed, "runner/selection")
    controls = [p for p in ordered if p.sample_kind == CONTROL]
    rest = [p for p in ordered if p.sample_kind != CONTROL]

    if limit is None or limit >= len(rest):
        everything = list(ordered)
        r.shuffle(everything)
        return everything

    units: dict = {}
    for p in rest:
        units.setdefault((p.dimension, p.pair_id or p.id), []).append(p)

    by_dim: dict[str, list] = {}
    for (dim, _), members in units.items():
        by_dim.setdefault(dim, []).append(members)
    for dim in by_dim:
        by_dim[dim].sort(key=lambda unit: unit[0].id)
        r.shuffle(by_dim[dim])

    if not stratify:
        flat = [u for dim in sorted(by_dim) for u in by_dim[dim]]
        r.shuffle(flat)
        picked = _take(flat, limit)
        return controls + picked

    total = len(rest)
    picked: list = []
    for dim in sorted(by_dim):
        dim_prompts = sum(len(u) for u in by_dim[dim])
        picked.extend(_take(by_dim[dim], max(1, round(limit * dim_prompts / total))))

    r.shuffle(picked)
    return controls + picked


def _take(units: list, budget: int) -> list:
    """Whole units until the prompt budget is met — never a partial pair."""
    out: list = []
    for unit in units:
        if len(out) >= budget:
            break
        out.extend(unit)
    return out


def run(probes: list, model, log_path: str, params: dict | None = None,
        limit: int | None = None, seed: int = 0, allow_stub: bool = False,
        stratify: bool = True, on_progress=None) -> tuple[list[ResponseRecord], RunSummary]:
    """Send probes to `model`, appending raw responses to the log."""
    if getattr(model, "is_stub", False) and not allow_stub:
        raise SystemExit(
            f"RUNNER: refusing to write a response log with '{model.id}'. A stub "
            "is plumbing, not evidence — wire a real model, or pass allow_stub "
            "for a dry run (the stub's id stays in the log either way).")

    params = dict(params or {"temperature": 0.0})
    ph = params_hash(params)
    run_id = f"{model.id}@{ph}/{int(time.time())}"

    already = cached_keys(load(log_path))
    chosen = select(probes, limit, seed, stratify)

    fresh: list[ResponseRecord] = []
    called = cached = errors = 0
    started = time.time()

    todo = []
    for probe in chosen:
        if (probe.content_sha256, model.id, ph) in already:
            cached += 1
        else:
            todo.append(probe)

    def record(probe, text, err, ms):
        fresh.append(ResponseRecord(
            probe_id=probe.id, probe_sha256=probe.content_sha256,
            domain=probe.domain, dimension=probe.dimension, model_id=model.id,
            params_hash=ph, params=params, response=text, run_id=run_id,
            latency_ms=ms, error=err))

    batch = getattr(model, "generate_batch", None)
    if batch and todo:
        # One call for everything. A local engine schedules the whole set far
        # better than we can by feeding it one prompt at a time.
        t0 = time.time()
        try:
            texts = batch([p.prompt for p in todo], **params)
            if len(texts) != len(todo):
                raise RuntimeError(
                    f"batch returned {len(texts)} responses for {len(todo)} prompts — "
                    "responses could be misaligned with their probes, so none are kept")
            per = int((time.time() - t0) * 1000 / max(1, len(todo)))
            for probe, text in zip(todo, texts):
                record(probe, text, "", per)
        except Exception as exc:      # a failed batch is recorded, never raised
            errors = len(todo)
            for probe in todo:
                record(probe, "", f"{type(exc).__name__}: {exc}", 0)
        called = len(todo)
        if on_progress:
            on_progress(called, len(chosen))
    else:
        for i, probe in enumerate(todo):
            t0 = time.time()
            text, err = "", ""
            try:
                text = model.generate(probe.prompt, **params)
            except Exception as exc:                  # recorded, never raised
                err = f"{type(exc).__name__}: {exc}"
                errors += 1
            called += 1
            record(probe, text, err, int((time.time() - t0) * 1000))
            if on_progress and (i + 1) % 25 == 0:
                on_progress(i + 1, len(todo))

    if fresh:
        append(log_path, fresh)

    return fresh, RunSummary(
        run_id=run_id, model_id=model.id, params=params, requested=len(chosen),
        called=called, cached=cached, errors=errors,
        seconds=round(time.time() - started, 2))
