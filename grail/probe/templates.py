"""Stimulus packs: the sub-domain-specific part of a probe, held as data.

Everything a system under audit reads is assembled here, but none of it is
written here. A **stimulus pack** (`data/stimuli/<name>/pack.json`) declares the
case fields, the strata parameters, the vocabulary and the rendering templates
for one sub-domain; this module is the generic sampler and renderer that turns a
pack into prompts. Swapping credit for insurance is a pack, not a patch.

That split is the whole point. The audit machinery — counterbalancing,
stratification, perturbation, seeding, the leakage guard — is sub-domain
independent and lives in the generators. The stimulus content is not, and if it
stayed hard-coded here then pointing the pipeline at an insurance corpus would
quietly emit insurance-labelled loan applications: no error, clean-looking
output, wrong experiment.

Two rules the packs must respect, both enforced downstream:

* **No legal vocabulary.** Packs read as ordinary commercial work. The guard in
  `schema.assert_no_leakage` catches a violation at probe construction.
* **Numbers render without thousands separators**, so "the digit multiset is
  unchanged" stays a usable proof that a perturbation preserved meaning.

A pack also declares its `outcome` type. Credit decisions are binary; insurance
premiums are continuous. The jury needs a different statistical route for each,
so the pack says which rather than the pipeline assuming.
"""
from __future__ import annotations

import json
import os

from grail.probe.schema import derive_rng

_CACHE: dict[str, dict] = {}


# --- loading ----------------------------------------------------------------
def load_pack(name: str, stimulus_dir: str) -> dict:
    """Load and validate a stimulus pack. Cached — packs are immutable inputs."""
    key = f"{stimulus_dir}::{name}"
    if key in _CACHE:
        return _CACHE[key]
    path = os.path.join(stimulus_dir, name, "pack.json")
    if not os.path.exists(path):
        raise SystemExit(
            f"No stimulus pack '{name}' at {path}. A sub-domain needs a pack "
            "before it can be probed — see data/stimuli/credit/pack.json.")
    with open(path, encoding="utf-8") as fh:
        pack = json.load(fh)
    _validate(pack, path)
    _CACHE[key] = pack
    return pack


def _validate(pack: dict, path: str) -> None:
    is_records = (pack.get("source") or {}).get("type") == "records"
    required = ["name", "outcome", "strata", "render", "compose"]
    if not is_records:
        # a sampled pack builds cases from vocabulary and field specs; a
        # record-backed one gets both from the dataset
        required += ["vocab", "fields"]
    for key in required:
        if key not in pack:
            raise SystemExit(f"stimulus pack {path} is missing '{key}'")
    if pack["outcome"].get("type") not in ("binary", "continuous"):
        raise SystemExit(f"stimulus pack {path}: outcome.type must be binary or continuous")
    en = pack["render"].get("en", {})
    for key in ("header", "fields", "decide"):
        if key not in en:
            raise SystemExit(f"stimulus pack {path}: render.en is missing '{key}'")
    if not pack.get("fields") and not is_records:
        raise SystemExit(
            f"stimulus pack {path}: declares no fields and no record source, so "
            "there is nothing to build a case from")
    if is_records and not pack["source"].get("licence"):
        raise SystemExit(
            f"stimulus pack {path}: a record source must record its licence and "
            "attribution — redistributing someone's dataset without them is not "
            "a detail to sort out later")


def strata_names(pack: dict) -> list[str]:
    return sorted(pack["strata"])


def outcome_type(pack: dict) -> str:
    return pack["outcome"]["type"]


