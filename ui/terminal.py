"""Live terminal dashboard for intelligence research runs."""

import sys
import threading
import time
from collections import deque
from datetime import datetime
from io import StringIO
from typing import Optional

from rich import box
from rich.columns import Columns
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

AGENTS = ["Infiltrator", "Ghost", "Nexus", "Oracle"]

AGENT_COLOR = {
    "Infiltrator": "#f59e0b",
    "Ghost":       "#a78bfa",
    "Nexus":       "#22c55e",
    "Oracle":      "#60a5fa",
}
AGENT_SYMBOL = {
    "Infiltrator": "⬡",
    "Ghost":       "◈",
    "Nexus":       "⬟",
    "Oracle":      "◉",
}

# Tool name → short label for the feed
_TOOL_LABELS = {
    "dork_search":               "DORK",
    "web_search":                "SEARCH",
    "paste_site_search":         "PASTE",
    "common_crawl_search":       "CC-INDEX",
    "news_search":               "NEWS",
    "image_search":              "IMAGE",
    "forum_archive_search":      "FORUMS",
    "public_leak_journalism":    "LEAKS",
    "extract_page":              "EXTRACT",
    "deep_crawl":                "CRAWL",
    "extract_metadata":          "META",
    "fetch_rss_feed":            "RSS",
    "wayback_search":            "WAYBACK",
    "wayback_fetch":             "WB-FETCH",
    "archive_org_search":        "ARCHIVE",
    "fetch_cached_page":         "CACHE",
    "arxiv_search":              "ARXIV",
    "github_search":             "GITHUB",
    "reddit_search":             "REDDIT",
    "whois_lookup":              "WHOIS",
    "government_docs_search":    "GOV",
    "semantic_scholar_search":   "SCHOLAR",
    "shodan_search":             "SHODAN",
    "dataset_search":            "DATASET",
    "vintage_web_search":        "VINTAGE",
    "store_memory":              "MEM-WRITE",
    "retrieve_memory":           "MEM-READ",
    "list_sources":              "SOURCES",
    "store_source_map":          "SRC-MAP",
    "get_source_map":            "SRC-GET",
    "narrative_analysis":        "NARRATIVE",
}


def _short_tool(raw: str) -> str:
    key = raw.lower().replace(" ", "_").replace("-", "_")
    return _TOOL_LABELS.get(key, raw[:12].upper())


