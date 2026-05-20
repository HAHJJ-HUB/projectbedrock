"""FastAPI web application — case file dashboard."""

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
    init_db,
    list_cases,
    update_case_status,
    update_run,
)

app = FastAPI(title="Case File Dashboard")
templates = Jinja2Templates(directory="web/templates")

static_path = Path("web/static")
static_path.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory="web/static"), name="static")


@app.on_event("startup")
def startup():
    init_db()


# ── Helpers ─────────────────────────────────────────────────────────────────

def _run_research_background(case_id: int, run_id: int, topic: str, scope: str) -> None:
    """Runs the CrewAI pipeline in a background thread."""
    try:
        from crew import build_crew
        from memory.persistent_memory import get_all_sources

        crew = build_crew(topic=topic, scope=scope)
        crew.kickoff(inputs={"topic": topic, "scope": scope})

        sources = get_all_sources(topic=topic)
        from web.database import get_notes
        # Store a system note summarizing the run
        add_note(
            case_id=case_id,
            content=f"Research run complete. {len(sources)} sources discovered and extracted.",
            source="system",
            agent="pipeline",
        )
        update_run(run_id, "complete", sources_found=len(sources))
    except Exception as e:
        update_run(run_id, "failed", error=str(e))
        add_note(
            case_id=case_id,
            content=f"Research run failed: {e}",
            source="system",
            agent="pipeline",
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
        content=f"Research run #{run['id']} started. Scope: {scope or 'unrestricted'}.",
        source="system",
        agent="pipeline",
    )

    thread = threading.Thread(
        target=_run_research_background,
        args=(case_id, run["id"], case["name"], scope),
        daemon=True,
    )
    thread.start()

    return RedirectResponse(f"/cases/{case_id}", status_code=303)


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
    bound_at = datetime.utcnow().strftime("%Y-%m-%d  %H:%M UTC")
    return templates.TemplateResponse(request, "case_file.html", {
        "case": case,
        "notes": notes,
        "runs": runs,
        "stats": stats,
        "findings": findings,
        "bound_at": bound_at,
    })


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