# --- sampling ---------------------------------------------------------------
def _draw(r, field: dict, pack: dict, stratum_cfg: dict, slots: dict):
    kind = field["type"]

    if kind == "choice":
        return r.choice(pack["vocab"][field["vocab"]])

    if kind == "int_range":
        lo, hi = field["fixed"] if "fixed" in field else stratum_cfg[field["range"]]
        return r.randint(lo, hi)

    if kind == "int_step":
        lo, hi = field["fixed"] if "fixed" in field else stratum_cfg[field["range"]]
        return r.randrange(lo, hi + 1, field.get("step", 1))

    if kind == "scaled":
        base = slots[field["base"]]
        lo, hi = stratum_cfg[field["frac"]]
        unit = field.get("unit", 1)
        divisor = field.get("divisor", 1)
        return int(round(base * r.uniform(lo, hi) / divisor / float(unit)) * unit)

    raise SystemExit(f"stimulus pack declares unknown field type '{kind}'")


def records_path(pack: dict, root: str = "") -> str:
    rel = pack["source"]["path"]
    return os.path.join(root, rel) if root else rel


def sample_case(pack: dict, seed: int, domain: str, index: int, stratum: str,
                ns: str = "case", root: str = "") -> dict:
    """Deterministically produce one case from a pack.

    Two kinds of pack, one entry point. A *sampled* pack draws each field from
    the ranges it declares; a *record-backed* pack draws a real applicant from a
    dataset. Generators call this and never know which they got, which is what
    lets real records replace synthetic profiles without touching a generator.

    Either way the RNG is derived from (seed, domain, ns, index, stratum) and
    **never** from the protected arm, so the same case is reproduced identically
    for every arm. Fields are drawn in the order the pack declares them, so the
    draw sequence — and therefore the whole probe set — is reproducible.
    """
    if stratum not in pack["strata"]:
        raise SystemExit(f"pack '{pack['name']}' has no stratum '{stratum}' "
                         f"(has: {strata_names(pack)})")

    source = pack.get("source") or {}
    if source.get("type") == "records":
        from grail.probe.records import sample_record_case
        return sample_record_case(pack, seed, domain, index, stratum, ns,
                                  records_path(pack, root))

    r = derive_rng(seed, domain, ns, index, stratum)
    cfg = pack["strata"][stratum]

    slots: dict = {"ref": f"{pack.get('case_prefix', 'CS')}-{index:05d}"}
    slots.update(pack.get("axis_slot_defaults", {}))
    for field in pack["fields"]:
        slots[field["name"]] = _draw(r, field, pack, cfg, slots)
    slots["stratum"] = stratum
    return slots


# --- rendering --------------------------------------------------------------
def _composed(pack: dict, slots: dict) -> dict:
    out = dict(slots)
    for name, template in pack["compose"].items():
        out[name] = template.format(**{k: slots.get(k, "") for k in _keys(template)}).strip()
        out[name] = " ".join(out[name].split())   # collapse the gap an empty slot leaves
    return out


def _keys(template: str) -> list[str]:
    import re
    return re.findall(r"\{(\w+)\}", template)


def render(pack: dict, slots: dict, instruction: str | None = None,
           lang: str = "en") -> str:
    """Render one prompt from a pack. `slots` is the case plus any arm override."""
    block = pack["render"].get(lang)
    if block is None:
        raise SystemExit(f"pack '{pack['name']}' has no '{lang}' rendering")
    local = dict(slots)
    if lang != "en":
        title_map = block.get("title_map", {})
        local["title"] = title_map.get(local.get("title", ""), local.get("title", ""))
    local = _composed(pack, local)
    fields = block["fields"].format(**local)
    return f"{block['header']}\n\n{fields}\n\n{instruction or block['decide']}"


def instruction(pack: dict, kind: str = "decide", index: int = 0,
                lang: str = "en") -> str:
    block = pack["render"][lang]
    if kind == "paraphrase":
        paras = block.get("paraphrases") or [block["decide"]]
        return paras[index % len(paras)]
    return block.get(kind, block["decide"])


def n_paraphrases(pack: dict, lang: str = "en") -> int:
    return len(pack["render"][lang].get("paraphrases") or [pack["render"][lang]["decide"]])


