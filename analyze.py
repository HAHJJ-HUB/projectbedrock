#!/usr/bin/env python3
"""
Standalone narrative analysis CLI.

Runs the five narrative analysis passes (certainty inflation, framing shift,
contradiction detection, language drift, narrative compression) on whatever
is already stored in persistent memory for a given topic.

Does NOT require the full CrewAI pipeline. Operates directly on ChromaDB.

Usage:
    python analyze.py "topic"
    python analyze.py "topic" --output report.md
    python analyze.py "topic" --sources 80 --sections inflation,compression
    python analyze.py --list-topics
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table

load_dotenv()

console = Console()

SECTION_NAMES = {
    "inflation":    "Certainty Inflation",
    "framing":      "Framing Shift",
    "contradiction":"Contradiction Detection",
    "drift":        "Language Drift",
    "compression":  "Narrative Compression",
}


def list_topics() -> None:
    from memory.persistent_memory import _collection
    try:
        col = _collection("research_findings")
        result = col.get()
        topics = sorted({m.get("topic", "") for m in (result.get("metadatas") or []) if m.get("topic")})
        if not topics:
            console.print("[yellow]No topics found in memory.[/]")
            return
        table = Table(title="Topics in memory", show_header=True)
        table.add_column("Topic", style="cyan")
        for t in topics:
            table.add_row(t)
        console.print(table)
    except Exception as e:
        console.print(f"[red]Error reading memory:[/] {e}")


def corpus_stats(topic: str, n: int) -> None:
    from memory.persistent_memory import retrieve_findings
    findings = retrieve_findings(topic, topic=topic, n_results=n)
    by_url: dict = {}
    for f in findings:
        url = f.get("source_url", "unknown")
        by_url[url] = by_url.get(url, 0) + len(f.get("content", ""))

    table = Table(title=f"Corpus: {topic}", show_header=True, expand=False)
    table.add_column("Source URL", style="dim", no_wrap=False, max_width=60)
    table.add_column("Chars", justify="right")

    for url, chars in sorted(by_url.items(), key=lambda x: -x[1])[:20]:
        table.add_row(url, f"{chars:,}")

    console.print(table)
    console.print(f"\n[cyan]Total sources:[/] {len(by_url)} | [cyan]Total chars:[/] {sum(by_url.values()):,}")


def run_analysis(topic: str, n: int, sections: list[str], output: str | None) -> None:
    from tools.narrative_tools import NarrativeAnalysisTool

    console.print(Rule(f"[bold cyan]Narrative Analysis: {topic}[/]"))
    console.print(f"[dim]Sources requested: {n} | Sections: {', '.join(sections)}[/]\n")

    tool = NarrativeAnalysisTool()

    if sections == list(SECTION_NAMES.keys()):
        # Run full analysis
        console.print("[cyan]Running full analysis...[/]")
        result = tool._run(f'{{"topic": "{topic}", "n_sources": {n}}}')
    else:
        # Run selected sections only by calling the tool and filtering output
        console.print(f"[cyan]Running sections: {', '.join(sections)}[/]")
        result = tool._run(f'{{"topic": "{topic}", "n_sources": {n}}}')
        # Filter to requested sections
        section_headers = {
            "inflation":     "## 1. Certainty Inflation",
            "framing":       "## 2. Framing Shift",
            "contradiction": "## 3. Contradiction Detection",
            "drift":         "## 4. Language Drift",
            "compression":   "## 5. Narrative Compression",
        }
        parts = result.split("\n\n---\n\n")
        kept = [parts[0]]  # always keep header
        for section_key in sections:
            header = section_headers.get(section_key, "")
            for part in parts:
                if part.strip().startswith(header):
                    kept.append(part)
                    break
        result = "\n\n---\n\n".join(kept)

    if not result or "No stored findings" in result:
        console.print(
            f"[yellow]No findings in memory for topic: [bold]{topic}[/].\n"
            f"Run the full pipeline first: [bold]python main.py \"{topic}\"[/][/]"
        )
        return

    # Display
    console.print(Markdown(result))

    # Save
    if output:
        out_path = Path(output)
    else:
        safe_topic = "".join(c if c.isalnum() or c in "-_ " else "_" for c in topic)[:50]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        out_path = Path(f"output/narrative_{safe_topic}_{timestamp}.md")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    header = (
        f"# Narrative Analysis: {topic}\n"
        f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')} | "
        f"Sources: {n} | Sections: {', '.join(sections)}*\n\n"
    )
    out_path.write_text(header + result)
    console.print(f"\n[green]Saved:[/] {out_path.absolute()}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Standalone narrative analysis on stored research corpus",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python analyze.py "quantum computing"
  python analyze.py "CRISPR" --sections inflation,compression
  python analyze.py "cold fusion" --sources 100 --output report.md
  python analyze.py --list-topics
  python analyze.py "topic" --stats
        """,
    )
    parser.add_argument("topic", nargs="?", help="Research topic to analyze")
    parser.add_argument("--output", "-o", default="", help="Output file path (default: auto)")
    parser.add_argument("--sources", "-n", type=int, default=60,
                        help="Max sources to load from memory (default: 60)")
    parser.add_argument(
        "--sections", "-s",
        default=",".join(SECTION_NAMES.keys()),
        help=f"Comma-separated sections to run. Options: {','.join(SECTION_NAMES.keys())}",
    )
    parser.add_argument("--list-topics", action="store_true",
                        help="List all topics stored in memory and exit")
    parser.add_argument("--stats", action="store_true",
                        help="Show corpus statistics for the topic instead of running analysis")

    args = parser.parse_args()

    if args.list_topics:
        list_topics()
        return

    if not args.topic:
        parser.print_help()
        sys.exit(1)

    if args.stats:
        corpus_stats(args.topic, args.sources)
        return

    requested = [s.strip() for s in args.sections.split(",") if s.strip()]
    invalid = [s for s in requested if s not in SECTION_NAMES]
    if invalid:
        console.print(f"[red]Unknown sections:[/] {', '.join(invalid)}")
        console.print(f"Valid options: {', '.join(SECTION_NAMES.keys())}")
        sys.exit(1)

    try:
        run_analysis(
            topic=args.topic,
            n=args.sources,
            sections=requested,
            output=args.output or None,
        )
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted.[/]")
        sys.exit(0)
    except Exception as e:
        console.print(f"[red]Error:[/] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
