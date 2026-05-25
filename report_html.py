"""
Convert output/report.md to a styled, self-contained case file HTML document.

Usage:
    python report_html.py                      # reads output/report.md
    python report_html.py path/to/report.md    # explicit input
    python report_html.py in.md --out out.html # explicit output
"""

import argparse
import html
import re
import sys
from datetime import datetime
from pathlib import Path


# ── Oracle output section parser ──────────────────────────────────────────────

_SECTION_HEADERS = [
    ("finding",     re.compile(r"^(?:#{1,4} +)?THE FINDING *$", re.I | re.M)),
    ("margin_note", re.compile(r"^(?:#{1,4} +)?THE MARGIN NOTE *$", re.I | re.M)),
    ("section_i",   re.compile(
        r"^(?:#{1,4} +)?SECTION (?:I|1) *[—–\-:]+ *THE RECORD *$"
        r"|^(?:#{1,4} +)?I\. *THE RECORD *$", re.I | re.M)),
    ("section_ii",  re.compile(
        r"^(?:#{1,4} +)?SECTION (?:II|2) *[—–\-:]+ *THE TIMELINE *$"
        r"|^(?:#{1,4} +)?II\. *THE TIMELINE *$", re.I | re.M)),
    ("section_iii", re.compile(
        r"^(?:#{1,4} +)?SECTION (?:III|3) *[—–\-:]+ *CONTRADICT", re.I | re.M)),
    ("section_iv",  re.compile(
        r"^(?:#{1,4} +)?SECTION (?:IV|4) *[—–\-:]+ *NARRATIVE DRIFT *$"
        r"|^(?:#{1,4} +)?IV\. *NARRATIVE DRIFT *$", re.I | re.M)),
    ("section_v",   re.compile(
        r"^(?:#{1,4} +)?SECTION (?:V|5) *[—–\-:]+ *THE SOURCE INVENTORY *$"
        r"|^(?:#{1,4} +)?V\. *THE SOURCE INVENTORY *$", re.I | re.M)),
    ("section_vi",  re.compile(
        r"^(?:#{1,4} +)?SECTION (?:VI|6) *[—–\-:]+ *(?:THE )?EXHIBITS *$"
        r"|^(?:#{1,4} +)?VI\. *(?:THE )?EXHIBITS *$", re.I | re.M)),
    ("attribution", re.compile(r"^(?:#{1,4} +)?ATTRIBUTION LINES? *$", re.I | re.M)),
    ("confidence",  re.compile(r"^(?:#{1,4} +)?CONFIDENCE *$", re.I | re.M)),
    ("signature",   re.compile(
        r"^(?:#{1,4} +)?ORACLE(?:'S)? SIGNATURE *$"
        r"|^(?:#{1,4} +)?SIGNED BY ORACLE *$", re.I | re.M)),
]

_SECTION_KEYS = [k for k, _ in _SECTION_HEADERS]


def _parse_oracle_output(md: str) -> dict:
    """
    Parse Oracle's structured markdown output into named sections.
    Tolerates ## / plain-text headers, Roman / Arabic numerals,
    em-dash / en-dash / hyphen separators, and mixed case.
    Missing sections have empty-string values.
    """
    result = {k: "" for k in _SECTION_KEYS}
    hits = []
    for key, pattern in _SECTION_HEADERS:
        for m in pattern.finditer(md):
            hits.append((m.start(), m.end(), key))
    hits.sort(key=lambda x: x[0])
    for idx, (start, end, key) in enumerate(hits):
        next_start = hits[idx + 1][0] if idx + 1 < len(hits) else len(md)
        result[key] = md[end:next_start].strip()
    return result


def _finding_paragraphs(finding_text: str) -> list:
    """Split THE FINDING block into up to three paragraphs; strip stray headers."""
    if not finding_text:
        return []
    paras = [re.sub(r"^#+\s+", "", p.strip()) for p in re.split(r"\n\n+", finding_text)]
    return [p for p in paras if p][:3]


def _confidence_level(confidence_text: str) -> str:
    m = re.search(r"\b(High|Medium|Low)\b", confidence_text, re.I)
    return m.group(1).capitalize() if m else "—"


# ── Minimal Markdown → HTML ────────────────────────────────────────────────────