class TerminalDashboard:
    """Manages the live Rich terminal dashboard."""

    def __init__(self, topic: str, scope: str = ""):
        self.topic = topic
        self.scope = scope
        self.start_time = datetime.now()

        self._lock = threading.Lock()
        self.current_agent: Optional[str] = None
        self.statuses = {a: "STANDBY" for a in AGENTS}
        self.tool_counts = {a: 0 for a in AGENTS}
        self.feed: deque = deque(maxlen=60)
        self.total_tools = 0
        self.sources_found = 0
        self.mem_ops = 0
        self.complete = False

        # saved real stdout/stderr — Live writes here after we redirect
        self._real_stdout = sys.stdout
        self._log_buffer = StringIO()

    # ── Callbacks ─────────────────────────────────────────────────────────────

    def step_callback(self, step_output) -> None:
        """CrewAI step_callback: fired after every agent action."""
        with self._lock:
            try:
                tool_name = ""
                tool_input = ""

                if hasattr(step_output, "tool"):
                    # LangChain AgentAction
                    tool_name = step_output.tool
                    raw_input = step_output.tool_input
                    tool_input = (
                        raw_input if isinstance(raw_input, str) else str(raw_input)
                    )[:70]
                elif isinstance(step_output, (list, tuple)) and step_output:
                    # CrewAI sometimes passes (action, observation) tuples
                    action = step_output[0]
                    if hasattr(action, "tool"):
                        tool_name = action.tool
                        raw_input = action.tool_input
                        tool_input = (
                            raw_input if isinstance(raw_input, str) else str(raw_input)
                        )[:70]

                if not tool_name:
                    return

                agent = self.current_agent or "?"
                self.tool_counts[agent] = self.tool_counts.get(agent, 0) + 1
                self.total_tools += 1

                tl = tool_name.lower()
                if any(x in tl for x in ("search", "dork", "paste", "forum", "github",
                                          "arxiv", "crawl", "scholar", "reddit", "gov",
                                          "wayback", "archive", "vintage", "shodan",
                                          "dataset", "leak")):
                    self.sources_found += 1
                if "memory" in tl or "store" in tl or "mem" in tl:
                    self.mem_ops += 1

                label = _short_tool(tool_name)
                color = AGENT_COLOR.get(agent, "white")
                ts = datetime.now().strftime("%H:%M:%S")
                snippet = tool_input.replace("\n", " ").strip()
                self.feed.appendleft(
                    f"[dim]{ts}[/]  [{color}]{agent[:3].upper()}[/]"
                    f"  [bold]{label:<10}[/]  [dim]{snippet}[/]"
                )
            except Exception:
                pass

    def task_callback(self, task_output) -> None:
        """CrewAI task_callback: fired when a task finishes."""
        pass  # agent progression driven by set_agent()

    # ── Agent lifecycle ────────────────────────────────────────────────────────

    def set_agent(self, name: str) -> None:
        with self._lock:
            if self.current_agent and self.current_agent != name:
                self.statuses[self.current_agent] = "COMPLETE"
            self.current_agent = name
            self.statuses[name] = "ACTIVE"
            color = AGENT_COLOR.get(name, "white")
            ts = datetime.now().strftime("%H:%M:%S")
            sym = AGENT_SYMBOL.get(name, "●")
            self.feed.appendleft(
                f"[dim]{ts}[/]  [{color} bold]{'─' * 4} {sym} {name.upper()} ACTIVATED {'─' * 4}[/]"
            )

    def finish(self) -> None:
        with self._lock:
            if self.current_agent:
                self.statuses[self.current_agent] = "COMPLETE"
            self.current_agent = None
            self.complete = True
            ts = datetime.now().strftime("%H:%M:%S")
            self.feed.appendleft(
                f"[dim]{ts}[/]  [bold green]{'─' * 6} RESEARCH COMPLETE {'─' * 6}[/]"
            )

    # ── Rendering ─────────────────────────────────────────────────────────────

    def _elapsed(self) -> str:
        delta = datetime.now() - self.start_time
        h, rem = divmod(int(delta.total_seconds()), 3600)
        m, s = divmod(rem, 60)
        return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"

    def _header(self) -> Panel:
        topic_disp = (self.topic[:55] + "…") if len(self.topic) > 55 else self.topic
        now = datetime.now().strftime("%Y-%m-%d  %H:%M:%S")
        t = Text()
        t.append("PROJECT BEDROCK", style="bold #f59e0b")
        t.append("  ·  ", style="dim")
        t.append(topic_disp, style="bold white")
        t.append("  ·  ", style="dim")
        t.append(now, style="dim")
        t.append("  ·  ELAPSED ", style="dim")
        t.append(self._elapsed(), style="bold cyan")
        return Panel(t, style="on #0c0c0f", border_style="#1e1e26", padding=(0, 1))

    def _agent_grid(self) -> Panel:
        cols = Table.grid(expand=True, padding=(0, 1))
        for _ in AGENTS:
            cols.add_column(ratio=1)

        cells = []
        for name in AGENTS:
            status = self.statuses[name]
            color = AGENT_COLOR[name]
            sym = AGENT_SYMBOL[name]
            tc = self.tool_counts.get(name, 0)

            t = Text()
            if status == "ACTIVE":
                t.append(f"{sym} {name.upper()}\n", style=f"bold {color}")
                t.append("● ACTIVE\n", style=f"bold {color}")
            elif status == "COMPLETE":
                t.append(f"{sym} {name.upper()}\n", style="dim")
                t.append("✓ DONE\n", style="bold green")
            else:
                t.append(f"{sym} {name.upper()}\n", style="dim #3f3f46")
                t.append("○ STANDBY\n", style="dim #3f3f46")

            t.append(f"calls: {tc}", style="dim")
            cells.append(
                Panel(t, border_style="#1e1e26", style="on #111116", padding=(0, 1))
            )

        cols.add_row(*cells)
        return Panel(
            cols,
            title="[dim]AGENTS[/]",
            border_style="#1e1e26",
            style="on #0c0c0f",
            padding=0,
        )

    def _feed_panel(self, height: int = 20) -> Panel:
        lines = list(self.feed)[: height - 2]
        if not lines:
            body = Text("Waiting for first tool call…", style="dim #3f3f46")
        else:
            body = Text.from_markup("\n".join(lines))
        return Panel(
            body,
            title="[dim]ACTIVITY FEED[/]",
            border_style="#1e1e26",
            style="on #0c0c0f",
            padding=(0, 1),
        )

    def _footer(self) -> Panel:
        t = Text()
        t.append("TOOL CALLS ", style="dim")
        t.append(str(self.total_tools), style="bold #f59e0b")
        t.append("  ·  SOURCES ", style="dim")
        t.append(str(self.sources_found), style="bold #22c55e")
        t.append("  ·  MEM OPS ", style="dim")
        t.append(str(self.mem_ops), style="bold #a78bfa")
        t.append("  ·  ACTIVE AGENT ", style="dim")
        agent = self.current_agent or ("DONE" if self.complete else "INIT")
        color = AGENT_COLOR.get(self.current_agent or "", "#60a5fa") if not self.complete else "#22c55e"
        t.append(agent, style=f"bold {color}")
        return Panel(t, style="on #0c0c0f", border_style="#1e1e26", padding=(0, 1))

    def build(self) -> Layout:
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="agents", size=8),
            Layout(name="feed"),
            Layout(name="footer", size=3),
        )
        layout["header"].update(self._header())
        layout["agents"].update(self._agent_grid())
        layout["feed"].update(self._feed_panel())
        layout["footer"].update(self._footer())
        return layout

    # ── Context manager ────────────────────────────────────────────────────────

    def start(self) -> "_DashContext":
        return _DashContext(self)


