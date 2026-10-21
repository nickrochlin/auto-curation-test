"""
Turn a result in outputs/*.json into a readable web page (.html) beside it.

run_skill.py does this automatically after every run. You can also run it yourself,
for example on results you already have, without running the model again:

    python render_report.py                     # every .json in outputs/
    python render_report.py outputs/NAME.json   # one result
    python render_report.py --open              # also open the newest report in your browser

The page works offline and sends nothing anywhere. Where a result quotes the
source text as evidence, the quote is checked against the source and flagged if
it cannot be found.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
import webbrowser
from datetime import datetime
from pathlib import Path

from read_documents import extract_text

BASE = Path(__file__).resolve().parent
OUTPUTS = BASE / "outputs"
INBOX = BASE / "inbox"

STATUS = {   # status -> (label, css class)
    "present": ("Present", "good"), "pass": ("Pass", "good"),
    "partial": ("Partial", "warn"), "unclear": ("Unclear", "warn"),
    "missing": ("Missing", "bad"), "fail": ("Fail", "bad"),
    "not_applicable": ("Not applicable", "mute"), "n/a": ("Not applicable", "mute"),
}
OVERALL = {"thorough": "good", "adequate": "good", "incomplete": "warn", "missing": "bad"}
README_SECTIONS = {
    "g": "General information", "f": "Data and file overview", "s": "Sharing and access",
    "m": "Methodological information", "d": "Data-specific information", "c": "Canadian context",
}

CSS = """
:root{--bg:#fbfaf8;--card:#fff;--ink:#1d2330;--sub:#5d6678;--line:#e3e0d9;--accent:#2b5fa8;
--good:#1c7a46;--good-bg:#e3f4ea;--warn:#8a5a00;--warn-bg:#fdf1d6;--bad:#a8261f;--bad-bg:#fbe5e3;--mute:#5d6678;--mute-bg:#eceae5}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#14171d;--card:#1c2029;--ink:#e8eaf0;--sub:#9aa3b5;
--line:#2c3240;--accent:#7fa8e6;--good:#5cc98a;--good-bg:#173626;--warn:#e8b955;--warn-bg:#3b2e10;--bad:#f08a82;--bad-bg:#40201e;--mute:#9aa3b5;--mute-bg:#262b36}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.55 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
main{max-width:980px;margin:0 auto;padding:28px 16px 64px}
h1{font-size:1.55rem;margin:0 0 4px}h2{font-size:1.1rem;margin:30px 0 10px}
.meta{color:var(--sub);font-size:.88rem;margin-bottom:18px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 18px;margin:12px 0}
.chip{display:inline-block;padding:1px 10px;border-radius:99px;font-size:.8rem;font-weight:600;white-space:nowrap}
.good{color:var(--good);background:var(--good-bg)}.warn{color:var(--warn);background:var(--warn-bg)}
.bad{color:var(--bad);background:var(--bad-bg)}.mute{color:var(--mute);background:var(--mute-bg)}
.overall{display:flex;flex-wrap:wrap;gap:10px 22px;align-items:center}
.overall .big{font-size:1.25rem;font-weight:700}
ol.fixes{margin:6px 0 0;padding-left:22px}ol.fixes li{margin:5px 0}
table{width:100%;border-collapse:collapse;background:var(--card);border:1px solid var(--line);border-radius:10px;overflow:hidden;font-size:.93rem}
th,td{text-align:left;padding:8px 12px;border-bottom:1px solid var(--line);vertical-align:top}
th{background:var(--mute-bg);font-size:.8rem;text-transform:uppercase;letter-spacing:.03em;color:var(--sub)}
tr:last-child td{border-bottom:0}.star{color:var(--accent);font-weight:700}
.quote{font-style:italic;color:var(--sub)}.verify{font-size:.8rem;margin-top:3px}.verify.ok{color:var(--good)}.verify.no{color:var(--bad);font-weight:600}
.none{color:var(--sub);font-style:italic}.alert{border-left:4px solid var(--warn);background:var(--warn-bg);color:var(--ink)}
dl{display:grid;grid-template-columns:max-content 1fr;gap:6px 18px;margin:0}dt{color:var(--sub)}dd{margin:0}
details{margin-top:28px}summary{cursor:pointer;color:var(--sub)}pre{overflow:auto;background:var(--card);border:1px solid var(--line);padding:12px;border-radius:8px;font-size:.8rem}
table.el,table.ck{table-layout:fixed}
table.el th:nth-child(1){width:21%}table.el th:nth-child(2){width:12%}table.el th:nth-child(3){width:32%}table.el th:nth-child(4){width:35%}
table.ck th:nth-child(1){width:26%}table.ck th:nth-child(2){width:12%}
td{overflow-wrap:anywhere}
@media (max-width:640px){dl{grid-template-columns:1fr}.overall{display:block}.overall>div{margin:6px 0}
table.el,table.ck{table-layout:auto}tr.hd{display:none}
table.el tr,table.ck tr{display:block;padding:8px 0;border-bottom:1px solid var(--line)}
table.el td,table.ck td{display:block;border:0;padding:2px 12px}}
@media print{body{background:#fff}.card,table{break-inside:avoid}}
"""


def esc(value) -> str:
    return html.escape("" if value is None else str(value))


def as_list(value) -> list:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def chip(status) -> str:
    key = str(status or "").strip().lower().replace(" ", "_")
    label, css = STATUS.get(key, (str(status or "?"), "mute"))
    return f'<span class="chip {css}">{esc(label)}</span>'


def norm(text: str) -> str:
    return re.sub(r"[\s\W_]+", " ", text.lower()).strip()


def quote_found(quote: str, source_norm: str | None):
    """True/False if the quote can be checked against the source, None if it cannot."""
    if source_norm is None or not str(quote or "").strip():
        return None
    pieces = [norm(p) for p in re.split(r"\.\.\.|…", str(quote))]
    pieces = [p for p in pieces if len(p) >= 8]
    return all(p in source_norm for p in pieces) if pieces else None


def verify_html(quote, source_norm) -> str:
    found = quote_found(quote, source_norm)
    if found is True:
        return '<div class="verify ok">&#10003; quote found in the source</div>'
    if found is False:
        return '<div class="verify no">&#9888; this quote was not found in the source; check it by hand</div>'
    return ""


def fix_list(fixes) -> str:
    items = [f"<li>{esc(f)}</li>" for f in as_list(fixes) if f]
    return f'<ol class="fixes">{"".join(items)}</ol>' if items else '<p class="none">None listed.</p>'


def expected_rating(elements: list[dict], readme_found: bool) -> str:
    if not readme_found:
        return "missing"
    status = lambda e: str(e.get("status", "")).lower()
    minimum = [e for e in elements if e.get("minimum")]
    if any(status(e) == "missing" for e in minimum):
        return "incomplete"
    others = [e for e in elements if not e.get("minimum") and status(e) != "not_applicable"]
    if others and sum(status(e) in ("present", "partial") for e in others) / len(others) >= 2 / 3:
        return "thorough"
    return "adequate"


def render_readme(d: dict, source_norm) -> str:
    elements = [e for e in as_list(d.get("elements")) if isinstance(e, dict)]
    found = d.get("readme_found", True) is not False
    counts = {k: sum(str(e.get("status", "")).lower() == k for e in elements)
              for k in ("present", "partial", "missing", "not_applicable")}
    minimum = [e for e in elements if e.get("minimum")]
    min_ok = sum(str(e.get("status", "")).lower() == "present" for e in minimum)
    overall = str(d.get("overall", "?")).lower()
    expected = expected_rating(elements, found)

    out = ['<div class="card overall">',
           f'<div><div class="meta" style="margin:0">Overall</div><span class="chip big {OVERALL.get(overall, "mute")}">{esc(overall.title())}</span></div>',
           f'<div><b>{min_ok} of {len(minimum)}</b> minimum elements fully present</div>',
           f'<div>{counts["present"]} present &middot; {counts["partial"]} partial &middot; '
           f'{counts["missing"]} missing &middot; {counts["not_applicable"]} not applicable</div></div>']
    if elements and overall != expected:
        out.append(f'<div class="card alert">The model rated this <b>{esc(overall)}</b>, but applying the rating rules '
                   f'to its own table gives <b>{esc(expected)}</b>. Trust the table over the label.</div>')
    bad_quotes = [e for e in elements if str(e.get("status", "")).lower() in ("present", "partial")
                  and quote_found(e.get("evidence"), source_norm) is False]
    if bad_quotes:
        out.append(f'<div class="card alert"><b>{len(bad_quotes)} quoted passage(s) could not be found in the source.</b> '
                   'They are flagged in the table below. The model may have misread or invented them.</div>')

    out += ["<h2>Most important fixes</h2>", f'<div class="card">{fix_list(d.get("top_fixes"))}</div>',
            "<h2>Element by element</h2>"]
    groups: dict[str, list] = {}
    for e in elements:
        groups.setdefault(str(e.get("id", "?"))[:1].lower(), []).append(e)
    for key in list(README_SECTIONS) + [k for k in groups if k not in README_SECTIONS]:
        if key not in groups:
            continue
        rows = []
        for e in groups[key]:
            star = '<span class="star" title="Minimum for reuse">&#9733;</span> ' if e.get("minimum") else ""
            ev = e.get("evidence")
            evidence = f'<div class="quote">&ldquo;{esc(ev)}&rdquo;</div>{verify_html(ev, source_norm)}' if ev else ""
            rows.append(f'<tr><td>{star}{esc(str(e.get("element", e.get("id", ""))).replace("_", " ").capitalize().replace("Readme", "README"))}</td>'
                        f'<td>{chip(e.get("status"))}</td><td>{evidence}</td><td>{esc(e.get("note"))}</td></tr>')
        out.append(f'<h3 style="font-size:1rem;margin:20px 0 6px">{esc(README_SECTIONS.get(key, "Other"))}</h3>'
                   '<table class="el"><tr class="hd"><th>Element</th><th>Status</th><th>Evidence in the README</th><th>Note</th></tr>'
                   + "".join(rows) + "</table>")
    out.append('<p class="meta">&#9733; = minimum content for reuse, according to the Cornell README guide.</p>')
    return "\n".join(out)


def kv(value) -> str:
    items = [x for x in as_list(value) if x not in (None, "")]
    if not items:
        return '<span class="none">not provided</span>'
    return "<br>".join(esc(x) for x in items)


def render_deposit(d: dict, source_norm) -> str:
    checklist = [c for c in as_list(d.get("checklist")) if isinstance(c, dict)]
    counts = {k: sum(str(c.get("status", "")).lower() == k for c in checklist) for k in ("pass", "fail", "unclear")}
    out = ['<div class="card overall">'
           f'<div>{counts["pass"]} pass &middot; {counts["unclear"]} unclear &middot; {counts["fail"]} fail</div></div>',
           "<h2>Most important fixes</h2>", f'<div class="card">{fix_list(d.get("top_fixes"))}</div>',
           "<h2>Deposit checklist</h2>", '<table class="ck"><tr class="hd"><th>Item</th><th>Result</th><th>Reason</th></tr>']
    for c in checklist:
        out.append(f'<tr><td>{esc(str(c.get("item", "")).replace("_", " ").capitalize().replace("Readme", "README"))}</td>'
                   f'<td>{chip(c.get("status"))}</td><td>{esc(c.get("reason"))}</td></tr>')
    out.append("</table><h2>Draft citation metadata</h2><div class=\"card\"><dl>")
    meta = d.get("metadata")
    if isinstance(meta, dict):
        for k, v in meta.items():
            out.append(f'<dt>{esc(str(k).replace("_", " ").capitalize())}</dt><dd>{kv(v)}</dd>')
    out.append("</dl></div>")
    missing = [m for m in as_list(d.get("missing_info")) if m]
    if missing:
        out.append("<h2>Information the researcher still needs to supply</h2><div class=\"card\"><ul>"
                   + "".join(f"<li>{esc(m)}</li>" for m in missing) + "</ul></div>")
    return "\n".join(out)


def render_generic(value, depth=0) -> str:
    if isinstance(value, dict):
        return '<dl>' + "".join(f'<dt>{esc(str(k).replace("_", " ").capitalize())}</dt><dd>{render_generic(v, depth + 1)}</dd>'
                                for k, v in value.items()) + "</dl>"
    if isinstance(value, list):
        if value and all(isinstance(v, dict) for v in value):
            cols = list(dict.fromkeys(k for v in value for k in v))
            return ("<table><tr>" + "".join(f"<th>{esc(c)}</th>" for c in cols) + "</tr>"
                    + "".join("<tr>" + "".join(f"<td>{render_generic(v.get(c), depth + 1)}</td>" for c in cols) + "</tr>"
                              for v in value) + "</table>")
        return "<ul>" + "".join(f"<li>{render_generic(v, depth + 1)}</li>" for v in value) + "</ul>"
    return esc(value) if value not in (None, "") else '<span class="none">none</span>'


TITLES = {"readme-review": "README review", "deposit-readiness": "Deposit readiness check"}


def render(data, skill: str, source: str, model: str, source_text: str | None) -> str:
    source_norm = norm(source_text) if source_text else None
    if skill == "readme-review" and isinstance(data, dict):
        body = render_readme(data, source_norm)
    elif skill == "deposit-readiness" and isinstance(data, dict):
        body = render_deposit(data, source_norm)
    else:
        body = f'<div class="card">{render_generic(data)}</div>'
    title = f"{TITLES.get(skill, skill)}: {source}"
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(title)}</title>'
            f'<style>{CSS}</style></head><body><main><h1>{esc(TITLES.get(skill, skill))}</h1>'
            f'<div class="meta">Source: {esc(source)} &middot; Skill: {esc(skill)} &middot; Model: {esc(model)} &middot; '
            f'Report made {stamp}<br>This is a first pass by a small local model. A curator should check it.</div>'
            f'{body}<details><summary>Raw result (JSON)</summary><pre>{esc(json.dumps(data, indent=2, ensure_ascii=False))}</pre></details>'
            f'</main></body></html>')


def find_source_text(source: str) -> str | None:
    """The text the model was given: the inbox file with this name."""
    for f in sorted(INBOX.glob(f"{source}.*")):
        text, _ = extract_text(f)
        if text:
            return text
    return None


def render_file(json_path: Path) -> Path | None:
    """Write the .html report beside a result file. Returns its path, or None if the file isn't a result."""
    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    parts = json_path.stem.rsplit("__", 2)
    source, skill, model = (parts + ["?", "?"])[:3] if len(parts) == 3 else (json_path.stem, "?", "?")
    out = json_path.with_suffix(".html")
    out.write_text(render(data, skill, source, model, find_source_text(source)), encoding="utf-8")
    return out


def main():
    parser = argparse.ArgumentParser(description="Make readable reports from results in outputs/.")
    parser.add_argument("files", nargs="*", help="Result .json files (default: all in outputs/)")
    parser.add_argument("--open", action="store_true", help="Open the newest report in your browser")
    args = parser.parse_args()
    files = [Path(f) for f in args.files] or sorted(OUTPUTS.glob("*.json"))
    if not files:
        sys.exit("No results found in outputs/. Run a skill first.")
    made = [r for r in (render_file(f) for f in files) if r]
    for r in made:
        print(f"Wrote {r}")
    if args.open and made:
        webbrowser.open(max(made, key=lambda p: p.stat().st_mtime).resolve().as_uri())


if __name__ == "__main__":
    main()