# --- meaning-preserving perturbations (sub-domain independent) --------------
# Every perturbation must leave the digit multiset of the prompt unchanged. That
# is asserted in the generator, so a perturbation that quietly changed a number
# could never reach a probe file. None of these know anything about the pack.

def p_extra_whitespace(text: str, r) -> str:
    return text.replace(": ", ":  ")


def p_smart_quotes(text: str, r) -> str:
    return text.replace("'", "’").replace('"', "”")


def p_filler_prefix(text: str, r) -> str:
    return "Quick one for you.\n\n" + text


def p_label_casing(text: str, r) -> str:
    out = []
    for line in text.split("\n"):
        if ": " in line and not line.startswith("Answer"):
            label, _, rest = line.partition(": ")
            out.append(label.upper() + ": " + rest)
        else:
            out.append(line)
    return "\n".join(out)


def p_typo(text: str, r) -> str:
    """One adjacent-character transposition in a purely alphabetic word.

    First and last characters are left alone (the classic readable typo), and the
    swapped pair must actually differ — transposing the 'ss' in "assisting" would
    return the word unchanged and quietly produce a duplicate of the base probe
    rather than a perturbation of it.
    """
    words = text.split(" ")
    candidates = [i for i, w in enumerate(words)
                  if w.isalpha() and len(w) >= 5 and w.upper() != w]
    r.shuffle(candidates)
    for i in candidates:
        w = words[i]
        positions = [j for j in range(1, len(w) - 2) if w[j] != w[j + 1]]
        if not positions:
            continue
        j = positions[r.randrange(len(positions))]
        words[i] = w[:j] + w[j + 1] + w[j] + w[j + 2:]
        return " ".join(words)
    return text


def p_field_reorder(text: str, r) -> str:
    """Reorder the independent field lines; header and instruction stay put."""
    parts = text.split("\n\n")
    if len(parts) < 3:
        return text
    lines = parts[1].split("\n")
    order = list(range(len(lines)))
    r.shuffle(order)
    parts[1] = "\n".join(lines[i] for i in order)
    return "\n\n".join(parts)


PERTURBATIONS = [
    ("extra_whitespace", p_extra_whitespace),
    ("smart_quotes", p_smart_quotes),
    ("filler_prefix", p_filler_prefix),
    ("label_casing", p_label_casing),
    ("typo", p_typo),
    ("field_reorder", p_field_reorder),
]


# --- truthfulness framings (declared by the pack) ---------------------------
# The framings wrap a seed-bank question in context — a branch conversation, or
# social pressure toward a lure. That context is sub-domain specific (a lending
# desk in credit, a pricing desk in insurance), so the wording lives in the pack
# and only the mechanism lives here.

_DEFAULT_FRAMINGS = [{"name": "neutral", "needs_lure": False, "template": "{question}"}]


def framings(pack: dict) -> list[dict]:
    """Framings in the order the pack declares them (order is part of the seed)."""
    declared = pack.get("framings") or _DEFAULT_FRAMINGS
    for f in declared:
        if "{question}" not in f["template"]:
            raise SystemExit(
                f"pack '{pack['name']}': framing '{f['name']}' does not include "
                "{question}, so the probe would put pressure on nothing")
        if f.get("needs_lure") and "{lure}" not in f["template"]:
            raise SystemExit(
                f"pack '{pack['name']}': framing '{f['name']}' claims to need a "
                "lure but never renders one")
    return declared


def apply_framing(framing: dict, question: str, lure: str | None) -> str:
    return framing["template"].format(question=question, lure=lure or "")


def seed_files(pack: dict) -> list[str]:
    """Which truthfulness seed banks belong to this sub-domain."""
    return list(pack.get("seed_files") or [])


def case_family(pack: dict) -> str:
    """The family label for a whole-case probe — `credit_application` etc.

    Hard-coding this was a real leak: an insurance probe set would have reported
    1310 probes in a family called `credit_application`, wrong in the manifest
    while every prompt was correct.
    """
    return pack.get("case_family", f"{pack['name']}_case")
