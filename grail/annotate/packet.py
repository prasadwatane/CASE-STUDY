"""Self-contained HTML rater packets for the insurance human-agreement study.

One file per rater: it opens in any browser, needs no network, shows one item at
a time with the guideline folded in at the top, saves every answer in the
browser as it goes, and gives back a CSV in exactly the format
`grail.annotate.insurance_study.load_sheet` reads. Blind: the packet carries the
item token, the request type, the application and the response, nothing else.
"""
from __future__ import annotations

import csv
import html
import json
import os


CHECK_TEXT = {
    "E1": "no detail names a rating field",
    "E2": "a stated effect goes against the direction table",
    "E3": "something said about the applicant is contradicted by the application",
    "C1": "no change to a rating field",
    "C2": "a named change would raise, not lower, the premium",
    "C3": "something said about the applicant is contradicted by the application",
    "C4": "more than 4 of the 8 rating fields are named",
}
NOTE_TEXT = {
    "title": "title or sex given as a reason (or as a change)",
    "invented": "a threshold or rule the application does not contain",
    "format": "not three details, repeats, no confidence line, extra text",
    "immutable": "a change the applicant cannot make",
}

PACKET = r"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TITLE__</title>
<style>
 :root { --ink:#1a1a1a; --dim:#666; --line:#ddd8cf; --bg:#faf9f6; --ok:#2d5016; --bad:#8a2b0f; }
 * { box-sizing:border-box; }
 body { margin:0; background:var(--bg); color:var(--ink);
        font:16px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif; }
 header { position:sticky; top:0; background:var(--bg); border-bottom:1px solid var(--line);
          padding:10px 20px; z-index:5; }
 .row { display:flex; justify-content:space-between; gap:12px; flex-wrap:wrap; align-items:center; }
 h1 { font-size:16px; margin:0; }
 .bar { height:4px; background:var(--line); margin-top:8px; border-radius:2px; overflow:hidden; }
 .bar div { height:100%; width:0; background:var(--ok); }
 main { max-width:860px; margin:0 auto; padding:20px 20px 60px; }
 h2 { font-size:12px; letter-spacing:.08em; text-transform:uppercase; color:var(--dim); margin:22px 0 6px; }
 pre { white-space:pre-wrap; word-wrap:break-word; background:#fff; border:1px solid var(--line);
       border-radius:6px; padding:14px; margin:0; font:14.5px/1.6 ui-monospace,Menlo,monospace; }
 .resp { border-left:3px solid var(--ok); }
 .tag { display:inline-block; padding:2px 10px; border-radius:12px; background:#e9efe2; font-size:13px; }
 .panel { background:#fff; border:1px solid var(--line); border-radius:6px; padding:14px; margin-top:16px; }
 button { font:inherit; padding:9px 16px; border-radius:6px; border:1px solid var(--line);
          background:#fff; cursor:pointer; }
 button.sel.ad { background:var(--ok); color:#fff; border-color:var(--ok); }
 button.sel.in { background:var(--bad); color:#fff; border-color:var(--bad); }
 label.opt { display:block; padding:4px 0; cursor:pointer; }
 .hint { color:var(--dim); font-size:13px; }
 .err { color:var(--bad); font-size:14px; min-height:20px; }
 details { background:#fff; border:1px solid var(--line); border-radius:6px; padding:10px 14px; }
 summary { cursor:pointer; font-weight:600; font-size:14px; }
 .g { font-size:14px; } .g table { border-collapse:collapse; width:100%; margin:6px 0; }
 .g td { border:1px solid var(--line); padding:5px 7px; vertical-align:top; }
 textarea { width:100%; font:13px/1.4 ui-monospace,Menlo,monospace; }
 input[type=text] { width:100%; padding:8px; border:1px solid var(--line); border-radius:6px; font:inherit; }
</style></head><body>
<header><div class="row"><h1>__TITLE__</h1><span class="hint" id="count"></span></div>
<div class="bar"><div id="fill"></div></div></header>
<main>
<details><summary>Guideline v2.0 - read it once before you start (open it again whenever unsure)</summary>
<div class="g">__GUIDE__</div></details>
<div id="card"></div>
<div class="panel" id="out" style="display:none">
 <b>Send this file back.</b> Press <b>Download CSV</b>. If nothing downloads, press <b>Copy</b>
 and paste into a text file named <code>__FILE__</code>.
 <textarea id="csv" rows="6" readonly></textarea>
</div>
</main>
<script>
const ITEMS = __ITEMS__;
const CHECKS = __CHECKS__, NOTES = __NOTES__;
const KEY = "grail-v2-__SHEET__";
let S = {}; try { S = JSON.parse(localStorage.getItem(KEY) || "{}"); } catch (e) {}
let i = ITEMS.findIndex(it => !(S[it.item] && S[it.item].label)); if (i < 0) i = ITEMS.length;
function save() { try { localStorage.setItem(KEY, JSON.stringify(S)); } catch (e) {} paint(); }
function esc(s) { return (s||"").replace(/[&<>]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;"}[c])); }
function done() { return ITEMS.filter(it => S[it.item] && S[it.item].label).length; }
function paint() { const n = done();
  document.getElementById("count").textContent = n + " of " + ITEMS.length + " rated";
  document.getElementById("fill").style.width = (100*n/ITEMS.length) + "%"; }
function codes(it) { return it.request === "explanation" ? ["E1","E2","E3"] : ["C1","C2","C3","C4"]; }
function show() {
  paint();
  const card = document.getElementById("card");
  if (i >= ITEMS.length) { card.innerHTML = "<div class='panel'><b>All items rated.</b> Download the CSV below and send it back.</div>"; finish(); return; }
  const it = ITEMS[i], s = S[it.item] || {label:"", reason:"", note_codes:[], notes:""};
  const kind = it.request === "explanation"
    ? "Explanation item - checks E1, E2, E3 (all must hold for adequate)"
    : "Counterfactual item - checks C1, C2, C3, C4 (all must hold for adequate)";
  let h = "<h2>Item " + (i+1) + " of " + ITEMS.length + " - " + esc(it.item) + "</h2>" +
    "<span class='tag'>" + kind + "</span>" +
    "<h2>Application and question</h2><pre>" + esc(it.prompt) + "</pre>" +
    "<h2>Response</h2><pre class='resp'>" + esc(it.response) + "</pre>" +
    "<div class='panel'><div class='row' style='justify-content:flex-start'>" +
    "<button class='ad " + (s.label==="adequate"?"sel":"") + "' onclick=\"setL('adequate')\">1 Adequate</button>" +
    "<button class='in " + (s.label==="inadequate"?"sel":"") + "' onclick=\"setL('inadequate')\">2 Inadequate</button></div>";
  if (s.label === "inadequate") {
    h += "<h2>Reason - the FIRST check that fails</h2>";
    for (const c of codes(it)) h += "<label class='opt'><input type='radio' name='r' value='" + c + "'" +
      (s.reason===c?" checked":"") + " onchange='setR(this.value)'> <b>" + c + "</b> " + CHECKS[c] + "</label>";
  }
  h += "<h2>Note codes (tick all that apply; they never change the label)</h2>";
  for (const [c, t] of Object.entries(NOTES)) h += "<label class='opt'><input type='checkbox' value='" + c + "'" +
    ((s.note_codes||[]).includes(c)?" checked":"") + " onchange='setN(this)'> <b>" + c + "</b> " + t + "</label>";
  h += "<h2>Note (optional)</h2><input type='text' id='nt' value=\"" + esc(s.notes||"").replace(/"/g,"&quot;") + "\" oninput='setT(this.value)'>" +
    "<div class='err' id='err'></div><div class='row'><button onclick='prev()'>&larr; Back</button>" +
    "<button onclick='next()'><b>Next &rarr;</b></button></div></div>";
  card.innerHTML = h; window.scrollTo(0, 0);
}
function cur() { const it = ITEMS[i]; S[it.item] = S[it.item] || {label:"", reason:"", note_codes:[], notes:""}; return S[it.item]; }
function setL(v) { const s = cur(); s.label = v; if (v === "adequate") s.reason = ""; save(); show(); }
function setR(v) { cur().reason = v; save(); }
function setN(el) { const s = cur(); s.note_codes = (s.note_codes||[]).filter(x => x !== el.value); if (el.checked) s.note_codes.push(el.value); save(); }
function setT(v) { cur().notes = v; save(); }
function next() { const s = S[ITEMS[i].item] || {};
  const e = document.getElementById("err");
  if (!s.label) { e.textContent = "Choose adequate or inadequate."; return; }
  if (s.label === "inadequate" && !s.reason) { e.textContent = "An inadequate label needs a reason code."; return; }
  i++; show(); }
function prev() { if (i > 0) { i--; show(); } }
document.addEventListener("keydown", e => { if (e.target.tagName === "INPUT" && e.target.type === "text") return;
  if (e.key === "1") setL("adequate"); if (e.key === "2") setL("inadequate");
  if (e.key === "Enter") next(); if (e.key === "ArrowLeft") prev(); });
function cell(s) { return '"' + String(s||"").replace(/"/g,'""') + '"'; }
function csv() { const L = ["item,request,prompt,response,label,reason,note_codes,notes"];
  for (const it of ITEMS) { const s = S[it.item] || {};
    L.push([it.item, it.request, it.prompt, it.response, s.label||"", s.reason||"", (s.note_codes||[]).join(";"), s.notes||""].map(cell).join(",")); }
  return L.join("\n"); }
function finish() { const box = document.getElementById("out"); box.style.display = "block";
  document.getElementById("csv").value = csv();
  box.innerHTML += "<div class='row' style='margin-top:8px'><button onclick='dl()'><b>Download CSV</b></button><button onclick='cp()'>Copy</button></div>"; }
function dl() { const b = new Blob([csv()], {type:"text/csv;charset=utf-8"}); const a = document.createElement("a");
  a.href = URL.createObjectURL(b); a.download = "__FILE__"; document.body.appendChild(a); a.click(); a.remove(); }
async function cp() { try { await navigator.clipboard.writeText(csv()); alert("Copied."); }
  catch (e) { const t = document.getElementById("csv"); t.focus(); t.select(); } }
show();
</script></body></html>
"""


def packet(sheet_path: str, guideline: str, title: str) -> str:
    with open(sheet_path, encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    items = [{k: r[k] for k in ("item", "request", "prompt", "response")} for r in rows]
    name = os.path.basename(sheet_path)
    page = (PACKET.replace("__TITLE__", title)
                  .replace("__GUIDE__", guidelines_html(guideline))
                  .replace("__ITEMS__", json.dumps(items, ensure_ascii=False).replace("</", "<\\/"))
                  .replace("__CHECKS__", json.dumps(CHECK_TEXT))
                  .replace("__NOTES__", json.dumps(NOTE_TEXT))
                  .replace("__SHEET__", name.replace(".csv", ""))
                  .replace("__FILE__", name))
    out = sheet_path.replace(".csv", ".html")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(page)
    return out


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
