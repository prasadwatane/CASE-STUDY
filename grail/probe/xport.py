"""A small reader for SAS transport (XPORT version 5) files, standard library only.

NHANES publishes every data file in this format. pandas can read it, but the
pipeline's core runs on numpy alone, and a 120-line reader is a better trade than
a new dependency for one import step. The import script cross-checks this reader
against pandas whenever pandas happens to be installed, and records the result.

Format (SAS TS-140): 80-byte header records; one 140-byte NAMESTR per variable;
observations packed back to back and blank-padded to a multiple of 80 bytes.
Numbers are IBM System/370 hexadecimal floating point, big-endian, stored in 2 to
8 bytes (shorter ones are truncated on the right). A missing value is "." or a
letter or "_" in the first byte followed by zero bytes.
"""
from __future__ import annotations

import struct

_LIBRARY = b"HEADER RECORD*******LIBRARY HEADER RECORD!!!!!!!"
_MEMBER = b"HEADER RECORD*******MEMBER  HEADER RECORD!!!!!!!"
_DSCRPTR = b"HEADER RECORD*******DSCRPTR HEADER RECORD!!!!!!!"
_NAMESTR = b"HEADER RECORD*******NAMESTR HEADER RECORD!!!!!!!"
_OBS = b"HEADER RECORD*******OBS     HEADER RECORD!!!!!!!"

# ntype, nhfun, nlng, nvar0, nname, nlabel, nform, nfl, nfd, nfj, nfill, niform,
# nifl, nifd, npos  (the remaining 52 bytes of the 140 are unused)
_NAMESTR_FMT = ">hhhh8s40s8shhh2s8shhl"
_MISSING_FIRST = {0x2E, 0x5F} | set(range(0x41, 0x5B))     # ".", "_", "A".."Z"


def is_xport(head: bytes) -> bool:
    return head.startswith(_LIBRARY)


def ibm_to_float(raw: bytes):
    """IBM hex float (2-8 bytes, big-endian) -> Python float; None if missing."""
    b = raw + b"\x00" * (8 - len(raw))
    if b[0] in _MISSING_FIRST and not any(b[1:]):
        return None
    word = int.from_bytes(b, "big")
    mantissa = word & 0x00FFFFFFFFFFFFFF
    if mantissa == 0:
        return 0.0
    sign = -1.0 if b[0] & 0x80 else 1.0
    exponent = (b[0] & 0x7F) - 64
    # mantissa / 2**56 is the hexadecimal fraction; the conversion to a double
    # rounds once (int -> float), the rest is exact scaling by powers of two
    return sign * (mantissa / float(1 << 56)) * (16.0 ** exponent)


def read_xport(path: str, columns=None) -> dict:
    """Read the first member of an XPORT file.

    Returns {"name", "label", "variables": [{name, type, length, label}],
    "columns": {name: [values]}, "n": rows}. Numeric values are floats or None;
    character values are stripped strings or None when blank. `columns`, if
    given, limits the returned columns (unknown names are simply absent, so the
    caller can tell which requested variables a cycle does not carry).
    """
    with open(path, "rb") as fh:
        data = fh.read()
    if not is_xport(data[:80]):
        raise ValueError(f"{path}: not a SAS transport (XPORT v5) file")

    pos = 3 * 80                                   # library header + 2 real headers
    if data[pos:pos + 48] != _MEMBER:
        raise ValueError(f"{path}: member header missing")
    namestr_len = int(data[pos + 74:pos + 78])     # 140, or 136 on VAX/VMS
    if data[pos + 80:pos + 128] != _DSCRPTR:
        raise ValueError(f"{path}: descriptor header missing")
    member = data[pos + 160:pos + 240]
    ds_name = member[8:16].decode("latin-1").strip()
    ds_label = data[pos + 240 + 32:pos + 240 + 72].decode("latin-1").strip()

    pos += 320
    if data[pos:pos + 48] != _NAMESTR:
        raise ValueError(f"{path}: NAMESTR header missing")
    nvars = int(data[pos + 54:pos + 58])
    pos += 80

    variables = []
    for i in range(nvars):
        (ntype, _hf, nlng, _v0, nname, nlabel, _nf, _nfl, _nfd, _nfj, _fill,
         _nif, _nifl, _nifd, npos) = struct.unpack_from(_NAMESTR_FMT, data, pos + i * namestr_len)
        variables.append({"name": nname.decode("latin-1").strip(),
                          "type": "numeric" if ntype == 1 else "char",
                          "length": nlng, "position": npos,
                          "label": nlabel.decode("latin-1").strip()})
    block = nvars * namestr_len
    pos += block + (-block) % 80                   # NAMESTRs are padded to 80

    if data[pos:pos + 48] != _OBS:
        raise ValueError(f"{path}: observation header missing")
    pos += 80
    end = data.find(_MEMBER, pos)                  # a second member, if any
    end = len(data) if end < 0 else end

    obs_len = sum(v["length"] for v in variables)
    n = (end - pos) // obs_len if obs_len else 0
    blank = b" " * obs_len
    while n and data[pos + (n - 1) * obs_len:pos + n * obs_len] == blank:
        n -= 1                                     # trailing blank padding

    wanted = [v for v in variables if columns is None or v["name"] in set(columns)]
    out = {v["name"]: [] for v in wanted}
    for row in range(n):
        base = pos + row * obs_len
        for v in wanted:
            raw = data[base + v["position"]:base + v["position"] + v["length"]]
            if v["type"] == "numeric":
                out[v["name"]].append(ibm_to_float(raw))
            else:
                s = raw.decode("latin-1").rstrip()
                out[v["name"]].append(s or None)
    return {"name": ds_name, "label": ds_label, "variables": variables,
            "columns": out, "n": n}


