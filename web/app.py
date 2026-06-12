"""FastAPI web application — case file dashboard."""

import re
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import BackgroundTasks, FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from web.database import (
    add_note,
    case_stats,
    create_case,
    create_run,
    get_case,
    get_notes,
    get_run,
    get_runs,
    get_settings,
    init_db,
    list_cases,
    save_settings,
    update_case_status,
    update_run,
)

from report_html import _confidence_level, _finding_paragraphs, _parse_oracle_output

app = FastAPI(title="Case File Dashboard")
templates = Jinja2Templates(directory="web/templates")

static_path = Path("web/static")
static_path.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory="web/static"), name="static")


@app.on_event("startup")
def startup():
    init_db()


# ── Helpers ─────────────────────────────────────────────────────────────────

def _load_oracle_output(case_id: int) -> dict:
    """Load and parse Oracle's output for a case. Returns empty-valued dict if unavailable."""
    empty = {k: "" for k in [
        "finding", "margin_note", "section_i", "section_ii", "section_iii",
        "section_iv", "section_v", "section_vi", "attribution", "confidence", "signature",
    ]}
    for path in [Path(f"output/case_{case_id}/report.md"), Path("output/report.md")]:
        if path.exists():
            try:
                return _parse_oracle_output(path.read_text(encoding="utf-8"))
            except Exception:
                pass
    return empty


def _attr_line_for(filer: str, attribution_text: str) -> str:
    """Return the attribution line that mentions a specific filer."""
    for line in attribution_text.splitlines():
        if filer.lower() in line.lower():
            return line.strip()
    return ""


def _sections_toc(parsed: dict) -> list:
    """Build TOC rows (roman, title, count_label) for the six body sections."""
    def url_count(text: str) -> str:
        urls = re.findall(r"https?://\S+", text)
        return str(len(set(urls))) if urls else ""

    def has(key: str) -> bool:
        return bool(parsed.get(key, "").strip())

    return [
        ("I",   "The record",             "on file" if has("section_i")   else ""),
        ("II",  "The timeline",           "on file" if has("section_ii")  else ""),
        ("III", "Contradictions on file", "on file" if has("section_iii") else ""),
        ("IV",  "The narrative drift",    "on file" if has("section_iv")  else ""),
        ("V",   "The source inventory",   url_count(parsed.get("section_v", "")) or ("on file" if has("section_v") else "")),
        ("VI",  "The exhibits",           "on file" if has("section_vi")  else ""),
    ]


def _run_research_background(case_id: int, run_id: int, topic: str, scope: str) -> None:
    """Runs the CrewAI pipeline in a background thread."""
    try:
        from crew import build_crew
        from memory.persistent_memory import get_all_sources

        crew = build_crew(topic=topic, scope=scope, case_id=case_id)
        crew.kickoff(inputs={"topic": topic, "scope": scope})

        sources = get_all_sources(topic=topic)
        from web.database import get_notes
        add_note(
            case_id=case_id,
            content=f"The unit filed {len(sources)} items to the record.",
            source="system",
            agent="the unit",
        )
        update_run(run_id, "complete", sources_found=len(sources))
    except Exception as e:
        update_run(run_id, "failed", error=str(e))
        add_note(
            case_id=case_id,
            content=f"The unit could not complete the case. {e}",
            source="system",
            agent="the unit",
        )


# ── Routes ───────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, status: str = ""):
    cases = list_cases(status=status)
    counts = {
        "active":   sum(1 for c in list_cases("active")),
        "closed":   sum(1 for c in list_cases("closed")),
        "archived": sum(1 for c in list_cases("archived")),
        "total":    len(list_cases()),
    }
    return templates.TemplateResponse(request, "dashboard.html", {
        "cases": cases,
        "counts": counts,
        "active_filter": status,
    })


@app.get("/cases/new", response_class=HTMLResponse)
async def new_case_form(request: Request):
    return templates.TemplateResponse(request, "case_new.html")


@app.post("/cases/new")
async def create_case_post(
    request: Request,
    name: str = Form(...),
    subject_type: str = Form("topic"),
    description: str = Form(""),
    priority: str = Form("medium"),
    tags: str = Form(""),
):
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    case = create_case(
        name=name,
        subject_type=subject_type,
        description=description,
        priority=priority,
        tags=tag_list,
    )
    return RedirectResponse(f"/cases/{case['id']}", status_code=303)


