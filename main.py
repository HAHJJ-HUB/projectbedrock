#!/usr/bin/env python3
"""
Entry point for the CrewAI intelligence system.

Usage:
    python main.py "your research topic"
    python main.py "quantum computing" --scope "focus on recent breakthroughs 2022-2024"
    python main.py "CRISPR gene editing" --no-ui     # plain Rich output, no dashboard
    python main.py "topic" --html                    # also generate HTML report
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


def run(topic: str, scope: str = "", use_ui: bool = True, html: bool = False) -> None:
    from crew import build_crew

    os.makedirs("output", exist_ok=True)
    os.makedirs("memory", exist_ok=True)

    # ── Choose UI mode ─────────────────────────────────────────────────────────
    if use_ui and sys.stdout.isatty():
        _run_with_dashboard(topic=topic, scope=scope, html=html)
    else:
        _run_plain(topic=topic, scope=scope, html=html)


def _run_with_dashboard(topic: str, scope: str, html: bool) -> None:
    """Full live terminal dashboard mode."""
    from crew import build_crew
    from ui.terminal import TerminalDashboard

    dashboard = TerminalDashboard(topic=topic, scope=scope)

    # Agent progression: task_callback fires when each task finishes.
    # We track which agent index we're on and advance accordingly.
    _agent_order = ["Infiltrator", "Ghost", "Nexus", "Oracle"]
    _task_counter = [0]

    def _task_cb(task_output):
        idx = _task_counter[0]
        _task_counter[0] += 1
        next_idx = _task_counter[0]
        if next_idx < len(_agent_order):
            dashboard.set_agent(_agent_order[next_idx])

    # Activate Infiltrator immediately on start
    dashboard.set_agent("Infiltrator")

    crew = build_crew(
        topic=topic,
        scope=scope,
        step_callback=dashboard.step_callback,
        task_callback=_task_cb,
    )

    result = None
    with dashboard.start():
        result = crew.kickoff(inputs={"topic": topic, "scope": scope})
        dashboard.finish()

    # Back to normal console after dashboard exits
    report_path = Path("output/report.md")
    console.print()
    console.print(Rule("[bold green]Research Complete[/]"))

    if report_path.exists():
        console.print(f"\n[green]Report:[/] {report_path.absolute()}")
        size_kb = report_path.stat().st_size / 1024
        console.print(f"[green]Size:[/]   {size_kb:.1f} KB")
        if html:
            _generate_html(report_path, topic, scope)
    else:
        console.print("\n[yellow]Report file not found — raw result:[/]\n")
        console.print(str(result))

    console.print(f"[dim]Log:[/] output/crew_log.txt")


def _run_plain(topic: str, scope: str, html: bool) -> None:
    """Simple Rich output for non-TTY or --no-ui mode."""
    from crew import build_crew

    console.print(Rule("[bold cyan]Intelligence System — Initializing[/]"))
    console.print(
        Panel(
            f"[bold]Topic:[/] {topic}\n"
            f"[bold]Scope:[/] {scope or 'unrestricted'}\n"
            f"[bold]Time:[/]  {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            title="Mission Brief",
            border_style="cyan",
        )
    )
    console.print("[cyan]Assembling crew: Infiltrator → Ghost → Nexus → Oracle[/]")
    crew = build_crew(topic=topic, scope=scope)

    console.print("[cyan]Initiating research sequence...[/]\n")
    result = crew.kickoff(inputs={"topic": topic, "scope": scope})

    report_path = Path("output/report.md")
    console.print()
    console.print(Rule("[bold green]Research Complete[/]"))

    if report_path.exists():
        console.print(f"\n[green]Report:[/] {report_path.absolute()}")
        size_kb = report_path.stat().st_size / 1024
        console.print(f"[green]Size:[/]   {size_kb:.1f} KB")
        if html:
            _generate_html(report_path, topic, scope)
    else:
        console.print("\n[yellow]Report file not written — printing result:[/]\n")
        console.print(str(result))

    log_path = Path("output/crew_log.txt")
    if log_path.exists():
        console.print(f"[dim]Log:[/] {log_path.absolute()}")


def _generate_html(report_path: Path, topic: str, scope: str) -> None:
    try:
        from report_html import convert
        html_path = report_path.with_suffix(".html")
        convert(report_path, html_path, topic=topic, scope=scope)
        console.print(f"[green]HTML:[/]   {html_path.absolute()}")
    except Exception as e:
        console.print(f"[yellow]HTML generation failed:[/] {e}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="CrewAI intelligence research system",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py "history of ARPANET"
  python main.py "cold fusion research" --scope "focus on experimental results"
  python main.py "Project MKUltra" --scope "declassified sources only" --html
  python main.py "topic" --no-ui          # plain output (no live dashboard)
        """,
    )
    parser.add_argument("topic", help="Research topic or question")
    parser.add_argument(
        "--scope",
        default="",
        help="Optional constraints or focus area for the research",
    )
    parser.add_argument(
        "--no-ui",
        dest="no_ui",
        action="store_true",
        help="Disable live terminal dashboard (plain Rich output)",
    )
    parser.add_argument(
        "--html",
        action="store_true",
        help="Generate a styled HTML report alongside report.md",
    )
    args = parser.parse_args()

    validate_env()

    try:
        run(
            topic=args.topic,
            scope=args.scope,
            use_ui=not args.no_ui,
            html=args.html,
        )
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
