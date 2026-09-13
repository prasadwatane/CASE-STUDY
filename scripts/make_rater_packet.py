"""Build a single self-contained HTML file the second rater can just open.

The second rater is not going to clone a repository, install Python, or edit a
CSV whose prompt cells are two thousand characters wide. They need one file that
opens in a browser, shows one item at a time, and gives back something that can
be scored.

So this bakes the sheet AND the frozen guidelines into one HTML document with no
external dependencies — no network, no fonts, no scripts from anywhere. It runs
from a Downloads folder on a machine that has never heard of this project.

    python scripts/make_rater_packet.py \\
        data/processed/annotation/pilot/annotation_rater_B.csv \\
        --guidelines docs/annotation_guidelines_Art13.md

Three properties matter and are deliberate:

**Blind.** The file contains the prompt and the response and nothing else. No
model identity, no probe id, no judge verdict — the same blinding the CSV has,
preserved rather than re-derived.

**Cannot lose work.** Every answer is written to localStorage immediately, and
the page refuses to pretend that is a backup: it shows an unsaved-work warning
until the CSV has been downloaded.

**Gives back exactly what the scorer reads.** The download is the same CSV, same
columns, same item tokens. The rater sends one file back and it drops straight
into the annotation directory.
"""
from __future__ import annotations

import argparse
import csv
import html
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