@app.get("/cases/{case_id}", response_class=HTMLResponse)
async def case_detail(request: Request, case_id: int):
    case = get_case(case_id)
    if not case:
        return HTMLResponse("Case not found", status_code=404)
    notes = get_notes(case_id)
    runs = get_runs(case_id)
    stats = case_stats(case_id)

    # Pull relevant findings from memory
    findings = []
    try:
        from memory.persistent_memory import retrieve_findings
        findings = retrieve_findings(case["name"], topic=case["name"], n_results=20)
    except Exception:
        pass

    return templates.TemplateResponse(request, "case_detail.html", {
        "case": case,
        "notes": notes,
        "runs": runs,
        "stats": stats,
        "findings": findings,
    })


@app.post("/cases/{case_id}/notes")
async def add_note_post(
    case_id: int,
    content: str = Form(...),
    source: str = Form("manual"),
):
    case = get_case(case_id)
    if not case:
        return HTMLResponse("Case not found", status_code=404)
    add_note(case_id=case_id, content=content, source=source)
    return RedirectResponse(f"/cases/{case_id}", status_code=303)


@app.post("/cases/{case_id}/research")
async def run_research(
    case_id: int,
    scope: str = Form(""),
):
    case = get_case(case_id)
    if not case:
        return HTMLResponse("Case not found", status_code=404)

    run = create_run(case_id=case_id, scope=scope)
    add_note(
        case_id=case_id,
        content=f"The unit convened — session #{run['id']}. Scope: {scope or 'unrestricted'}.",
        source="system",
        agent="the unit",
    )

    thread = threading.Thread(
        target=_run_research_background,
        args=(case_id, run["id"], case["name"], scope),
        daemon=True,
    )
    thread.start()

    return RedirectResponse(f"/cases/{case_id}/operations?run_id={run['id']}", status_code=303)


@app.post("/cases/{case_id}/status")
async def update_status(case_id: int, status: str = Form(...)):
    update_case_status(case_id, status)
    return RedirectResponse(f"/cases/{case_id}", status_code=303)


@app.get("/cases/{case_id}/runs/{run_id}/status")
async def run_status(case_id: int, run_id: int):
    run = get_run(run_id)
    if not run:
        return JSONResponse({"status": "unknown"})
    return JSONResponse({
        "status": run["status"],
        "sources_found": run["sources_found"],
        "findings_count": run["findings_count"],
        "completed_at": run["completed_at"],
        "error": run["error"],
    })


@app.get("/cases/{case_id}/file", response_class=HTMLResponse)
async def case_file_view(request: Request, case_id: int):
    case = get_case(case_id)
    if not case:
        return HTMLResponse("Case not found", status_code=404)
    notes = get_notes(case_id)
    runs = get_runs(case_id)
    stats = case_stats(case_id)
    findings = []
    try:
        from memory.persistent_memory import retrieve_findings
        findings = retrieve_findings(case["name"], topic=case["name"], n_results=50)
    except Exception:
        pass

    parsed = _load_oracle_output(case_id)
    fp = _finding_paragraphs(parsed.get("finding", ""))
    attr = parsed.get("attribution", "")
    confidence_body = parsed.get("confidence", "")

    bound_at = datetime.utcnow().strftime("%Y-%m-%d  %H:%M UTC")
    return templates.TemplateResponse(request, "case_file.html", {
        "case": case,
        "notes": notes,
        "runs": runs,
        "stats": stats,
        "findings": findings,
        "bound_at": bound_at,
        "finding_p1": fp[0] if len(fp) > 0 else "",
        "finding_p2": fp[1] if len(fp) > 1 else "",
        "finding_p3": fp[2] if len(fp) > 2 else "",
        "margin_note": parsed.get("margin_note", ""),
        "sections_toc": _sections_toc(parsed),
        "attribution_oracle":      _attr_line_for("Oracle",      attr),
        "attribution_nexus":       _attr_line_for("Nexus",       attr),
        "attribution_ghost":       _attr_line_for("Ghost",       attr),
        "attribution_infiltrator": _attr_line_for("Infiltrator", attr),
        "confidence_level":  _confidence_level(confidence_body) if confidence_body else "",
        "confidence_reason": confidence_body,
    })


