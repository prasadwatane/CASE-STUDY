"""The A-then-B router: decide how each gold is obtained, then how far to trust it.

**A — take everything that can be had without a model.** Items with a compute
spec are solved in `formulas.py` and stamped Green with the formula and its
arguments recorded. No proposer is consulted; a computed gold never has a model
anywhere in its provenance.

**B — for the rest, propose and gate.** The proposer answers k times, and the
disagreement score goes to the conformal gate. Accept as Amber only if the score
clears a threshold that was certified to hold selective error at or below alpha;
otherwise escalate to a human.

The calibration set is the computed items, which is the pleasant part of the
design: their labels are free, so calibration costs nothing extra and grows
automatically as the seed bank grows.

**Bounded leakage** is the quantity to report — the share of items a human has to
look at. It falls as the proposer gets better and as calibration grows, and it is
measured rather than asserted. When the gate cannot certify anything, leakage is
100% by construction, which is the correct and honest answer rather than a
degraded one.
"""
from __future__ import annotations

from grail.gold import formulas
from grail.gold.conformal import Calibration, calibrate, nonconformity
from grail.gold.schema import (AMBER, ESCALATED, GREEN, ROUTE_COMPUTED,
                               ROUTE_SOURCED, ROUTE_STRUCTURAL, GoldRecord,
                               seal_chain)

KEYED_ROUTES = {ROUTE_COMPUTED, ROUTE_SOURCED, ROUTE_STRUCTURAL}


def _probe_index(probes: list) -> dict[str, list[str]]:
    """seed item id -> the probe ids it keys (every framing shares one gold)."""
    out: dict[str, list[str]] = {}
    for p in probes:
        item_id = p.slots.get("seed_item") if isinstance(p.slots, dict) else None
        if item_id:
            out.setdefault(item_id, []).append(p.id)
    return {k: sorted(v) for k, v in out.items()}


def _compute_green(item: dict, domain: str, dimension: str,
                   probe_ids: list[str]) -> tuple[GoldRecord, str]:
    value, formatted, prov = formulas.evaluate(item["compute"])
    return GoldRecord(
        item_id=item["id"], domain=domain, dimension=dimension,
        route=ROUTE_COMPUTED, status=GREEN, answer=formatted,
        answer_kind="value", provenance=prov, probe_ids=probe_ids), formatted


