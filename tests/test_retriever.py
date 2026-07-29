import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from grail.ingest.clause_parser import parse_file
from grail.ingest.linker import link_units
from grail.index.hybrid_index import HybridIndex
from grail.retrieve.retriever import Retriever
from config import RAW_DIR, INSTRUMENT
import glob


def _build():
    units = []
    for p in sorted(glob.glob(os.path.join(RAW_DIR, "*.txt"))):
        units.extend(parse_file(p, INSTRUMENT))
    units = link_units(units)
    return Retriever(HybridIndex.build(units))


def test_retrieves_bias_obligation():
    r = _build()
    res = r.retrieve("the model shows bias against a protected group in its outputs")
    cites = [x.obligation.citation for x in res]
    # Article 10(2)(f)/(g) are the bias-examination / mitigation obligations
    assert any("10(2)(f)" in c or "10(2)(g)" in c for c in cites), cites


def test_only_probeable_partitions_returned():
    r = _build()
    res = r.retrieve("record keeping logs technical documentation")
    # procedural clauses (Art 11/12) must never be returned as obligations
    for x in res:
        assert x.obligation.scope_partition in ("behavioral", "hybrid")


def test_expansion_attaches_context():
    r = _build()
    res = r.retrieve("bias in training data may cause discrimination")
    # at least one retrieved obligation carries a definition or exception
    assert any(x.definitions or x.exceptions for x in res)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn(); print("ok", name)