@app.get("/cases/{case_id}/operations", response_class=HTMLResponse)
async def operations_room(request: Request, case_id: int, run_id: int = 0):
    case = get_case(case_id)
    if not case:
        return HTMLResponse("Case not found", status_code=404)
    run = get_run(run_id) if run_id else None
    if not run:
        runs = get_runs(case_id)
        run = runs[0] if runs else None
    return templates.TemplateResponse(request, "operations.html", {
        "case": case,
        "run": run,
    })


# ── Filer data ────────────────────────────────────────────────────────────────

_FILER_DATA = {
    "infiltrator": {
        "num": "01", "name": "Infiltrator",
        "color": "var(--filer-infiltrator)", "tint": "var(--filer-infiltrator-tint)",
        "role": "finds what search misses",
        "para_a": (
            "Infiltrator works the public web at depth. Search operators, API endpoints, "
            "government document portals, GitHub repositories, paste sites, mailing list archives, "
            "Common Crawl indexes. Infiltrator goes into places search engines don't surface and "
            "returns with a source map — the full inventory of what exists before the unit moves on it."
        ),
        "para_b": (
            "The source map is Infiltrator's deliverable. Not the content — the map. "
            "Every source logged: URL, type, relevance, live or archived. "
            "Infiltrator does not extract, does not analyze, does not write. "
            "Infiltrator finds the door and marks it on the record."
        ),
        "does": [
            "Maps every publicly reachable source on the subject",
            "Works search operators, dorks, and API endpoints",
            "Surfaces academic literature, government records, paste sites, and GitHub",
            "Logs all sources to the unit's memory before Ghost moves",
        ],
        "does_not": [
            "Extract or read the content of sources — that is Ghost's work",
            "Analyze patterns or relationships — that is Nexus's work",
            "Write findings or sign the file — that is Oracle's work",
            "Stop at the first page of results",
        ],
        "specimen": "Infiltrator entered Common Crawl index. 14,200 candidate URLs on subject. Reduced to 47 primary sources. Source map filed.",
        "prev": None, "next": "ghost",
    },
    "ghost": {
        "num": "02", "name": "Ghost",
        "color": "var(--filer-ghost)", "tint": "var(--filer-ghost-tint)",
        "role": "recovers what disappeared",
        "para_a": (
            "Ghost works the dead web. Wayback Machine snapshots, defunct forums, "
            "deleted press releases, dissolved subdirectories, cached versions of pages "
            "that no longer resolve. Ghost goes to the archive and returns with material "
            "that others have let go — the version of the record before it was edited."
        ),
        "para_b": (
            "Everything Ghost recovers is stored to the unit's memory with provenance intact: "
            "source URL, snapshot date, chain of custody. If a live page fails, Ghost tries "
            "the archive. If the archive fails, Ghost tries the cache. Ghost does not stop "
            "at the first retrieval failure."
        ),
        "does": [
            "Extracts full content from every source in Infiltrator's map",
            "Recovers archived and deleted material via Wayback Machine and caches",
            "Stores all recovered content with source URL and provenance",
            "Follows embedded links to primary documents when directly relevant",
        ],
        "does_not": [
            "Map new sources — that is Infiltrator's work",
            "Analyze or draw connections — that is Nexus's work",
            "Write the finding — that is Oracle's work",
            "Abandon a source after a single failed fetch",
        ],
        "specimen": "Ghost recovered 9 archived snapshots from the ICIJ leaks database. 3 pages had been deleted since Infiltrator's map. Content filed.",
        "prev": "infiltrator", "next": "nexus",
    },
    "nexus": {
        "num": "03", "name": "Nexus",
        "color": "var(--filer-nexus)", "tint": "var(--filer-nexus-tint)",
        "role": "connects the record",
        "para_a": (
            "Nexus reads the corpus Ghost filed and builds the structure. "
            "Named entities pinned and cross-referenced. Timeline reconstructed chronologically. "
            "Relationships between persons, organizations, and events mapped. "
            "Where sources agree, Nexus confirms. Where sources disagree, Nexus marks it "
            "as a contradiction on record."
        ),
        "para_b": (
            "Nexus applies three confidence tiers to every claim: CONFIRMED (two or more "
            "independent sources), REPORTED (one source only), INFERRED (no direct citation, "
            "but supported by the pattern). Nothing is collapsed or softened. "
            "Gaps in the record are identified explicitly."
        ),
        "does": [
            "Identifies all named entities across the full corpus",
            "Reconstructs the chronological timeline with source citations",
            "Maps relationships between persons, organizations, and events",
            "Marks contradictions where sources disagree, with both sides on record",
        ],
        "does_not": [
            "Recover or extract source material — that is Ghost's work",
            "Write the finding or sign the file — that is Oracle's work",
            "Resolve contradictions unilaterally — Nexus marks them, Oracle weighs them",
            "Collapse the three confidence tiers into a single claim",
        ],
        "specimen": "Nexus marked 3 contradictions on record. 11 entities confirmed across sources. Timeline reconstructed: 14 dated entries, 2 approximate.",
        "prev": "ghost", "next": "oracle",
    },
    "oracle": {
        "num": "04", "name": "Oracle",
        "color": "var(--filer-oracle)", "tint": "var(--filer-oracle-tint)",
        "role": "writes the finding",
        "para_a": (
            "Oracle reads everything the unit filed. The source map, the recovered material, "
            "Nexus's analysis, the contradictions on record. Then Oracle writes — in a specific "
            "register: declarative, unsentimental, without hedging. "
            "The finding states what the record supports, cites the evidence specifically, "
            "and notes what the unit cannot confirm."
        ),
        "para_b": (
            "Oracle sets the confidence level and signs the file with a timestamp. "
            "The margin note is Oracle's alone: one to three sentences in the three-beat shape — "
            "what the anomaly is, why it matters, what the reader should do with it. "
            "Oracle does not do field work. Oracle reads what the others brought back and weighs it."
        ),
        "does": [
            "Reads the full corpus before writing a single word",
            "Writes the finding in three paragraphs, every claim cited",
            "Sets the confidence level with explicit reasoning",
            "Signs the file with a timestamp — the unit's final act on the case",
        ],
        "does_not": [
            "Do field work — that is Infiltrator's and Ghost's work",
            "Map entities or build timelines — that is Nexus's work",
            "Write before reading the full record",
            "Use hedging language, passive voice, or AI-register phrasing",
        ],
        "specimen": "Oracle read the record. The finding is signed. Confidence: Medium. Three contradictions noted; two material, one not elevated.",
        "prev": "nexus", "next": None,
    },
}


