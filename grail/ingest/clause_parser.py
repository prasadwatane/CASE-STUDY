"""Deterministic structural parser for EU-AI-Act-style legal text.

IMPORTANT (v3 correction): this is NOT RAG. Clauses are extracted by
STRUCTURAL parsing of the official text. Each Article -> Paragraph -> Point is
the smallest legal unit; obligations at Article 10(2)(b) granularity are stored
individually so later compliance checking is precise.

Recognised structure
--------------------
    Article 10                      -> container (article)
    Data and data governance        -> heading (line after "Article N")
    1. ....                         -> paragraph "1"
    (a) ....                        -> point "a" under current paragraph
        (i) ....                    -> subpoint "i" under current point
    ANNEX III                       -> container (annex)
    5. High-risk AI ...             -> annex item "5"
    (b) ....                        -> point "b" under annex item

A paragraph that has points also keeps its intro text as a CHAPEAU unit, so a
point can be read together with its parent for meaning. Points link to their
chapeau via parent_id.
"""
from __future__ import annotations
import re

from grail.ingest.schema import (
    LegalUnit, OBLIGATION, DEFINITION, EXCEPTION, SCOPE, CHAPEAU,
)
from grail.scope.partition import infer_partition

# --- line patterns ----------------------------------------------------------
RE_ARTICLE = re.compile(r"^Article\s+(\d+)\s*$", re.I)
RE_ANNEX = re.compile(r"^ANNEX\s+([IVXLC]+)\s*$", re.I)
RE_PARA = re.compile(r"^(\d+)\.\s+(.*)$")
RE_PARA_ALONE = re.compile(r"^(\d+)\.\s*$")   # official PDF: number on its own line
# One matcher for any bracketed lettering; point-vs-subpoint is disambiguated
# in code, because letters like (c)/(i)/(v)/(x) are ambiguous with roman numerals.
RE_BRACKET = re.compile(r"^\(([a-z]{1,4})\)\s+(.*)$")
# Article 3 numbers its definitions "(1) 'term' means ...": parenthesised digits.
RE_NUMPOINT = re.compile(r"^\((\d+)\)\s+(.*)$")
_ROMAN = set("ivxlcdm")


def _is_roman(tok: str) -> bool:
    return len(tok) > 0 and all(ch in _ROMAN for ch in tok)


def _successor(tok: str) -> str | None:
    return chr(ord(tok) + 1) if len(tok) == 1 else None

# --- semantics --------------------------------------------------------------
RE_DEF = re.compile(r"^[‘'\"]?(.+?)[’'\"]?\s+means\b", re.I)
RE_EXCEPTION = re.compile(
    r"\b(shall not apply|does not apply|shall not be considered|"
    r"with the exception of|except (?:where|for|that)|unless|"
    r"is not subject to|has been placed on the market for the sole purpose)\b",
    re.I)
RE_SCOPE = re.compile(
    r"\b(shall be considered (?:to be )?high-risk|classified as high-risk|"
    r"the following.*shall be)\b", re.I)


def _classify(text: str, container: str) -> str:
    if container.lower().startswith("article 3"):
        if RE_DEF.search(text):
            return DEFINITION
    if RE_EXCEPTION.search(text):
        return EXCEPTION
    if RE_SCOPE.search(text):
        return SCOPE
    return OBLIGATION


def _defined_term(text: str) -> str | None:
    m = RE_DEF.search(text)
    return m.group(1).strip() if m else None