def _md_to_html(md: str) -> str:
    """Convert a subset of Markdown to HTML (no deps required)."""
    lines = md.split("\n")
    out = []
    in_code = False
    in_ul = False
    in_ol = False
    in_blockquote = False
    toc_entries: list = []  # (level, anchor, title)

    def close_lists():
        nonlocal in_ul, in_ol
        if in_ul:
            out.append("</ul>")
            in_ul = False
        if in_ol:
            out.append("</ol>")
            in_ol = False

    def close_bq():
        nonlocal in_blockquote
        if in_blockquote:
            out.append("</blockquote>")
            in_blockquote = False

    def inline(text: str) -> str:
        """Process inline formatting."""
        text = html.escape(text, quote=False)
        text = re.sub(r"\*\*\*(.+?)\*\*\*", r"<strong><em>\1</em></strong>", text)
        text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
        text = re.sub(r"__(.+?)__", r"<strong>\1</strong>", text)
        text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)
        text = re.sub(r"_(.+?)_", r"<em>\1</em>", text)
        text = re.sub(r"`(.+?)`", r"<code>\1</code>", text)
        text = re.sub(
            r"\[(.+?)\]\((https?://[^\)]+)\)",
            r'<a href="\2" target="_blank" rel="noopener">\1</a>',
            text,
        )
        text = re.sub(
            r"(?<![\"'])(https?://[^\s<>\"']+)",
            r'<a href="\1" target="_blank" rel="noopener">\1</a>',
            text,
        )
        return text

    def make_anchor(title: str) -> str:
        anchor = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
        return anchor

    i = 0
    while i < len(lines):
        line = lines[i]

        if line.startswith("```"):
            close_lists()
            close_bq()
            if not in_code:
                lang = line[3:].strip()
                cls = f' class="language-{lang}"' if lang else ""
                out.append(f"<pre><code{cls}>")
                in_code = True
            else:
                out.append("</code></pre>")
                in_code = False
            i += 1
            continue

        if in_code:
            out.append(html.escape(line))
            i += 1
            continue

        if re.match(r"^[-*_]{3,}\s*$", line):
            close_lists()
            close_bq()
            out.append('<hr class="divider">')
            i += 1
            continue

        m = re.match(r"^(#{1,6})\s+(.+)$", line)
        if m:
            close_lists()
            close_bq()
            level = len(m.group(1))
            title = m.group(2).strip()
            anchor = make_anchor(title)
            toc_entries.append((level, anchor, title))
            out.append(
                f'<h{level} id="{anchor}">'
                f'<a class="anchor" href="#{anchor}">¶</a>'
                f"{html.escape(title)}</h{level}>"
            )
            i += 1
            continue

        if line.startswith("> "):
            close_lists()
            if not in_blockquote:
                out.append("<blockquote>")
                in_blockquote = True
            out.append(f"<p>{inline(line[2:])}</p>")
            i += 1
            continue
        else:
            close_bq()

        m = re.match(r"^[-*+]\s+(.+)$", line)
        if m:
            if in_ol:
                out.append("</ol>")
                in_ol = False
            if not in_ul:
                out.append('<ul class="findings-list">')
                in_ul = True
            out.append(f"<li>{inline(m.group(1))}</li>")
            i += 1
            continue

        m = re.match(r"^\d+\.\s+(.+)$", line)
        if m:
            if in_ul:
                out.append("</ul>")
                in_ul = False
            if not in_ol:
                out.append('<ol class="findings-list">')
                in_ol = True
            out.append(f"<li>{inline(m.group(1))}</li>")
            i += 1
            continue

        if not line.strip():
            close_lists()
            close_bq()
            out.append("")
            i += 1
            continue

        close_lists()
        close_bq()
        out.append(f"<p>{inline(line)}</p>")
        i += 1

    close_lists()
    close_bq()
    if in_code:
        out.append("</code></pre>")

    return "\n".join(out), toc_entries


def _build_toc(entries: list) -> str:
    if not entries:
        return ""
    items = []
    for level, anchor, title in entries:
        indent = "  " * (level - 1)
        items.append(f'{indent}<li><a href="#{anchor}">{html.escape(title)}</a></li>')
    return "<ul>\n" + "\n".join(items) + "\n</ul>"


# ── CSS ────────────────────────────────────────────────────────────────────────