TEMPLATE = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Annotation — Article 13(1) transparency</title>
<style>
 :root {{ --ink:#1a1a1a; --dim:#6b6b6b; --line:#e0ddd6; --bg:#faf9f6;
          --accent:#2d5016; --warn:#8a5a00; }}
 * {{ box-sizing:border-box; }}
 body {{ margin:0; background:var(--bg); color:var(--ink);
         font:16px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif; }}
 header {{ position:sticky; top:0; background:var(--bg); border-bottom:1px solid var(--line);
           padding:12px 20px; z-index:10; }}
 .bar {{ height:4px; background:var(--line); border-radius:2px; overflow:hidden; margin-top:8px; }}
 .bar > div {{ height:100%; background:var(--accent); width:0; transition:width .2s; }}
 .row {{ display:flex; justify-content:space-between; align-items:center; gap:16px;
         flex-wrap:wrap; }}
 main {{ max-width:820px; margin:0 auto; padding:24px 20px 120px; }}
 h1 {{ font-size:17px; margin:0; font-weight:600; }}
 h2 {{ font-size:12px; letter-spacing:.09em; text-transform:uppercase;
       color:var(--dim); margin:28px 0 8px; font-weight:600; }}
 pre {{ white-space:pre-wrap; word-wrap:break-word; background:#fff;
        border:1px solid var(--line); border-radius:6px; padding:16px;
        font:15px/1.65 ui-monospace,SFMono-Regular,Menlo,monospace; margin:0; }}
 .resp {{ border-left:3px solid var(--accent); }}
 footer {{ position:fixed; bottom:0; left:0; right:0; background:var(--bg);
           border-top:1px solid var(--line); padding:14px 20px; }}
 .acts {{ max-width:820px; margin:0 auto; display:flex; gap:10px; flex-wrap:wrap;
          align-items:center; }}
 button {{ font:inherit; padding:10px 18px; border-radius:6px; cursor:pointer;
           border:1px solid var(--line); background:#fff; color:var(--ink); }}
 button:hover {{ border-color:var(--dim); }}
 button.sel {{ background:var(--accent); color:#fff; border-color:var(--accent); }}
 .ghost {{ color:var(--dim); }}
 #note {{ flex:1; min-width:200px; padding:10px; border:1px solid var(--line);
          border-radius:6px; font:inherit; }}
 #dl {{ background:var(--accent); color:#fff; border-color:var(--accent); font-weight:600; }}
 .unsaved {{ color:var(--warn); font-size:14px; }}
 details {{ background:#fff; border:1px solid var(--line); border-radius:6px;
            padding:12px 16px; margin-bottom:20px; }}
 summary {{ cursor:pointer; font-weight:600; font-size:14px; }}
 .g {{ font-size:14px; }} .g table {{ border-collapse:collapse; width:100%; margin:8px 0; }}
 .g td, .g th {{ border:1px solid var(--line); padding:6px 8px; text-align:left;
                 vertical-align:top; }}
 .done {{ text-align:center; padding:60px 20px; }}
</style></head><body>

<header><div class="row">
  <h1>Article 13(1) — is this explanation adequate?</h1>
  <span class="ghost" id="count"></span>
</div><div class="bar"><div id="fill"></div></div></header>

<main>
  <details><summary>The rules — read once before you start</summary>
    <div class="g">{guidelines}</div>
  </details>
  <div id="card"></div>
</main>

<footer><div class="acts">
  <button data-v="adequate">1 &nbsp;Adequate</button>
  <button data-v="inadequate">2 &nbsp;Inadequate</button>
  <button data-v="cannot judge">3 &nbsp;Cannot judge</button>
  <input id="note" placeholder="note (optional)">
  <button id="back" class="ghost">&larr;</button>
  <button id="dl">Download CSV</button>
  <span class="unsaved" id="warn"></span>
</div></footer>

<script>
const ITEMS = {items};
const KEY = "grail-annot-{sheet_key}";
let ratings = {{}}, notes = {{}}, i = 0, dirty = false;

try {{
  const s = JSON.parse(localStorage.getItem(KEY) || "{{}}");
  ratings = s.ratings || {{}}; notes = s.notes || {{}};
}} catch (e) {{ /* private mode, or file:// with storage off — memory only */ }}

function persist() {{
  dirty = true;
  try {{ localStorage.setItem(KEY, JSON.stringify({{ratings, notes}})); }} catch (e) {{}}
  paint();
}}

function esc(s) {{
  return (s||"").replace(/[&<>]/g, c => ({{"&":"&amp;","<":"&lt;",">":"&gt;"}}[c]));
}}

function paint() {{
  const n = Object.keys(ratings).length;
  document.getElementById("count").textContent = n + " of " + ITEMS.length + " rated";
  document.getElementById("fill").style.width = (100*n/ITEMS.length) + "%";
  document.getElementById("warn").textContent =
    (dirty && n > 0) ? "not yet downloaded" : "";
  document.querySelectorAll("[data-v]").forEach(b =>
    b.classList.toggle("sel", ITEMS[i] && ratings[ITEMS[i].item] === b.dataset.v));
}}

function show() {{
  if (i >= ITEMS.length) {{
    document.getElementById("card").innerHTML =
      '<div class="done"><h2>All items rated</h2>' +
      '<p>Press <b>Download CSV</b> below and send that file back.</p></div>';
    paint(); return;
  }}
  const it = ITEMS[i];
  document.getElementById("card").innerHTML =
    '<h2>Item ' + (i+1) + ' of ' + ITEMS.length + ' &nbsp;·&nbsp; ' + esc(it.item) + '</h2>' +
    '<h2>The application</h2><pre>' + esc(it.prompt) + '</pre>' +
    '<h2>The response</h2><pre class="resp">' + esc(it.response) + '</pre>';
  document.getElementById("note").value = notes[it.item] || "";
  window.scrollTo(0,0);
  paint();
}}

function rate(v) {{
  if (i >= ITEMS.length) return;
  const it = ITEMS[i];
  ratings[it.item] = v;
  const nt = document.getElementById("note").value.trim();
  if (nt) notes[it.item] = nt; else delete notes[it.item];
  persist();
  i++; show();
}}

document.querySelectorAll("[data-v]").forEach(b =>
  b.onclick = () => rate(b.dataset.v));
document.getElementById("back").onclick = () => {{ if (i>0) {{ i--; show(); }} }};

document.addEventListener("keydown", e => {{
  if (e.target.tagName === "INPUT") return;
  if (e.key === "1") rate("adequate");
  if (e.key === "2") rate("inadequate");
  if (e.key === "3") rate("cannot judge");
  if (e.key === "ArrowLeft" && i>0) {{ i--; show(); }}
}});

function csvCell(s) {{ return '"' + String(s||"").replace(/"/g,'""') + '"'; }}

document.getElementById("dl").onclick = () => {{
  const head = ["item","dimension","criterion","prompt","response","rating","notes"];
  const lines = [head.join(",")];
  for (const it of ITEMS) lines.push([
    it.item, it.dimension, it.criterion, it.prompt, it.response,
    ratings[it.item] || "", notes[it.item] || ""
  ].map(csvCell).join(","));
  const blob = new Blob([lines.join("\\n")], {{type:"text/csv;charset=utf-8"}});
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "{download_name}";
  a.click();
  dirty = false; paint();
}};

window.addEventListener("beforeunload", e => {{
  if (dirty && Object.keys(ratings).length) {{ e.preventDefault(); e.returnValue = ""; }}
}});

// resume where they stopped
i = ITEMS.findIndex(it => !ratings[it.item]);
if (i < 0) i = ITEMS.length;
show();
</script></body></html>
"""


def guidelines_html(path: str) -> str:
    """Very small markdown subset — enough for the guidelines, no dependency."""
    if not path or not os.path.exists(path):
        return "<p>Guidelines not embedded. Ask the study lead for them.</p>"
    out, in_table, in_list = [], False, False
    for line in open(path, encoding="utf-8").read().splitlines():
        s = line.rstrip()
        if s.startswith("|"):
            cells = [c.strip() for c in s.strip("|").split("|")]
            if set("".join(cells)) <= set("-: "):
                continue
            if not in_table:
                out.append("<table>")
                in_table = True
            tag = "td"
            out.append("<tr>" + "".join(f"<{tag}>{_inline(c)}</{tag}>"
                                        for c in cells) + "</tr>")
            continue
        if in_table:
            out.append("</table>")
            in_table = False
        if s.startswith("#"):
            lvl = len(s) - len(s.lstrip("#"))
            out.append(f"<h{min(lvl+2,6)}>{_inline(s.lstrip('# '))}</h{min(lvl+2,6)}>")
        elif s.startswith(("- ", "* ")):
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append(f"<li>{_inline(s[2:])}</li>")
        elif not s.strip():
            if in_list:
                out.append("</ul>")
                in_list = False
        elif s.startswith("---"):
            out.append("<hr>")
        else:
            out.append(f"<p>{_inline(s)}</p>")
    if in_list:
        out.append("</ul>")
    if in_table:
        out.append("</table>")
    return "\n".join(out)


def _inline(s: str) -> str:
    s = html.escape(s)
    for mark, tag in (("**", "b"), ("*", "i"), ("`", "code")):
        parts = s.split(mark)
        if len(parts) > 2:
            s = parts[0] + "".join(
                f"<{tag}>{p}</{tag}>" + q
                for p, q in zip(parts[1::2], parts[2::2] + [""]))
    return s


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("sheet")
    ap.add_argument("--guidelines", default="docs/annotation_guidelines_Art13.md")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    with open(args.sheet, encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        raise SystemExit(f"{args.sheet} has no items.")

    name = os.path.basename(args.sheet)
    out_path = args.out or os.path.join(os.path.dirname(args.sheet),
                                        name.replace(".csv", ".html"))

    page = TEMPLATE.format(
        items=json.dumps([{k: r.get(k, "") for k in
                           ("item", "dimension", "criterion", "prompt", "response")}
                          for r in rows], ensure_ascii=False),
        guidelines=guidelines_html(args.guidelines),
        sheet_key=name.replace(".csv", ""),
        download_name=name)

    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(page)

    kb = os.path.getsize(out_path) / 1024
    print(f"Rater packet -> {out_path}  ({kb:.0f} KB, {len(rows)} items)")
    print("  Self-contained: no network, no install. Send this ONE file.")
    print("  The rater opens it, labels, presses Download CSV, sends that back.")
    print(f"  Put the returned {name} in {os.path.dirname(args.sheet)}/ and score.")


if __name__ == "__main__":
    main()