def parse_text(raw: str, instrument: str) -> list[LegalUnit]:
    """Parse one official text blob into legal units. Deterministic; no model."""
    units: list[LegalUnit] = []

    container = None          # "Article 10" / "Annex III"
    article_no = None
    annex_no = None
    heading = None
    cur_para = None           # paragraph number as str
    cur_para_chapeau_id = None
    cur_point = None
    cur_point_id = None
    expect_heading = False

    def prefix() -> str:
        return "AIA:" if article_no is not None else "AIA:"

    def mk_id(para=None, point=None, sub=None) -> tuple[str, str]:
        """Return (stable_id, human_citation)."""
        if article_no is not None:
            head = f"Art{article_no}"
            cite = f"Article {article_no}"
        else:
            head = f"Annex{annex_no}"
            cite = f"Annex {annex_no}"
        if para is not None:
            head += f"({para})"; cite += f"({para})"
        if point is not None:
            head += f"({point})"; cite += f"({point})"
        if sub is not None:
            head += f"({sub})"; cite += f"({sub})"
        return f"AIA:{head}", cite

    def add(text, para, point, sub, parent_id) -> LegalUnit:
        sid, cite = mk_id(para, point, sub)
        utype = _classify(text, container or "")
        u = LegalUnit(
            id=sid, citation=cite, instrument=instrument,
            container=container or "", article=article_no, annex=annex_no,
            paragraph=para, point=point, subpoint=sub, heading=heading,
            parent_id=parent_id, text=text.strip(),
            unit_type=utype,
            defined_term=_defined_term(text) if utype == DEFINITION else None,
            scope_partition=infer_partition(text),
            authority="binding", tier=1, lang="en",
        )
        units.append(u)
        return u

    for line in raw.splitlines():
        line = line.rstrip()
        if not line.strip():
            continue

        m = RE_ARTICLE.match(line.strip())
        if m:
            article_no = int(m.group(1)); annex_no = None
            container = f"Article {article_no}"
            heading = None; cur_para = None; cur_point = None
            cur_para_chapeau_id = None; expect_heading = True
            continue

        m = RE_ANNEX.match(line.strip())
        if m:
            annex_no = m.group(1); article_no = None
            container = f"Annex {annex_no}"
            heading = None; cur_para = None; cur_point = None
            cur_para_chapeau_id = None; expect_heading = True
            continue

        # The line right after "Article N" (not itself a numbered para) = heading.
        if expect_heading:
            expect_heading = False
            if not RE_PARA.match(line.strip()):
                heading = line.strip()
                continue

        m = RE_PARA.match(line.strip())
        if m and container is not None:
            cur_para = m.group(1)
            cur_point = None
            cur_point_id = None
            u = add(m.group(2), cur_para, None, None, parent_id=None)
            # Provisionally the paragraph is its own unit; if points follow it
            # becomes their chapeau (marked below).
            cur_para_chapeau_id = u.id
            continue

        m = RE_PARA_ALONE.match(line.strip())
        if m and container is not None:
            # Paragraph number on its own line; text arrives on following lines
            # and is appended by the continuation rule below.
            cur_para = m.group(1)
            cur_point = None
            cur_point_id = None
            u = add("", cur_para, None, None, parent_id=None)
            cur_para_chapeau_id = u.id
            continue

        m = RE_NUMPOINT.match(line.strip())
        if m and container is not None:
            # Parenthesised-number item (Article 3 definitions). Always a point.
            for u in units:
                if u.id == cur_para_chapeau_id and u.unit_type == OBLIGATION:
                    u.unit_type = CHAPEAU
            cur_point = m.group(1)
            pu = add(m.group(2), cur_para, cur_point, None,
                     parent_id=cur_para_chapeau_id)
            cur_point_id = pu.id
            continue

        m = RE_BRACKET.match(line.strip())
        if m:
            tok, body = m.group(1), m.group(2)
            # Disambiguate point vs roman subpoint:
            #  - non-roman token          -> always a point
            #  - roman token that is the alphabetical successor of the current
            #    point (e.g. (b)->(c))    -> a point
            #  - any other roman token while inside a point -> a subpoint
            is_sub = (
                cur_point is not None
                and _is_roman(tok)
                and tok != _successor(cur_point)
            )
            if is_sub:
                add(body, cur_para, cur_point, tok, parent_id=cur_point_id)
            else:
                # first point under this paragraph => paragraph becomes a chapeau
                for u in units:
                    if u.id == cur_para_chapeau_id and u.unit_type == OBLIGATION:
                        u.unit_type = CHAPEAU
                cur_point = tok
                pu = add(body, cur_para, cur_point, None,
                         parent_id=cur_para_chapeau_id)
                cur_point_id = pu.id
            continue

        # Continuation line: append to the most recent unit, but only if that
        # unit belongs to the CURRENT container (guards against page-break text
        # from a previous article/annex leaking across a boundary).
        if units and units[-1].container == (container or ""):
            units[-1].text = (units[-1].text + " " + line.strip()).strip()

    # Post-pass: classify on the FULL assembled text. During streaming a unit is
    # created from its first line only, so an exception clause or a definition
    # that arrives on a continuation line would otherwise be missed.
    for u in units:
        if u.unit_type == CHAPEAU:
            continue                     # structural role, keep it
        u.unit_type = _classify(u.text, u.container)
        u.defined_term = (_defined_term(u.text)
                          if u.unit_type == DEFINITION else None)
        u.scope_partition = infer_partition(u.text)

    return units


def parse_file(path: str, instrument: str) -> list[LegalUnit]:
    with open(path, encoding="utf-8") as fh:
        return parse_text(fh.read(), instrument)