_CSS = """
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

:root {
  --bg:      #0c0c0f;
  --surface: #111116;
  --border:  #1e1e26;
  --amber:   #f59e0b;
  --violet:  #a78bfa;
  --green:   #22c55e;
  --blue:    #60a5fa;
  --zinc-100: #f4f4f5;
  --zinc-200: #e4e4e7;
  --zinc-400: #a1a1aa;
  --zinc-500: #71717a;
  --zinc-600: #52525b;
  --zinc-700: #3f3f46;
}

html { scroll-behavior: smooth; }

body {
  background: var(--bg);
  color: var(--zinc-400);
  font-family: 'Inter', 'Helvetica Neue', Arial, sans-serif;
  font-size: 14px;
  line-height: 1.7;
  display: flex;
  min-height: 100vh;
}

body::before {
  content: '';
  position: fixed;
  inset: 0;
  background: repeating-linear-gradient(
    to bottom,
    transparent 0px,
    transparent 3px,
    rgba(0,0,0,0.04) 3px,
    rgba(0,0,0,0.04) 4px
  );
  pointer-events: none;
  z-index: 9999;
}

#sidebar {
  width: 240px;
  min-width: 240px;
  position: sticky;
  top: 0;
  height: 100vh;
  overflow-y: auto;
  background: var(--surface);
  border-right: 1px solid var(--border);
  padding: 24px 16px;
  flex-shrink: 0;
}

#sidebar .brand {
  font-family: 'JetBrains Mono', 'Courier New', monospace;
  font-size: 11px;
  font-weight: 700;
  color: var(--amber);
  letter-spacing: 0.12em;
  text-transform: uppercase;
  margin-bottom: 4px;
}

#sidebar .brand-sub {
  font-family: 'JetBrains Mono', 'Courier New', monospace;
  font-size: 9px;
  color: var(--zinc-600);
  letter-spacing: 0.1em;
  text-transform: uppercase;
  margin-bottom: 24px;
}

#sidebar .toc-label {
  font-family: 'JetBrains Mono', 'Courier New', monospace;
  font-size: 9px;
  color: var(--zinc-600);
  letter-spacing: 0.15em;
  text-transform: uppercase;
  margin-bottom: 8px;
}

#sidebar ul { list-style: none; padding: 0; }
#sidebar li { line-height: 1.4; }

#sidebar a {
  display: block;
  font-size: 12px;
  color: var(--zinc-500);
  text-decoration: none;
  padding: 4px 8px;
  border-radius: 3px;
  transition: color 0.15s, background 0.15s;
  border-left: 2px solid transparent;
}
#sidebar a:hover {
  color: var(--zinc-200);
  background: rgba(245,158,11,0.06);
  border-left-color: var(--amber);
}

#sidebar li li a { padding-left: 16px; font-size: 11px; }
#sidebar li li li a { padding-left: 24px; font-size: 10px; }

#content {
  flex: 1;
  max-width: 820px;
  padding: 48px 40px;
  overflow-x: hidden;
}

.report-header {
  border-bottom: 1px solid var(--border);
  padding-bottom: 32px;
  margin-bottom: 40px;
  position: relative;
}

.report-header .stamp {
  position: absolute;
  top: -8px;
  right: 0;
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  font-weight: 700;
  color: #ef4444;
  border: 2px solid #ef4444;
  padding: 2px 10px;
  letter-spacing: 0.2em;
  text-transform: uppercase;
  transform: rotate(-2deg);
  opacity: 0.75;
}

.report-meta {
  font-family: 'JetBrains Mono', 'Courier New', monospace;
  font-size: 10px;
  color: var(--zinc-600);
  letter-spacing: 0.1em;
  text-transform: uppercase;
  margin-bottom: 12px;
}

.report-title {
  font-family: 'Inter', sans-serif;
  font-size: 26px;
  font-weight: 700;
  color: var(--zinc-100);
  line-height: 1.3;
  margin-bottom: 8px;
}

.report-scope {
  font-size: 13px;
  color: var(--zinc-500);
  font-style: italic;
}

h1, h2, h3, h4, h5, h6 {
  font-family: 'Inter', sans-serif;
  color: var(--zinc-100);
  font-weight: 700;
  line-height: 1.3;
  margin-top: 36px;
  margin-bottom: 12px;
}

h1 { font-size: 22px; border-bottom: 1px solid var(--border); padding-bottom: 8px; }
h2 { font-size: 17px; color: var(--zinc-200); }
h3 { font-size: 14px; color: var(--amber); }
h4 { font-size: 13px; color: var(--zinc-400); }

h1:first-child, h2:first-child { margin-top: 0; }

a.anchor {
  font-size: 11px;
  color: var(--zinc-700);
  text-decoration: none;
  margin-right: 6px;
  opacity: 0;
  transition: opacity 0.15s;
}
h1:hover a.anchor, h2:hover a.anchor, h3:hover a.anchor { opacity: 1; }

p { color: var(--zinc-400); margin-bottom: 14px; }
strong { color: var(--zinc-200); font-weight: 600; }
em { color: var(--zinc-500); font-style: italic; }

a { color: var(--amber); text-decoration: none; }
a:hover { text-decoration: underline; }

ul.findings-list, ol.findings-list { margin: 8px 0 16px 20px; }
ul.findings-list li, ol.findings-list li {
  color: var(--zinc-400);
  margin-bottom: 6px;
  padding-left: 4px;
}
ul.findings-list li::marker { color: var(--amber); }
ol.findings-list li::marker { color: var(--amber); font-family: 'JetBrains Mono', monospace; font-size: 11px; }

code {
  font-family: 'JetBrains Mono', 'Courier New', monospace;
  font-size: 12px;
  background: #1a1408;
  color: var(--amber);
  padding: 1px 5px;
  border-radius: 3px;
}

pre {
  background: #111116;
  border: 1px solid var(--border);
  border-radius: 4px;
  padding: 16px;
  overflow-x: auto;
  margin: 16px 0;
}
pre code { background: none; color: var(--zinc-400); padding: 0; }

blockquote {
  border-left: 2px solid var(--amber);
  margin: 16px 0;
  padding: 8px 16px;
  background: rgba(245,158,11,0.04);
}
blockquote p { color: var(--zinc-500); margin: 0; font-style: italic; }

hr.divider { border: none; border-top: 1px solid var(--border); margin: 32px 0; }

.stats-bar {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 40px;
}
.stat-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 4px;
  padding: 12px 16px;
}
.stat-label {
  font-family: 'JetBrains Mono', monospace;
  font-size: 9px;
  color: var(--zinc-600);
  letter-spacing: 0.15em;
  text-transform: uppercase;
  margin-bottom: 4px;
}
.stat-value {
  font-family: 'JetBrains Mono', monospace;
  font-size: 18px;
  font-weight: 700;
}

.confirmed { color: var(--green); }
.reported  { color: var(--amber); }
.inferred  { color: var(--violet); }

.source-table { width: 100%; border-collapse: collapse; font-size: 12px; margin: 16px 0; }
.source-table th {
  font-family: 'JetBrains Mono', monospace;
  font-size: 9px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--zinc-600);
  text-align: left;
  padding: 6px 12px;
  border-bottom: 1px solid var(--border);
}
.source-table td {
  padding: 8px 12px;
  border-bottom: 1px solid var(--border);
  vertical-align: top;
  color: var(--zinc-400);
}
.source-table tr:hover td { background: rgba(255,255,255,0.02); }
.source-table td:first-child { font-family: 'JetBrains Mono', monospace; font-size: 11px; }

::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: var(--bg); }
::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: var(--zinc-700); }

@media print {
  body::before { display: none; }
  #sidebar { display: none; }
  #content { max-width: none; padding: 20px; }
}
"""