def build_golds(items: list[dict], probes: list, proposer, domain: str,
                dimension: str = "truthfulness", alpha: float = 0.05,
                delta: float = 0.05, k: int = 5,
                allow_stub: bool = False) -> tuple[list[GoldRecord], dict]:
    """Route every keyed item to Green, Amber or a human. Returns (records, report)."""
    if getattr(proposer, "is_stub", False) and not allow_stub:
        raise SystemExit(
            "GOLD PIPELINE: refusing to build a ledger with "
            f"'{proposer.name}'. A stub proposer is not evidence — wire a real "
            "model, or pass allow_stub=True for a dry run (the stub's name stays "
            "in the provenance either way).")

    by_probe = _probe_index(probes)
    keyed = [it for it in items if it.get("gold_route") in KEYED_ROUTES]
    notes: list[str] = []

    # --- A: everything obtainable without a model ---------------------------
    records: list[GoldRecord] = []
    references: dict[str, str] = {}
    computed_items: list[dict] = []
    for item in keyed:
        if item.get("gold_route") != ROUTE_COMPUTED:
            continue
        if "compute" not in item:
            notes.append(f"{item['id']}: route is 'computed' but no compute spec — "
                         "cannot be Green, sent to the proposer instead")
            item = dict(item, gold_route=ROUTE_SOURCED)
            continue
        rec, formatted = _compute_green(item, domain, dimension,
                                        by_probe.get(item["id"], []))
        records.append(rec)
        references[item["id"]] = formatted
        computed_items.append(item)

    # --- calibrate on those free labels -------------------------------------
    observations: list[tuple[float, bool]] = []
    for item in computed_items:
        probe_item = dict(item)
        if getattr(proposer, "is_stub", False):
            # only the stub is handed the reference, and only so it can imitate a
            # proposer that is sometimes right; a real proposer never sees it
            probe_item["_reference"] = references[item["id"]]
        proposals = proposer.propose(probe_item, k)
        score, modal, _ = nonconformity(proposals)
        observations.append((score, modal == references[item["id"]]))

    cal: Calibration = calibrate(observations, alpha=alpha, delta=delta)
    if not cal.certified:
        notes.append(f"conformal gate: {cal.reason}")

    # --- B: propose and gate the rest ---------------------------------------
    for item in keyed:
        route = item.get("gold_route")
        if route == ROUTE_COMPUTED and "compute" in item:
            continue
        probe_ids = by_probe.get(item["id"], [])
        proposals = proposer.propose(item, k)
        score, modal, share = nonconformity(proposals)

        structural_ok = (route != ROUTE_STRUCTURAL or modal == "construction_holds")
        accept = cal.certified and score <= (cal.threshold or -1.0) and structural_ok

        if accept:
            answer = (item.get("expected_behavior") or modal
                      if route == ROUTE_STRUCTURAL else modal)
            records.append(GoldRecord(
                item_id=item["id"], domain=domain, dimension=dimension,
                route=route, status=AMBER, answer=answer,
                answer_kind="behaviour" if route == ROUTE_STRUCTURAL else "value",
                provenance={
                    "method": "model-proposed, accepted by the conformal gate",
                    "proposer": proposer.name, "k": k,
                    "calibrated_on": "computed items with free labels",
                    "n_calibration": cal.n_calibration,
                    "delta": delta, "delta_adjusted": cal.delta_adjusted,
                    "recomputable": False,
                },
                probe_ids=probe_ids, proposals=proposals, agreement=share,
                nonconformity=score, threshold=cal.threshold, alpha=alpha,
                error_bound=cal.error_bound))
        else:
            if not cal.certified:
                why = "the conformal gate is not certified, so nothing is auto-accepted"
            elif not structural_ok:
                why = (f"the proposer did not confirm the item's construction "
                       f"(said '{modal}') — the premise or entity needs checking")
            else:
                why = (f"disagreement {score:.2f} exceeds the certified threshold "
                       f"{cal.threshold:.2f}")
            records.append(GoldRecord(
                item_id=item["id"], domain=domain, dimension=dimension,
                route=route, status=ESCALATED, answer=None, answer_kind="none",
                provenance={"method": "queued for human resolution",
                            "proposer": proposer.name, "k": k},
                probe_ids=probe_ids, proposals=proposals, agreement=share,
                nonconformity=score, threshold=cal.threshold, alpha=alpha,
                escalation_reason=why))

    seal_chain(records)
    return records, _report(records, cal, proposer, domain, dimension, k, notes)


def _report(records: list[GoldRecord], cal: Calibration, proposer, domain: str,
            dimension: str, k: int, notes: list[str]) -> dict:
    n = len(records)
    counts = {GREEN: 0, AMBER: 0, ESCALATED: 0}
    by_route: dict[str, dict] = {}
    for rec in records:
        counts[rec.status] = counts.get(rec.status, 0) + 1
        r = by_route.setdefault(rec.route, {GREEN: 0, AMBER: 0, ESCALATED: 0})
        r[rec.status] += 1
    share = (lambda x: round(x / n, 4) if n else 0.0)
    return {
        "domain": domain,
        "dimension": dimension,
        "n_items": n,
        "counts": counts,
        "split": {"green": share(counts[GREEN]), "amber": share(counts[AMBER]),
                  "escalated": share(counts[ESCALATED])},
        "by_route": by_route,
        "human_leakage": share(counts[ESCALATED]),
        "proposer": proposer.name,
        "proposer_is_stub": bool(getattr(proposer, "is_stub", False)),
        "k": k,
        "calibration": cal.as_dict(),
        "notes": notes,
        "ledger_head": records[-1].sha256 if records else None,
    }