@app.get("/filers/{name}", response_class=HTMLResponse)
async def filer_profile(request: Request, name: str):
    filer = _FILER_DATA.get(name.lower())
    if not filer:
        return HTMLResponse("Filer not found", status_code=404)
    return templates.TemplateResponse(request, "filer_profile.html", {"filer": filer})


@app.get("/about", response_class=HTMLResponse)
async def about_page(request: Request):
    return templates.TemplateResponse(request, "about.html", {})


@app.get("/cases/{case_id}/analyze", response_class=HTMLResponse)
async def analyze_case(request: Request, case_id: int):
    case = get_case(case_id)
    if not case:
        return HTMLResponse("Case not found", status_code=404)
    analysis = ""
    try:
        from tools.narrative_tools import NarrativeAnalysisTool
        import json
        tool = NarrativeAnalysisTool()
        analysis = tool._run(json.dumps({"topic": case["name"], "n_sources": 60}))
    except Exception as e:
        analysis = f"Analysis error: {e}"
    return templates.TemplateResponse(request, "case_analyze.html", {
        "case": case,
        "analysis": analysis,
    })


@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    return templates.TemplateResponse(request, "settings.html", {
        "settings": get_settings(),
        "saved": request.query_params.get("saved") == "1",
    })


@app.post("/settings")
async def settings_save(
    request: Request,
    default_priority:     str = Form("medium"),
    default_subject_type: str = Form("topic"),
    default_scope:        str = Form(""),
    case_number_prefix:   str = Form("CASE"),
    memory_scope:         str = Form("per-case"),
    date_format:          str = Form("iso"),
):
    save_settings({
        "default_priority":     default_priority,
        "default_subject_type": default_subject_type,
        "default_scope":        default_scope.strip(),
        "case_number_prefix":   case_number_prefix.strip() or "CASE",
        "memory_scope":         memory_scope,
        "date_format":          date_format,
    })
    return RedirectResponse("/settings?saved=1", status_code=303)