# ── HTML template ──────────────────────────────────────────────────────────────

_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;700&display=swap" rel="stylesheet">
<style>
{css}
</style>
</head>
<body>

<aside id="sidebar">
  <div class="brand">The Casefilers</div>
  <div class="brand-sub">Case File</div>
  <div class="toc-label">Contents</div>
  {toc}
</aside>

<main id="content">

  <div class="report-header">
    <div class="stamp">Signed by Oracle</div>
    <div class="report-meta">
      Bound {bound_at} &nbsp;&middot;&nbsp; The Casefilers
    </div>
    <div class="report-title">{display_title}</div>
    {scope_line}
  </div>

  {stats_bar}

  {body}

</main>

<script>
const headings = document.querySelectorAll('h1[id],h2[id],h3[id],h4[id]');
const links = document.querySelectorAll('#sidebar a');
const obs = new IntersectionObserver(entries => {{
  entries.forEach(e => {{
    if (e.isIntersecting) {{
      links.forEach(l => l.classList.remove('active'));
      const a = document.querySelector('#sidebar a[href="#' + e.target.id + '"]');
      if (a) a.style.color = 'var(--amber)';
    }}
  }});
}}, {{ rootMargin: '-20% 0px -70% 0px' }});
headings.forEach(h => obs.observe(h));

