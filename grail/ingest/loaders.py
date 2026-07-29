"""Source loaders + cleaning for official OJ PDFs.

The official EU AI Act PDF (OJ L 2024/1689) extracts to text with:
  - a long preamble + recitals BEFORE the enacting terms,
  - page furniture injected mid-paragraph (page number NN/144, ELI url, the
    running "EN" and "OJ L, 12.7.2024" headers),
  - paragraph numbers on their OWN line ("1." then the text on the next line),
  - CHAPTER / SECTION / TITLE structural headings between articles.

`clean_oj_text` strips all of that and returns text the deterministic parser can
consume. This is still NOT RAG — it is mechanical normalization of the source.
"""
from __future__ import annotations
import re
import shutil
import subprocess

# Lines that are page furniture (drop them wherever they appear).
_FURNITURE = [
    re.compile(r"^\s*\d+\s*/\s*144\s*$"),          # 58/144
    re.compile(r"^\s*ELI:\s*http", re.I),          # ELI: http://data.europa.eu/...
    re.compile(r"^\s*EN\s*$"),                      # running language header
    re.compile(r"^\s*OJ\s+L,\s", re.I),            # OJ L, 12.7.2024
    re.compile(r"^\s*Official Journal", re.I),
    re.compile(r"^\s*of the European Union\s*$", re.I),
    re.compile(r"^\s*L series\s*$", re.I),
]
# Structural headings we do not want as obligation text.
_SKIP = re.compile(r"^\s*(CHAPTER|SECTION|TITLE)\b", re.I)
_ADOPT = "HAVE ADOPTED THIS REGULATION"

# Furniture that pdfplumber leaves INLINE (mid-sentence), not on its own line,
# so it must be scrubbed anywhere in a line, not just whole-line dropped.
_INLINE_FURNITURE = [
    re.compile(r"ELI:\s*http\S+", re.I),           # ELI: http://data.europa.eu/...
    re.compile(r"\b\d{1,3}\s*/\s*144\b"),          # page marker 136/144
    re.compile(r"\bOJ\s+L,\s*\d[\d.]*\b", re.I),   # OJ L, 12.7.2024
]


def load_pdf_text(path: str) -> str:
    """Extract text from a PDF. Prefers poppler's pdftotext; falls back to pdfplumber."""
    if shutil.which("pdftotext"):
        res = subprocess.run(["pdftotext", path, "-"],
                             capture_output=True, text=True, check=True)
        return res.stdout
    try:
        import pdfplumber  # lazy
        with pdfplumber.open(path) as pdf:
            return "\n".join((pg.extract_text() or "") for pg in pdf.pages)
    except ModuleNotFoundError:
        pass
    try:
        from pypdf import PdfReader  # lazy
        reader = PdfReader(path)
        return "\n".join((pg.extract_text() or "") for pg in reader.pages)
    except ModuleNotFoundError:
        raise SystemExit(
            "No PDF text extractor available. Install one of:\n"
            "  pip install pdfplumber      # recommended, pure-python\n"
            "  brew install poppler        # provides pdftotext (best layout)\n"
            "or convert the PDF to .txt and drop it in data/standards/raw/.")


def load_source_text(path: str) -> str:
    if path.lower().endswith(".pdf"):
        return load_pdf_text(path)
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def clean_oj_text(raw: str, drop_preamble: bool = True) -> str:
    """Return normalized text: enacting terms only, no furniture, no section heads."""
    lines = raw.splitlines()

    start = 0
    if drop_preamble:
        for i, l in enumerate(lines):
            if _ADOPT in l:
                start = i + 1
                break

    kept: list[str] = []
    for l in lines[start:]:
        if any(p.match(l) for p in _FURNITURE):
            continue
        if _SKIP.match(l):
            continue
        for pat in _INLINE_FURNITURE:              # scrub mid-line furniture
            l = pat.sub(" ", l)
        l = re.sub(r"\s{2,}", " ", l).rstrip().rstrip("`").rstrip()
        if l:
            kept.append(l)
    return "\n".join(kept)
