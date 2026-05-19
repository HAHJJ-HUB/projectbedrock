"""
Hacker-aesthetic live terminal dashboard for intelligence research runs.

Green-on-black matrix style. Each agent has a callsign and distinct color.
Tool calls stream in real-time. Full screen takeover via Rich Live.
"""

import sys
import threading
import time
from collections import deque
from datetime import datetime
from typing import Optional

from rich import box
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

# ── Color palette ──────────────────────────────────────────────────────────────
C_MATRIX   = "#00ff41"   # Matrix green — Infiltrator
C_GHOST    = "#00aaff"   # Electric blue — Ghost
C_NEXUS    = "#9966ff"   # Violet — Nexus
C_ORACLE   = "#00ddaa"   # Teal — Oracle
C_AMBER    = "#ffaa00"   # Warnings
C_RED      = "#ff3333"   # Alerts / errors
C_DIM      = "#004411"   # Dark green (dim text)
C_BORDER   = "#003300"   # Panel borders
C_MID      = "#00aa22"   # Mid green
C_SURFACE  = "#020802"   # Almost-black background

AGENTS = ["Infiltrator", "Ghost", "Nexus", "Oracle"]

CALLSIGN = {
    "Infiltrator": "PHANTOM-1",
    "Ghost":       "SPECTRE",
    "Nexus":       "CORTEX",
    "Oracle":      "AXIOM",
}

ROLE_LINE = {
    "Infiltrator": "DEEP PENETRATION",
    "Ghost":       "EXTRACTION OPS",
    "Nexus":       "PATTERN ANALYSIS",
    "Oracle":      "FINAL REPORTING",
}

AGENT_COLOR = {
    "Infiltrator": C_MATRIX,
    "Ghost":       C_GHOST,
    "Nexus":       C_NEXUS,
    "Oracle":      C_ORACLE,
}

# ── Animation frames ───────────────────────────────────────────────────────────
_SPIN  = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
_RADAR = ["◐", "◓", "◑", "◒"]

# Tool name → short ops label
_OPS = {
    "dork_search":              "DORK-SWEEP",
    "web_search":               "WEB-SCAN",
    "paste_site_search":        "PASTE-DUMP",
    "common_crawl_search":      "CC-INDEX",
    "news_search":              "NEWS-FEED",
    "image_search":             "IMG-SCAN",
    "forum_archive_search":     "FORUM-ARCH",
    "public_leak_journalism":   "LEAK-REPO",
    "extract_page":             "PAGE-PULL",
    "deep_crawl":               "DEEP-CRAWL",
    "extract_metadata":         "META-PULL",
    "fetch_rss_feed":           "RSS-FEED",
    "wayback_search":           "WB-SEARCH",
    "wayback_fetch":            "WB-FETCH",
    "archive_org_search":       "ARCH-SCAN",
    "fetch_cached_page":        "CACHE-HIT",
    "arxiv_search":             "ARXIV",
    "github_search":            "GITHUB",
    "reddit_search":            "REDDIT",
    "whois_lookup":             "WHOIS",
    "government_docs_search":   "GOV-DOCS",
    "semantic_scholar_search":  "SCHOLAR",
    "shodan_search":            "SHODAN",
    "dataset_search":           "DATASET",
    "vintage_web_search":       "VINTAGE",
    "store_memory":             "MEM-WRITE",
    "retrieve_memory":          "MEM-READ",
    "list_sources":             "SRC-LIST",
    "store_source_map":         "MAP-WRITE",
    "get_source_map":           "MAP-READ",
    "narrative_analysis":       "NARRATIVE",
}


def _op_label(raw: str) -> str:
    key = raw.lower().replace(" ", "_").replace("-", "_")
    return _OPS.get(key, raw[:12].upper())


# ── Dashboard state ────────────────────────────────────────────────────────────