# ---------------------------------------------------------------- writing
# Only the tests use this: it builds small XPORT fixtures so the import can be
# exercised end to end without the network. It is checked against pandas'
# reader in tests/test_insurance_records.py when pandas is available.
def float_to_ibm(x) -> bytes:
    if x is None:
        return b"." + b"\x00" * 7
    if x == 0:
        return b"\x00" * 8
    sign = 0x80 if x < 0 else 0
    frac, exp = abs(float(x)), 0
    while frac >= 1.0:
        frac /= 16.0
        exp += 1
    while frac < 1.0 / 16.0:
        frac *= 16.0
        exp -= 1
    mant = int(round(frac * (1 << 56)))
    if mant >= 1 << 56:
        mant >>= 4
        exp += 1
    return bytes([sign | (exp + 64)]) + mant.to_bytes(7, "big")


def write_xport(path: str, name: str, columns: dict, labels: dict | None = None) -> None:
    """Write numeric columns ({name: [float|None]}) as a one-member XPORT file."""
    labels = labels or {}
    names = list(columns)
    n = len(next(iter(columns.values()))) if columns else 0

    def rec(s: bytes) -> bytes:
        return s.ljust(80, b" ")[:80]

    stamp = b"01JAN00:00:00:00"
    out = [rec(_LIBRARY + b"0" * 30),
           rec(b"SAS     SAS     SASLIB  9.4     X64_10PR" + b" " * 24 + stamp),
           rec(stamp),
           rec(_MEMBER + b"000000000000000001600000000140"),
           rec(_DSCRPTR + b"0" * 30),
           rec(b"SAS     " + name.encode().ljust(8) + b"SASDATA 9.4     X64_10PR"
               + b" " * 24 + stamp),
           rec(stamp + b" " * 16 + name.encode().ljust(40) + b" " * 8),
           rec(_NAMESTR + b"000000" + f"{len(names):04d}".encode() + b"0" * 20)]
    ns = b""
    for i, col in enumerate(names):
        ns += struct.pack(_NAMESTR_FMT, 1, 0, 8, i + 1, col.encode().ljust(8),
                          labels.get(col, col).encode().ljust(40)[:40], b" " * 8,
                          0, 0, 0, b"\x00\x00", b" " * 8, 0, 0, 8 * i) + b"\x00" * 52
    ns += b" " * ((-len(ns)) % 80)
    out.append(ns)
    out.append(rec(_OBS + b"0" * 30))
    body = b"".join(float_to_ibm(columns[c][r]) for r in range(n) for c in names)
    body += b" " * ((-len(body)) % 80)
    out.append(body)
    with open(path, "wb") as fh:
        fh.write(b"".join(out))