class _DashContext:
    """Context manager: redirects stdout and runs the Live display."""

    def __init__(self, db: TerminalDashboard):
        self.db = db
        self._live: Optional[Live] = None
        self._timer: Optional[threading.Timer] = None
        self._orig_stdout = None
        self._log_fh = None

    def __enter__(self) -> TerminalDashboard:
        # Redirect print() / verbose output to log
        self._orig_stdout = sys.stdout
        self._log_fh = open("output/crew_log.txt", "w", encoding="utf-8")
        sys.stdout = self._log_fh

        # Dashboard runs on a Console pointed at the real stdout
        ui_console = Console(file=self._orig_stdout, force_terminal=True)
        self._live = Live(
            self.db.build(),
            console=ui_console,
            refresh_per_second=4,
            screen=True,
        )
        self._live.start()
        self._tick()
        return self.db

    def _tick(self):
        if self._live and self._live.is_started:
            try:
                self._live.update(self.db.build())
            except Exception:
                pass
            self._timer = threading.Timer(0.25, self._tick)
            self._timer.daemon = True
            self._timer.start()

    def __exit__(self, *_):
        if self._timer:
            self._timer.cancel()
        if self._live:
            try:
                # One final render
                self._live.update(self.db.build())
                time.sleep(0.3)
            except Exception:
                pass
            self._live.stop()
        # Restore stdout
        if self._orig_stdout:
            sys.stdout = self._orig_stdout
        if self._log_fh:
            self._log_fh.close()