class TerminalDashboard:
    """Green-on-black hacker terminal dashboard."""

    def __init__(self, topic: str, scope: str = ""):
        self.topic = topic
        self.scope = scope
        self.start_time = datetime.now()

        self._lock = threading.Lock()
        self._frame = 0

        self.current_agent: Optional[str] = None
        self.statuses = {a: "STANDBY" for a in AGENTS}
        self.tool_counts = {a: 0 for a in AGENTS}
        self.feed: deque = deque(maxlen=80)
        self.total_tools = 0
        self.vectors = 0      # sources/search calls
        self.mem_ops = 0
        self.complete = False

    # ── Callbacks ─────────────────────────────────────────────────────────────

    def step_callback(self, step_output) -> None:
        with self._lock:
            try:
                tool_name = ""
                tool_input = ""

                if hasattr(step_output, "tool"):
                    tool_name = step_output.tool
                    raw = step_output.tool_input
                    tool_input = (raw if isinstance(raw, str) else str(raw))[:72]
                elif isinstance(step_output, (list, tuple)) and step_output:
                    action = step_output[0]
                    if hasattr(action, "tool"):
                        tool_name = action.tool
                        raw = action.tool_input
                        tool_input = (raw if isinstance(raw, str) else str(raw))[:72]

                if not tool_name:
                    return

                agent = self.current_agent or "SYS"
                self.tool_counts[agent] = self.tool_counts.get(agent, 0) + 1
                self.total_tools += 1

                tl = tool_name.lower()
                if any(x in tl for x in ("search", "dork", "paste", "forum",
                                          "github", "arxiv", "crawl", "scholar",
                                          "reddit", "gov", "wayback", "archive",
                                          "vintage", "shodan", "dataset", "leak",
                                          "feed", "cache")):
                    self.vectors += 1
                if "mem" in tl or "store" in tl or "map" in tl:
                    self.mem_ops += 1

                label = _op_label(tool_name)
                color = AGENT_COLOR.get(agent, C_MATRIX)
                ts = datetime.now().strftime("%H:%M:%S")
                snippet = tool_input.replace("\n", " ").strip()
                self.feed.appendleft(
                    f"[dim]{ts}[/]  [{color}]{(CALLSIGN.get(agent, agent)):<10}[/]"
                    f"  [bold {color}]{label:<12}[/]  [dim]{snippet}[/]"
                )
            except Exception:
                pass

    def task_callback(self, _) -> None:
        pass

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    def set_agent(self, name: str) -> None:
        with self._lock:
            if self.current_agent and self.current_agent != name:
                self.statuses[self.current_agent] = "COMPLETE"
            self.current_agent = name
            self.statuses[name] = "ACTIVE"
            color = AGENT_COLOR.get(name, C_MATRIX)
            cs = CALLSIGN.get(name, name.upper())
            ts = datetime.now().strftime("%H:%M:%S")
            self.feed.appendleft(
                f"[dim]{ts}[/]  "
                f"[bold {color}]{'─'*3} {cs} // {name.upper()} ONLINE {'─'*3}[/]"
            )

    def finish(self) -> None:
        with self._lock:
            if self.current_agent:
                self.statuses[self.current_agent] = "COMPLETE"
            self.current_agent = None
            self.complete = True
            ts = datetime.now().strftime("%H:%M:%S")
            self.feed.appendleft(
                f"[dim]{ts}[/]  "
                f"[bold {C_MATRIX}]{'─'*5} BREACH COMPLETE // ALL OBJECTIVES ACHIEVED {'─'*5}[/]"
            )

    # ── Rendering ─────────────────────────────────────────────────────────────

    def _elapsed(self) -> str:
        delta = datetime.now() - self.start_time
        h, rem = divmod(int(delta.total_seconds()), 3600)
        m, s = divmod(rem, 60)
        return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"

    def _scan_bar(self, agent: str) -> str:
        """Animated scan bar for active agent, static for others."""
        status = self.statuses[agent]
        if status == "COMPLETE":
            return f"[{C_MATRIX}]{'█' * 10}[/] [bold {C_MATRIX}]DONE[/]"
        if status != "ACTIVE":
            return f"[{C_DIM}]{'░' * 10}[/] [dim]STANDBY[/]"
        # animate: sweep pos based on frame
        pos = self._frame % 10
        bar = "▓" * pos + "█" + "░" * (9 - pos)
        color = AGENT_COLOR.get(agent, C_MATRIX)
        spin = _SPIN[self._frame % len(_SPIN)]
        return f"[{color}]{bar}[/] [{color}]{spin}[/]"

    def _header(self) -> Panel:
        topic_disp = (self.topic[:50] + "…") if len(self.topic) > 50 else self.topic
        elapsed = self._elapsed()
        status_txt = "BREACH COMPLETE" if self.complete else (
            f"ACTIVE // {CALLSIGN.get(self.current_agent, 'INIT')}" if self.current_agent else "INITIALIZING"
        )
        status_color = C_MATRIX if self.complete else C_AMBER

        t = Text()
        t.append("  BEDROCK", style=f"bold {C_MATRIX}")
        t.append(" // ", style=f"dim {C_DIM}")
        t.append("INTELLIGENCE SYSTEM", style=f"dim {C_MID}")
        t.append("  ▸  ", style=f"dim {C_DIM}")
        t.append(topic_disp.upper(), style="bold white")
        t.append("  ▸  ", style=f"dim {C_DIM}")
        t.append(datetime.now().strftime("%Y-%m-%d %H:%M:%S"), style=f"dim {C_DIM}")
        t.append("  ▸  ELAPSED ", style=f"dim {C_DIM}")
        t.append(elapsed, style=f"bold {C_MATRIX}")
        t.append("  ▸  ", style=f"dim {C_DIM}")
        t.append(status_txt, style=f"bold {status_color}")
        t.append("  ", style="")
        return Panel(t, style=f"on #000000", border_style=C_BORDER, padding=(0, 0))

    def _agent_cell(self, name: str) -> Panel:
        status = self.statuses[name]
        color = AGENT_COLOR.get(name, C_MATRIX)
        cs = CALLSIGN[name]
        role = ROLE_LINE[name]
        tc = self.tool_counts.get(name, 0)

        t = Text()
        # Callsign + name
        if status == "ACTIVE":
            t.append(f" {cs}\n", style=f"bold {color}")
        elif status == "COMPLETE":
            t.append(f" {cs}\n", style=f"dim {C_MID}")
        else:
            t.append(f" {cs}\n", style=f"dim {C_DIM}")

        t.append(f" {role}\n", style=f"dim {C_DIM}")
        t.append(" ", style="")
        t.append_text(Text.from_markup(self._scan_bar(name)))
        t.append(f"\n OPS: {tc}", style=f"dim {C_MID}")

        border = color if status == "ACTIVE" else (C_MID if status == "COMPLETE" else C_BORDER)
        return Panel(t, border_style=border, style="on #000000", padding=(0, 0))

    def _agent_grid(self) -> Panel:
        grid = Table.grid(expand=True, padding=0)
        for _ in AGENTS:
            grid.add_column(ratio=1)
        grid.add_row(*[self._agent_cell(a) for a in AGENTS])
        return Panel(
            grid,
            title=f"[{C_DIM}]── AGENTS ──[/]",
            border_style=C_BORDER,
            style="on #000000",
            padding=0,
        )

    def _feed_panel(self) -> Panel:
        lines = list(self.feed)[:22]
        if not lines:
            body = Text("Awaiting breach initiation...", style=f"dim {C_DIM}")
        else:
            body = Text.from_markup("\n".join(lines))
        return Panel(
            body,
            title=f"[{C_DIM}]── LIVE BREACH FEED ──[/]",
            border_style=C_BORDER,
            style="on #000000",
            padding=(0, 1),
        )

    def _footer(self) -> Panel:
        t = Text()
        t.append("  OPS ", style=f"dim {C_DIM}")
        t.append(f"{self.total_tools:<6}", style=f"bold {C_MATRIX}")
        t.append("  VECTORS ", style=f"dim {C_DIM}")
        t.append(f"{self.vectors:<6}", style=f"bold {C_GHOST}")
        t.append("  MEM_WRITES ", style=f"dim {C_DIM}")
        t.append(f"{self.mem_ops:<6}", style=f"bold {C_NEXUS}")
        t.append("  ACTIVE ", style=f"dim {C_DIM}")
        if self.complete:
            t.append("ALL OBJECTIVES COMPLETE", style=f"bold {C_MATRIX}")
        elif self.current_agent:
            cs = CALLSIGN.get(self.current_agent, self.current_agent.upper())
            color = AGENT_COLOR.get(self.current_agent, C_MATRIX)
            t.append(f"{cs} // {self.current_agent.upper()}", style=f"bold {color}")
        else:
            t.append("INITIALIZING", style=f"dim {C_DIM}")
        t.append("  ", style="")
        return Panel(t, style="on #000000", border_style=C_BORDER, padding=(0, 0))

    def build(self) -> Layout:
        self._frame += 1
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="agents", size=7),
            Layout(name="feed"),
            Layout(name="footer", size=3),
        )
        layout["header"].update(self._header())
        layout["agents"].update(self._agent_grid())
        layout["feed"].update(self._feed_panel())
        layout["footer"].update(self._footer())
        return layout

    def start(self) -> "_DashContext":
        return _DashContext(self)


# ── Context manager ────────────────────────────────────────────────────────────

class _DashContext:
    def __init__(self, db: TerminalDashboard):
        self.db = db
        self._live: Optional[Live] = None
        self._timer: Optional[threading.Timer] = None
        self._orig_stdout = None
        self._log_fh = None

    def __enter__(self) -> TerminalDashboard:
        import os
        os.makedirs("output", exist_ok=True)
        self._orig_stdout = sys.stdout
        self._log_fh = open("output/crew_log.txt", "w", encoding="utf-8")
        sys.stdout = self._log_fh

        ui_console = Console(
            file=self._orig_stdout,
            force_terminal=True,
            force_interactive=True,
            color_system="truecolor",
        )
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
                self._live.update(self.db.build())
                time.sleep(0.4)
            except Exception:
                pass
            self._live.stop()
        if self._orig_stdout:
            sys.stdout = self._orig_stdout
        if self._log_fh:
            self._log_fh.close()
