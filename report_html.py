"""
Convert output/report.md to a styled, self-contained HTML intelligence report.

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


# ── Minimal Markdown → HTML ────────────────────────────────────────────────────

def _md_to_html(md: str) -> str:
    """Convert a subset of Markdown to HTML (no deps required)."""
    lines = md.split("\n")
    out = []
    in_code = False
    in_ul = False
    in_ol = False
    in_blockquote = False
    toc_entries: list[tuple[int, str, str]] = []  # (level, anchor, title)

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
        # Escape HTML first
        text = html.escape(text, quote=False)
        # Bold+italic
        text = re.sub(r"\*\*\*(.+?)\*\*\*", r"<strong><em>\1</em></strong>", text)
        # Bold
        text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
        text = re.sub(r"__(.+?)__", r"<strong>\1</strong>", text)
        # Italic
        text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)
        text = re.sub(r"_(.+?)_", r"<em>\1</em>", text)
        # Inline code
        text = re.sub(r"`(.+?)`", r"<code>\1</code>", text)
        # Links
        text = re.sub(
            r"\[(.+?)\]\((https?://[^\)]+)\)",
            r'<a href="\2" target="_blank" rel="noopener">\1</a>',
            text,
        )
        # Bare URLs
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

        # Fenced code block
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

        # Horizontal rule
        if re.match(r"^[-*_]{3,}\s*$", line):
            close_lists()
            close_bq()
            out.append('<hr class="divider">')
            i += 1
            continue

        # Headings
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

        # Blockquote
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

        # Unordered list
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

        # Ordered list
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

        # Blank line — close lists
        if not line.strip():
            close_lists()
            close_bq()
            out.append("")
            i += 1
            continue

        # Normal paragraph
        close_lists()
        close_bq()
        out.append(f"<p>{inline(line)}</p>")
        i += 1

    close_lists()
    close_bq()
    if in_code:
        out.append("</code></pre>")

    return "\n".join(out), toc_entries


def _build_toc(entries: list[tuple[int, str, str]]) -> str:
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

/* Scanline overlay */
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

/* ── Sidebar ── */
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

#sidebar ul {
  list-style: none;
  padding: 0;
}

#sidebar li {
  line-height: 1.4;
}

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

/* ── Main content ── */
#content {
  flex: 1;
  max-width: 820px;
  padding: 48px 40px;
  overflow-x: hidden;
}

/* ── Report header ── */
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

/* ── Headings ── */
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

/* Anchor links */
a.anchor {
  font-size: 11px;
  color: var(--zinc-700);
  text-decoration: none;
  margin-right: 6px;
  opacity: 0;
  transition: opacity 0.15s;
}
h1:hover a.anchor, h2:hover a.anchor, h3:hover a.anchor { opacity: 1; }

/* ── Body text ── */
p {
  color: var(--zinc-400);
  margin-bottom: 14px;
}

strong { color: var(--zinc-200); font-weight: 600; }
em { color: var(--zinc-500); font-style: italic; }

a {
  color: var(--amber);
  text-decoration: none;
}
a:hover { text-decoration: underline; }

/* ── Lists ── */
ul.findings-list, ol.findings-list {
  margin: 8px 0 16px 20px;
}
ul.findings-list li, ol.findings-list li {
  color: var(--zinc-400);
  margin-bottom: 6px;
  padding-left: 4px;
}
ul.findings-list li::marker { color: var(--amber); }
ol.findings-list li::marker { color: var(--amber); font-family: 'JetBrains Mono', monospace; font-size: 11px; }

/* ── Code ── */
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
pre code {
  background: none;
  color: var(--zinc-400);
  padding: 0;
}

/* ── Blockquote ── */
blockquote {
  border-left: 2px solid var(--amber);
  margin: 16px 0;
  padding: 8px 16px;
  background: rgba(245,158,11,0.04);
}
blockquote p { color: var(--zinc-500); margin: 0; font-style: italic; }

/* ── Divider ── */
hr.divider {
  border: none;
  border-top: 1px solid var(--border);
  margin: 32px 0;
}

/* ── Stats bar ── */
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

/* ── Confidence labels ── */
.confirmed { color: var(--green); }
.reported  { color: var(--amber); }
.inferred  { color: var(--violet); }

/* ── Source table ── */
.source-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
  margin: 16px 0;
}
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

/* ── Scrollbar ── */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: var(--bg); }
::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: var(--zinc-700); }

/* ── Print ── */
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
  <div class="brand">Project Bedrock</div>
  <div class="brand-sub">Intelligence Report</div>
  <div class="toc-label">Contents</div>
  {toc}
</aside>

<main id="content">

  <div class="report-header">
    <div class="stamp">Intelligence File</div>
    <div class="report-meta">
      Generated {generated} &nbsp;·&nbsp; Project Bedrock
    </div>
    <div class="report-title">{display_title}</div>
    {scope_line}
  </div>

  {stats_bar}

  {body}

</main>

<script>
// Highlight active TOC link on scroll
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

// Style CONFIRMED/REPORTED/INFERRED labels
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


# ── Main converter ─────────────────────────────────────────────────────────────

def _extract_stats(md: str) -> dict:
    """Best-effort extract stats from the Markdown report."""
    stats = {"sources": "—", "findings": "—", "confidence": "—", "generated": "—"}

    # Generated date
    m = re.search(r"Generated[:\s]+([^\|]+)", md, re.IGNORECASE)
    if m:
        stats["generated"] = m.group(1).strip()

    # Sources count — look for "Sources: N" or table rows
    m = re.search(r"Sources[:\s]+(\d+)", md, re.IGNORECASE)
    if m:
        stats["sources"] = m.group(1)
    else:
        urls = re.findall(r"https?://\S+", md)
        stats["sources"] = str(len(set(urls))) if urls else "—"

    # Findings count — count ## sections
    findings = re.findall(r"^##\s+", md, re.MULTILINE)
    stats["findings"] = str(len(findings)) if findings else "—"

    # Confidence
    m = re.search(r"Confidence[:\s]+([A-Za-z/\s]+)", md, re.IGNORECASE)
    if m:
        stats["confidence"] = m.group(1).strip()[:20]

    return stats


def _build_stats_bar(stats: dict, generated: str) -> str:
    items = [
        ("SOURCES",    stats["sources"],    "var(--green)"),
        ("FINDINGS",   stats["findings"],   "var(--amber)"),
        ("CONFIDENCE", stats["confidence"], "var(--violet)"),
        ("GENERATED",  generated[:10] if generated else "—", "var(--blue)"),
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


def convert(md_path: Path, html_path: Path, topic: str = "", scope: str = "") -> None:
    md = md_path.read_text(encoding="utf-8")

    # Strip YAML front-matter if present
    if md.startswith("---"):
        end = md.find("---", 3)
        if end != -1:
            md = md[end + 3:].lstrip()

    body_html, toc_entries = _md_to_html(md)
    toc_html = _build_toc(toc_entries)

    # Extract display title from first H1 or use topic
    m = re.search(r"^#\s+(.+)$", md, re.MULTILINE)
    display_title = m.group(1) if m else (topic or md_path.stem)

    generated = datetime.now().strftime("%Y-%m-%d %H:%M")
    stats = _extract_stats(md)
    stats_bar = _build_stats_bar(stats, generated)

    scope_line = (
        f'<div class="report-scope">{html.escape(scope)}</div>' if scope else ""
    )

    rendered = _HTML_TEMPLATE.format(
        title=html.escape(display_title),
        css=_CSS,
        toc=toc_html,
        generated=html.escape(generated),
        display_title=html.escape(display_title),
        scope_line=scope_line,
        stats_bar=stats_bar,
        body=body_html,
    )

    html_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.write_text(rendered, encoding="utf-8")
    print(f"HTML report written to: {html_path.absolute()}")
    kb = html_path.stat().st_size / 1024
    print(f"Report size: {kb:.1f} KB")


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert report.md to styled HTML")
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