document.querySelectorAll('p, li').forEach(el => {{
  el.innerHTML = el.innerHTML
    .replace(/\\bCONFIRMED\\b/g, '<span class="confirmed">CONFIRMED</span>')
    .replace(/\\bREPORTED\\b/g,  '<span class="reported">REPORTED</span>')
    .replace(/\\bINFERRED\\b/g,  '<span class="inferred">INFERRED</span>');
}});
</script>
</body>
</html>
"""


# ── Stats extraction ───────────────────────────────────────────────────────────

def _extract_stats(md: str, parsed: dict) -> dict:
    """Extract display stats from Oracle's case file output."""
    stats = {"sources": "—", "sections": "—", "confidence": "—", "bound_at": "—"}

    urls = re.findall(r"https?://\S+", md)
    stats["sources"] = str(len(set(urls))) if urls else "—"

    body_keys = ["section_i", "section_ii", "section_iii", "section_iv", "section_v", "section_vi"]
    n = sum(1 for k in body_keys if parsed.get(k, "").strip())
    stats["sections"] = str(n) if n else "—"

    if parsed.get("confidence"):
        stats["confidence"] = _confidence_level(parsed["confidence"])

    sig = parsed.get("signature", "").strip()
    if sig:
        stats["bound_at"] = sig[:30]

    return stats


def _build_stats_bar(stats: dict, bound_at: str) -> str:
    items = [
        ("ITEMS FILED", stats["sources"],    "var(--green)"),
        ("SECTIONS",    stats["sections"],   "var(--amber)"),
        ("CONFIDENCE",  stats["confidence"], "var(--violet)"),
        ("BOUND",       bound_at[:10] if bound_at and bound_at != "—" else "—", "var(--blue)"),
    ]
    cards = ""
    for label, val, color in items:
        cards += (
            f'<div class="stat-card">'
            f'<div class="stat-label">{label}</div>'
            f'<div class="stat-value" style="color:{color}">{html.escape(str(val))}</div>'
            f"</div>"
        )
    return f'<div class="stats-bar">{cards}</div>'


# ── Main converter ─────────────────────────────────────────────────────────────

def convert(md_path: Path, html_path: Path, topic: str = "", scope: str = "") -> None:
    md = md_path.read_text(encoding="utf-8")

    if md.startswith("---"):
        end = md.find("---", 3)
        if end != -1:
            md = md[end + 3:].lstrip()

    parsed = _parse_oracle_output(md)
    body_html, toc_entries = _md_to_html(md)
    toc_html = _build_toc(toc_entries)

    m = re.search(r"^#\s+(.+)$", md, re.MULTILINE)
    display_title = m.group(1) if m else (topic or md_path.stem)

    bound_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    stats = _extract_stats(md, parsed)
    stats_bar = _build_stats_bar(stats, bound_at)

    scope_line = (
        f'<div class="report-scope">{html.escape(scope)}</div>' if scope else ""
    )

    rendered = _HTML_TEMPLATE.format(
        title=html.escape(display_title),
        css=_CSS,
        toc=toc_html,
        bound_at=html.escape(bound_at),
        display_title=html.escape(display_title),
        scope_line=scope_line,
        stats_bar=stats_bar,
        body=body_html,
    )

    html_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.write_text(rendered, encoding="utf-8")
    print(f"Case file written to: {html_path.absolute()}")
    kb = html_path.stat().st_size / 1024
    print(f"File size: {kb:.1f} KB")


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert case file markdown to styled HTML")
    parser.add_argument("input", nargs="?", default="output/report.md")
    parser.add_argument("--out", default="")
    parser.add_argument("--topic", default="")
    parser.add_argument("--scope", default="")
    args = parser.parse_args()

    md_path = Path(args.input)
    if not md_path.exists():
        print(f"ERROR: {md_path} not found", file=sys.stderr)
        sys.exit(1)

    if args.out:
        html_path = Path(args.out)
    else:
        html_path = md_path.with_suffix(".html")

    convert(md_path, html_path, topic=args.topic, scope=args.scope)


if __name__ == "__main__":
    main()
