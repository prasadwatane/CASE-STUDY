"""Inter-rater agreement for the annotation study — deterministic, no model.

Rules this module enforces (mirrors the design notes in README):
  * kappa is never reported without a bootstrap interval;
  * kappa is reported as None when undefined (expected agreement == 1),
    never as 0.0;
  * kappa never travels alone: percent agreement, expected agreement and
    the label marginals are returned with it, because kappa is
    prevalence-sensitive;
  * any number of raters: pairwise Cohen's kappa for every pair, plus
    Fleiss' kappa across all raters on the common item set.
"""
from __future__ import annotations

import csv
import itertools
import random
from collections import Counter
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

Rating = str
Sheet = Dict[str, Rating]  # item id -> rating


# ---------------------------------------------------------------- loading
def load_sheet(path: Path, allowed: Optional[Sequence[str]] = None) -> Sheet:
    """Read a rater CSV (item,dimension,criterion,prompt,response,rating,notes).

    Blank ratings are dropped (unrated), and any label outside `allowed`
    raises: an undeclared label silently changes the chance-agreement
    baseline, so it must be declared before it is scored.
    """
    out: Sheet = {}
    with open(path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            r = (row.get("rating") or "").strip().lower()
            if not r:
                continue
            if allowed is not None and r not in allowed:
                raise ValueError(f"{path.name}: undeclared label {r!r} on {row['item']}")
            out[row["item"]] = r
    return out


def load_meta(path: Path) -> Dict[str, Dict[str, str]]:
    with open(path, newline="", encoding="utf-8") as fh:
        return {row["item"]: {"dimension": row["dimension"], "criterion": row["criterion"]}
                for row in csv.DictReader(fh)}


# ---------------------------------------------------------------- kappa
@dataclass
class Kappa:
    n: int
    percent_agreement: float
    expected_agreement: float
    kappa: Optional[float]          # None when undefined (pe == 1)
    ci_low: Optional[float] = None
    ci_high: Optional[float] = None
    marginals: Dict[str, Dict[str, int]] = field(default_factory=dict)


def _cohen(x: Sequence[Rating], y: Sequence[Rating]) -> Tuple[float, float, Optional[float]]:
    n = len(x)
    if n == 0:
        raise ValueError("no overlapping items")
    labels = set(x) | set(y)
    po = sum(a == b for a, b in zip(x, y)) / n
    cx, cy = Counter(x), Counter(y)
    pe = sum((cx[l] / n) * (cy[l] / n) for l in labels)
    if pe >= 1.0:
        return po, pe, None
    return po, pe, (po - pe) / (1 - pe)


def cohen_kappa(a: Sheet, b: Sheet, *, n_boot: int = 4000, seed: int = 0,
                alpha: float = 0.05) -> Kappa:
    items = sorted(set(a) & set(b))
    x = [a[i] for i in items]
    y = [b[i] for i in items]
    po, pe, k = _cohen(x, y)
    n = len(items)
    rng = random.Random(seed)
    boots: List[float] = []
    for _ in range(n_boot):
        idx = [rng.randrange(n) for _ in range(n)]
        _, _, kb = _cohen([x[j] for j in idx], [y[j] for j in idx])
        if kb is not None:
            boots.append(kb)
    lo = hi = None
    if k is not None and boots:
        boots.sort()
        lo = boots[int(alpha / 2 * len(boots))]
        hi = boots[min(len(boots) - 1, int((1 - alpha / 2) * len(boots)))]
    return Kappa(n=n, percent_agreement=po, expected_agreement=pe, kappa=k,
                 ci_low=lo, ci_high=hi,
                 marginals={"a": dict(Counter(x)), "b": dict(Counter(y))})


def fleiss_kappa(sheets: Sequence[Sheet]) -> Kappa:
    """Fleiss' kappa on items rated by every sheet."""
    items = sorted(set.intersection(*(set(s) for s in sheets)))
    m = len(sheets)
    if m < 2 or not items:
        raise ValueError("need >=2 raters and >=1 common item")
    labels = sorted({s[i] for s in sheets for i in items})
    N = len(items)
    P_i = []
    pj: Counter = Counter()
    for i in items:
        c = Counter(s[i] for s in sheets)
        pj.update(c)
        P_i.append((sum(v * v for v in c.values()) - m) / (m * (m - 1)))
    Pbar = sum(P_i) / N
    Pe = sum((pj[l] / (N * m)) ** 2 for l in labels)
    k = None if Pe >= 1.0 else (Pbar - Pe) / (1 - Pe)
    return Kappa(n=N, percent_agreement=Pbar, expected_agreement=Pe, kappa=k,
                 marginals={"all": dict(pj)})


# ---------------------------------------------------------------- study
@dataclass
class AgreementReport:
    raters: List[str]
    n_items: int
    labels: List[str]
    pairwise: Dict[str, dict]
    fleiss: dict
    unanimous: int
    disagreements: List[dict]
    per_criterion: Dict[str, dict]

    def to_dict(self) -> dict:
        return asdict(self)


def score_study(sheets: Dict[str, Sheet], meta: Dict[str, Dict[str, str]],
                *, seed: int = 0) -> AgreementReport:
    names = list(sheets)
    common = sorted(set.intersection(*(set(s) for s in sheets.values())))
    labels = sorted({sheets[r][i] for r in names for i in common})
    pairwise = {f"{a}-{b}": asdict(cohen_kappa(sheets[a], sheets[b], seed=seed))
                for a, b in itertools.combinations(names, 2)}
    fl = asdict(fleiss_kappa([sheets[r] for r in names]))
    dis, unan = [], 0
    for i in common:
        votes = {r: sheets[r][i] for r in names}
        if len(set(votes.values())) == 1:
            unan += 1
        else:
            dis.append({"item": i, **meta.get(i, {}), "votes": votes})
    per_crit: Dict[str, dict] = {}
    crits = sorted({meta[i]["criterion"] for i in common if i in meta})
    for c in crits:
        sub = [i for i in common if meta.get(i, {}).get("criterion") == c]
        if len(sub) < 2:
            continue
        subsheets = [{i: sheets[r][i] for i in sub} for r in names]
        per_crit[c] = {"n": len(sub), "fleiss": asdict(fleiss_kappa(subsheets))}
    return AgreementReport(raters=names, n_items=len(common), labels=labels,
                           pairwise=pairwise, fleiss=fl, unanimous=unan,
                           disagreements=dis, per_criterion=per_crit)


def render_markdown(rep: AgreementReport, title: str) -> str:
    def f(v: Optional[float]) -> str:
        return "undefined" if v is None else f"{v:.3f}"
    lines = [f"# {title}", "",
             f"Raters: {', '.join(rep.raters)} · common items: {rep.n_items} · "
             f"labels: {', '.join(rep.labels)}", "",
             "| pair | n | agreement | expected | κ | 95% CI |", "|---|---|---|---|---|---|"]
    for k, v in rep.pairwise.items():
        ci = "—" if v["ci_low"] is None else f"[{v['ci_low']:.2f}, {v['ci_high']:.2f}]"
        lines.append(f"| {k} | {v['n']} | {v['percent_agreement']:.2f} | "
                     f"{v['expected_agreement']:.2f} | {f(v['kappa'])} | {ci} |")
    fl = rep.fleiss
    lines += ["", f"Fleiss κ (all raters): **{f(fl['kappa'])}** "
                  f"(P̄ = {fl['percent_agreement']:.2f}, Pe = {fl['expected_agreement']:.2f}); "
                  f"unanimous on {rep.unanimous}/{rep.n_items}.", ""]
    if rep.per_criterion:
        lines += ["| criterion | n | Fleiss κ |", "|---|---|---|"]
        for c, v in rep.per_criterion.items():
            lines.append(f"| {c} | {v['n']} | {f(v['fleiss']['kappa'])} |")
        lines.append("")
    lines += [f"## Disagreements ({len(rep.disagreements)})", ""]
    for d in rep.disagreements:
        votes = ", ".join(f"{r}={v}" for r, v in d["votes"].items())
        lines.append(f"- `{d['item']}` · {d.get('criterion', '?')} · {votes}")
    return "\n".join(lines) + "\n"
