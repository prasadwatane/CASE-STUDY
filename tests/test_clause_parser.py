import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from grail.ingest.clause_parser import parse_text
from grail.ingest.schema import DEFINITION, EXCEPTION, CHAPEAU

SAMPLE = """Article 10
Data and data governance
1. High-risk AI systems shall be developed on the basis of data sets that meet quality criteria.
2. Data sets shall be subject to data governance practices. Those practices shall concern in particular:
(a) the relevant design choices;
(b) data collection processes and the origin of data.

ANNEX III
5. Access to essential services:
(b) AI systems intended to evaluate the creditworthiness of natural persons, with the exception of AI systems used for the purpose of detecting financial fraud;
"""


def _by_cite(units):
    return {u.citation: u for u in units}


def test_point_granularity():
    units = parse_text(SAMPLE, "TEST")
    cites = _by_cite(units)
    # smallest unit is the point, cited precisely
    assert "Article 10(2)(a)" in cites
    assert "Article 10(2)(b)" in cites
    assert "design choices" in cites["Article 10(2)(a)"].text


def test_chapeau_and_parent_link():
    units = parse_text(SAMPLE, "TEST")
    cites = _by_cite(units)
    # a paragraph that has points becomes a chapeau
    assert cites["Article 10(2)"].unit_type == CHAPEAU
    # the point links back to its chapeau
    assert cites["Article 10(2)(a)"].parent_id == cites["Article 10(2)"].id


def test_annex_and_exception():
    units = parse_text(SAMPLE, "TEST")
    cites = _by_cite(units)
    assert "Annex III(5)(b)" in cites
    # the fraud carve-out is detected as an exception
    assert cites["Annex III(5)(b)"].unit_type == EXCEPTION


def test_definition_detection():
    units = parse_text(
        "Article 3\nDefinitions\n67. ‘bias’ means a systematic difference in treatment.\n",
        "TEST")
    u = units[0]
    assert u.unit_type == DEFINITION
    assert u.defined_term == "bias"


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn(); print("ok", name)
