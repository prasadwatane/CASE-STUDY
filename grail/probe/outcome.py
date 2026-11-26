"""Which answer tokens a binary probe uses, and which of them is favourable.

The jury originally hard-coded `FAVOURABLE = "APPROVE"`. That is a credit
assumption welded into the inspection stage: a pack with other answer tokens
would have parsed as unparseable or, worse, been scored as uniformly
unfavourable without any error. The tokens belong to the stimulus pack,
which already declares them under `outcome.tokens`; this module reads them.

Defaults reproduce the credit behaviour exactly (tokens APPROVE / DECLINE,
favourable = the first token), so nothing about the committed finance run
changes: no probe content, no hash, no verdict.
"""
from __future__ import annotations

from functools import lru_cache

DEFAULT_TOKENS = ("APPROVE", "DECLINE")


@lru_cache(maxsize=None)
def spec(domain: str | None) -> tuple[tuple[str, ...], str]:
    if domain is None:
        return DEFAULT_TOKENS, DEFAULT_TOKENS[0]
    from config import STIMULUS_DIR, STIMULUS_PACK
    name = STIMULUS_PACK.get(domain)
    if name is None:
        return DEFAULT_TOKENS, DEFAULT_TOKENS[0]
    from grail.probe.templates import load_pack
    out = load_pack(name, STIMULUS_DIR)["outcome"]
    if out.get("type") != "binary":
        return DEFAULT_TOKENS, DEFAULT_TOKENS[0]
    toks = tuple(t.upper() for t in (out.get("tokens") or DEFAULT_TOKENS))
    fav = (out.get("favourable") or toks[0]).upper()
    if fav not in toks:
        raise SystemExit(f"stimulus pack '{name}': favourable token '{fav}' "
                         f"is not one of its tokens {list(toks)}")
    return toks, fav


def tokens(domain: str | None) -> list[str]:
    return list(spec(domain)[0])


def favourable(domain: str | None) -> str:
    return spec(domain)[1]
