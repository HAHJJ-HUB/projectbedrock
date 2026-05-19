#!/usr/bin/env python3
"""
Entry point for the CrewAI intelligence system.

Usage:
    python main.py "your research topic"
    python main.py "quantum computing" --scope "focus on recent breakthroughs 2022-2024"
    python main.py "CRISPR gene editing" --scope "focus on agricultural applications"
"""

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule

console = Console()


def validate_env() -> None:
    from config import ANTHROPIC_API_KEY
    if not ANTHROPIC_API_KEY:
        console.print(
            "[bold red]ERROR:[/] ANTHROPIC_API_KEY is not set.\n"
            "Copy .env.example to .env and add your key.",
            style="red",
        )
        sys.exit(1)


def run(topic: str, scope: str = "") -> None:
    from crew import build_crew

    os.makedirs("output", exist_ok=True)
    os.makedirs("memory", exist_ok=True)

    console.print(Rule("[bold cyan]Intelligence System — Initializing[/]"))
    console.print(
        Panel(
            f"[bold]Topic:[/] {topic}\n"
            f"[bold]Scope:[/] {scope or 'unrestricted'}\n"
            f"[bold]Time:[/] {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            title="Mission Brief",
            border_style="cyan",
        )
    )
    console.print()

    console.print("[cyan]Assembling crew: Infiltrator → Ghost → Nexus → Oracle[/]")
    crew = build_crew(topic=topic, scope=scope)

    console.print("[cyan]Initiating research sequence...[/]\n")
    result = crew.kickoff(inputs={"topic": topic, "scope": scope})

    report_path = Path("output/report.md")
    console.print()
    console.print(Rule("[bold green]Research Complete[/]"))

    if report_path.exists():
        console.print(f"\n[green]Report written to:[/] {report_path.absolute()}")
        size_kb = report_path.stat().st_size / 1024
        console.print(f"[green]Report size:[/] {size_kb:.1f} KB")
    else:
        console.print("\n[yellow]Report file not written — printing result below:[/]\n")
        console.print(str(result))

    log_path = Path("output/crew_log.txt")
    if log_path.exists():
        console.print(f"[dim]Full log:[/] {log_path.absolute()}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="CrewAI intelligence research system",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py "history of ARPANET"
  python main.py "cold fusion research" --scope "focus on experimental results"
  python main.py "Project MKUltra" --scope "use only declassified government sources"
        """,
    )
    parser.add_argument("topic", help="Research topic or question")
    parser.add_argument(
        "--scope",
        default="",
        help="Optional constraints or focus area for the research",
    )
    args = parser.parse_args()

    validate_env()

    try:
        run(topic=args.topic, scope=args.scope)
    except KeyboardInterrupt:
        console.print("\n[yellow]Research interrupted by user.[/]")
        sys.exit(0)
    except Exception as e:
        console.print(f"\n[bold red]Fatal error:[/] {e}", style="red")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
