"""FastAPI web application — case file dashboard."""

import json
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
    get_notes_since,
    get_run,
    get_runs,
    get_settings,
    init_db,
    list_cases,
    save_settings,
    set_filer_state,
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


def _confidence_for_url(url: str) -> tuple[str, str]:
    """Derive a confidence tier from the source domain. Returns (tier, basis)."""
    u = (url or "").lower()
    if any(t in u for t in (".gov", ".mil", "courtlistener", "sec.gov",
                            "archives.gov", "supremecourt", "europa.eu")):
        return "High", "official record"
    if any(t in u for t in (".edu", "scholar.", "arxiv.", "jstor",
                            "ncbi.nlm", "doi.org", "pubmed")):
        return "High", "academic source"
    if any(t in u for t in (".org", "reuters", "apnews", "bbc.", "nytimes",
                            "washingtonpost", "theguardian", "propublica")):
        return "Medium", "established publication"
    if any(t in u for t in ("reddit", "twitter", "x.com", "pastebin",
                            "medium.com", "substack", "blogspot", "wordpress")):
        return "Low", "self-published"
    if "web.archive.org" in u or "archive.ph" in u:
        return "Medium", "archived capture"
    return "Unverified", "source not yet rated"


def _domain_of(url: str) -> str:
    m = re.search(r"https?://([^/]+)", url or "")
    return m.group(1).replace("www.", "") if m else (url or "—")


def _build_evidence(findings: list) -> list:
    """Numbered evidence inventory — each item is a citation anchor [n]."""
    evidence = []
    for i, f in enumerate(findings, start=1):
        url = f.get("source_url", "") if isinstance(f, dict) else getattr(f, "source_url", "")
        content = f.get("content", "") if isinstance(f, dict) else getattr(f, "content", "")
        tier, basis = _confidence_for_url(url)
        evidence.append({
            "n": i,
            "url": url,
            "domain": _domain_of(url),
            "snippet": (content[:240] + "…") if len(content) > 240 else content,
            "confidence": tier,
            "basis": basis,
        })
    return evidence


def _build_record_timeline(notes: list) -> list:
    """Timeline of record — every item carries date + source + confidence."""
    source_conf = {
        "manual":  ("Recorded",     "filer's own observation"),
        "system":  ("Logged",       "unit operations log"),
        "unit":    ("Logged",       "unit operations log"),
    }
    items = []
    for note in notes:
        src = note.get("source", "manual")
        agent = note.get("agent") or ""
        if src in ("system", "unit"):
            label = "the unit"
        elif agent:
            label = agent
        else:
            label = src
        conf, basis = source_conf.get(src, ("Corroborated", "filed to the record"))
        items.append({
            "date": (note.get("created_at", "")[:16] or "").replace("T", " "),
            "source": label,
            "confidence": conf,
            "basis": basis,
            "content": note.get("content", ""),
        })
    return items


def _extract_contradictions(parsed: dict) -> list:
    """Parse Oracle's contradictions section into source-paired records.

    Each contradiction on the record is held as a pair: the two accounts that
    do not agree. Returns [] when none are on file.
    """
    text = parsed.get("section_iii", "").strip()
    if not text:
        return []
    pairs = []
    # Split on blank lines / bullet markers; each block is one contradiction.
    blocks = re.split(r"\n\s*\n|\n\s*[-•*]\s+", text)
    for block in blocks:
        block = block.strip()
        if len(block) < 12:
            continue
        urls = re.findall(r"https?://\S+", block)
        # A contradiction is a pair: split the prose on an adversative hinge.
        split = re.split(r"\b(?:however|whereas|but|contradict[s]?|disputes?|conversely|against this)\b",
                         block, maxsplit=1, flags=re.IGNORECASE)
        account_a = split[0].strip(" .;:")
        account_b = split[1].strip(" .;:") if len(split) > 1 else ""
        pairs.append({
            "account_a": account_a[:280],
            "account_b": account_b[:280],
            "source_a": _domain_of(urls[0]) if len(urls) > 0 else "source unattributed",
            "source_b": _domain_of(urls[1]) if len(urls) > 1 else "source unattributed",
        })
    return pairs[:8]


def _extract_entities(parsed: dict) -> list[dict]:
    """Extract named entities from Oracle's Section I and II output."""
    text = (parsed.get("section_i") or "") + "\n" + (parsed.get("section_ii") or "")
    entities: list[dict] = []
    seen: set[str] = set()

    # Persons: two or more consecutive Title-case words
    for m in re.finditer(r'\b([A-Z][a-z]{1,}(?:\s[A-Z][a-z]+){1,2})\b', text):
        name = m.group(1)
        if name not in seen and len(name) > 5:
            seen.add(name)
            entities.append({"id": f"p{len(entities)}", "type": "person",
                              "label": name, "detail": ""})

    # Organisations: suffixed with a recognisable institutional word
    org_re = (r'\b([A-Z][A-Za-z\s&\-]{2,42}'
              r'(?:Corp(?:oration)?|Ltd|Inc|LLC|Authority|Council|Agency|'
              r'Department|Ministry|Institute|Foundation|Association|Group|'
              r'Company|Commission|Bureau|Office|Organisation|Organization|'
              r'Service|Trust|Fund|Bank|University|College))\b')
    for m in re.finditer(org_re, text):
        name = m.group(1).strip()
        if name not in seen:
            seen.add(name)
            entities.append({"id": f"o{len(entities)}", "type": "organisation",
                              "label": name, "detail": ""})

    return entities[:40]


def _finding_status(runs: list, has_finding: bool, contradictions: int) -> dict:
    """Finding status: draft / bound / disputed / revised — with a basis line."""
    complete = [r for r in runs if r.get("status") == "complete"]
    if not has_finding or not complete:
        return {"key": "draft",
                "label": "Draft",
                "basis": "the unit has not yet bound this file"}
    if contradictions > 0:
        return {"key": "disputed",
                "label": "Disputed",
                "basis": f"{contradictions} contradiction{'s' if contradictions != 1 else ''} on the record"}
    if len(complete) > 1:
        return {"key": "revised",
                "label": "Revised",
                "basis": f"rebuilt across {len(complete)} sittings"}
    return {"key": "bound",
            "label": "Bound",
            "basis": "signed by Oracle, no contradictions on record"}


def _make_task_callback(case_id: int, run_id: int):
    """Returns a task_callback that logs filer milestones and updates filer_state."""
    _SEQUENCE = ["infiltrator", "ghost", "nexus", "oracle"]
    _MSGS = {
        "infiltrator": "Infiltrator filed the source map.",
        "ghost":       "Ghost extracted and filed the record.",
        "nexus":       "Nexus filed the analysis. Board marked.",
        "oracle":      "Oracle signed the file.",
    }
    completed = [0]
    state: dict = {}

    def callback(output):
        try:
            idx = completed[0]
            filer = _SEQUENCE[min(idx, 3)]
            raw = getattr(output, "raw", None) or getattr(output, "result", None) or str(output)
            url_count = len(re.findall(r"https?://", raw or ""))
            state[filer] = {"status": "complete", "items": url_count, "summary": _MSGS[filer]}
            set_filer_state(run_id, state)
            add_note(case_id=case_id, content=_MSGS[filer], source="unit", agent=filer)
        except Exception:
            pass
        finally:
            completed[0] += 1

    return callback


def _run_research_background(case_id: int, run_id: int, topic: str, scope: str) -> None:
    """Runs the CrewAI pipeline in a background thread."""
    try:
        from crew import build_crew
        from memory.persistent_memory import get_all_sources

        task_cb = _make_task_callback(case_id, run_id)
        crew = build_crew(topic=topic, scope=scope, case_id=case_id, task_callback=task_cb)
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
    return templates.TemplateResponse(request, "case_new.html", {
        "defaults": get_settings(),
    })


@app.post("/cases/new")
async def create_case_post(
    request: Request,
    name: str = Form(...),
    subject_type: str = Form("topic"),
    priority: str = Form("medium"),
    sensitivity: str = Form("standard"),
    objective: str = Form(""),
    key_questions: str = Form(""),
    timeline_range: str = Form(""),
    jurisdiction: str = Form(""),
    known_sources: str = Form(""),
    description: str = Form(""),
    scope: str = Form(""),
    tags: str = Form(""),
):
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    case = create_case(
        name=name,
        subject_type=subject_type,
        description=description,
        priority=priority,
        tags=tag_list,
        objective=objective.strip(),
        key_questions=key_questions.strip(),
        timeline_range=timeline_range.strip(),
        jurisdiction=jurisdiction.strip(),
        known_sources=known_sources.strip(),
        scope=scope.strip(),
        sensitivity=sensitivity,
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


@app.post("/cases/{case_id}/deepen")
async def deepen_case(case_id: int):
    case = get_case(case_id)
    if not case:
        return HTMLResponse("Case not found", status_code=404)

    # Pull gap text from Oracle's most recent completed output
    parsed = _load_oracle_output(case_id)
    gap_text = ""
    if parsed:
        # section_iv = "The narrative drift" — Oracle flags gaps and anomalies here
        gap_text = (parsed.get("section_iv") or "").strip()
        if not gap_text:
            # Fall back to last paragraph of section_iii
            s3 = (parsed.get("section_iii") or "").strip()
            if s3:
                gap_text = s3.split("\n\n")[-1].strip()

    scope = f"Second pass — chase the gaps Oracle identified:\n\n{gap_text}" if gap_text else "Second pass — deepen the record; chase anything unresolved from the first run."

    run = create_run(case_id=case_id, scope=scope)
    add_note(
        case_id=case_id,
        content=f"Unit reconvened — session #{run['id']}. Deepening the record.",
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

    # Per-filer state
    filer_state: dict = {}
    raw_state = run.get("filer_state") or "{}"
    try:
        filer_state = json.loads(raw_state)
    except Exception:
        pass

    # Recent log lines (unit notes written during this run)
    log_lines: list = []
    run_started = run.get("started_at") or ""
    if run_started:
        try:
            notes = get_notes_since(case_id, run_started, limit=25)
            for n in notes:  # newest first; JS will reverse
                log_lines.append({
                    "ts":    (n.get("created_at") or "")[:19].replace("T", " "),
                    "agent": (n.get("agent") or "unit").lower(),
                    "msg":   (n.get("content") or "")[:120],
                })
        except Exception:
            pass

    return JSONResponse({
        "status":         run["status"],
        "sources_found":  run["sources_found"],
        "findings_count": run["findings_count"],
        "completed_at":   run["completed_at"],
        "error":          run["error"],
        "filer_state":    filer_state,
        "log_lines":      log_lines,
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

    # Structured records — citation anchors, source-paired contradictions,
    # dated/sourced/rated timeline, and an overall finding status.
    evidence       = _build_evidence(findings)
    contradictions = _extract_contradictions(parsed)
    record_timeline = _build_record_timeline(notes)
    finding_status = _finding_status(runs, bool(fp), len(contradictions))

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
        "evidence":        evidence,
        "contradictions":  contradictions,
        "record_timeline": record_timeline,
        "finding_status":  finding_status,
    })


@app.get("/cases/{case_id}/operations", response_class=HTMLResponse)
async def operations_room(request: Request, case_id: int, run_id: int = 0):
    case = get_case(case_id)
    if not case:
        return HTMLResponse("Case not found", status_code=404)
    run = None
    if run_id:
        run = get_run(run_id)
        if not run:
            # Explicit run_id given but not found — fall back to most recent
            runs = get_runs(case_id)
            run = runs[0] if runs else None
    # If no run_id in URL: show activation sequence with no polling (run=None)
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


# ── Board ────────────────────────────────────────────────────────────────────

@app.get("/cases/{case_id}/board", response_class=HTMLResponse)
async def board_view(request: Request, case_id: int):
    case = get_case(case_id)
    if not case:
        return HTMLResponse("Case not found", status_code=404)
    return templates.TemplateResponse(request, "board.html", {"case": case})


@app.get("/cases/{case_id}/board/data")
async def board_data_api(case_id: int):
    case = get_case(case_id)
    if not case:
        return JSONResponse({"error": "not found"}, status_code=404)

    findings: list = []
    try:
        from memory.persistent_memory import retrieve_findings
        findings = retrieve_findings(case["name"], topic=case["name"], n_results=30)
    except Exception:
        pass

    parsed = _load_oracle_output(case_id)
    evidence = _build_evidence(findings)
    contradictions = _extract_contradictions(parsed)
    entities = _extract_entities(parsed)

    return JSONResponse({
        "entities": entities,
        "sources": [
            {
                "id": f"s{e['n']}",
                "type": "source",
                "label": e["domain"],
                "detail": e["snippet"][:100] if e["snippet"] else "",
                "url": e["url"],
                "confidence": e["confidence"],
            }
            for e in evidence[:16]
        ],
        "contradictions": [
            {
                "id": f"c{i}",
                "type": "contradiction",
                "label": "Contradiction on record",
                "detail": f"{c['source_a']} vs {c['source_b']}",
                "account_a": c["account_a"][:80],
                "account_b": c["account_b"][:80],
            }
            for i, c in enumerate(contradictions)
        ],
    })


# ── DTN Tactics ───────────────────────────────────────────────────────────────

_TACTIC_DATA = [
    {"id": "authority", "name": "Authority", "strength": "High",
     "description": "Invoking credentials, official status, or expert consensus to establish claims without evidence. The authority may be real, exaggerated, or fabricated.",
     "detection": ["Claims citing unnamed experts or 'studies show'", "Credentials emphasised disproportionately to argument quality", "Official channels invoked to shut down inquiry"],
     "countermeasures": ["Request primary sources, not summaries", "Verify credentials independently", "Evaluate the argument on its own merits"]},
    {"id": "framing", "name": "Framing", "strength": "High",
     "description": "Controlling which aspects of an issue are presented, which language is used, and which context is provided — to pre-determine how the audience interprets events before thinking begins.",
     "detection": ["Strong word choices that load the conclusion", "Consistent omission of context that would change the picture", "Stories structured so only one reading is available"],
     "countermeasures": ["Identify what is not being said", "Test alternative framings of the same facts", "Ask who benefits from this framing"]},
    {"id": "cherry-picking", "name": "Cherry-Picking", "strength": "Medium",
     "description": "Selecting only evidence that supports a predetermined conclusion while suppressing contradicting evidence. The selected evidence may be accurate; the problem is what is excluded.",
     "detection": ["Unusually clean data sets with no contradictions", "Statistics cited without base rates or comparison", "Historical examples drawn from non-representative periods"],
     "countermeasures": ["Search for disconfirming evidence actively", "Ask for the full dataset, not just examples", "Look for what time period or population was excluded"]},
    {"id": "gaslighting", "name": "Gaslighting", "strength": "High",
     "description": "Causing a target to doubt their own perception, memory, or judgment. Denying events that occurred, reinterpreting past statements, or asserting the target misunderstood what they clearly witnessed.",
     "detection": ["Denials that contradict documented evidence", "Claims that the target is confused or misremembering", "Statements reframed as 'taken out of context' without the context provided"],
     "countermeasures": ["Maintain contemporaneous records", "Rely on documented evidence, not memory alone", "Seek corroboration from independent sources"]},
    {"id": "repetition", "name": "Repetition", "strength": "High",
     "description": "Repeating a claim frequently enough that it becomes accepted as fact through familiarity. The illusory truth effect: repeated exposure increases perceived credibility regardless of accuracy.",
     "detection": ["Identical language appearing across multiple independent-seeming sources", "Claims that 'everyone knows' something without a sourced origin", "A narrative that appears simultaneously across unrelated channels"],
     "countermeasures": ["Trace claims to their original source", "Evaluate evidence each time a claim is encountered, not cumulatively", "Check for coordinated messaging behind apparent independent agreement"]},
    {"id": "false-equivalence", "name": "False Equivalence", "strength": "Medium",
     "description": "Presenting two things as equal in significance or credibility when they are not. Used to artificially balance a debate, legitimise fringe positions, or manufacture controversy where consensus exists.",
     "detection": ["'Both sides' framing applied to one-sided factual questions", "Expert consensus placed alongside minority dissent as equal", "Moral equivalence drawn between unequal acts"],
     "countermeasures": ["Assess the weight of evidence on each side independently", "Distinguish opinion from factual questions", "Ask whether the two positions actually make equivalent claims"]},
    {"id": "straw-man", "name": "Straw Man", "strength": "Medium",
     "description": "Misrepresenting an opponent's position in a weakened or exaggerated form, then attacking that false version. The real position is never engaged.",
     "detection": ["Characterisations of the opposing view that its proponents would reject", "Quotes taken out of context to imply positions not held", "Extreme versions of a position used to represent mainstream variants"],
     "countermeasures": ["Verify characterisations against primary sources", "Ask the opponent whether the representation is accurate", "Steel-man the opposing argument before evaluating it"]},
    {"id": "ad-hominem", "name": "Ad Hominem", "strength": "Low",
     "description": "Attacking the person making an argument rather than the argument itself. Used to discredit a source without addressing the evidence or reasoning they have presented.",
     "detection": ["Responses focused on the speaker's character, history, or affiliations", "Source credibility challenged without engaging the content", "Biographical attacks that appear when evidence cannot be refuted"],
     "countermeasures": ["Evaluate arguments on their merits regardless of source", "Note when personal attacks substitute for substantive response", "Distinguish legitimate credibility concerns from irrelevant attacks"]},
    {"id": "whataboutism", "name": "Whataboutism", "strength": "Low",
     "description": "Deflecting criticism by raising a counter-accusation or comparable wrongdoing by others. Does not address the original claim but shifts the conversation to a different subject.",
     "detection": ["Counter-accusations that do not address the original point", "'What about X?' responses to specific evidence", "Competitive suffering deployed as defence"],
     "countermeasures": ["Hold the counter-accusation separate from the original claim", "Acknowledge the counter-point may be valid without conceding the original", "Return to the evidence after addressing the deflection"]},
    {"id": "moving-goalposts", "name": "Moving the Goalposts", "strength": "Medium",
     "description": "Changing the criteria for evidence or proof each time the original criteria are met. The demands escalate to ensure the conclusion can never be confirmed.",
     "detection": ["New evidentiary demands that appear after previous ones are satisfied", "Standards that shift in specificity or type", "Claims that more evidence is always needed without defining sufficiency"],
     "countermeasures": ["Record the stated criteria before evidence is presented", "Hold the standard fixed once agreed", "Name the shift when it occurs"]},
    {"id": "false-urgency", "name": "False Urgency", "strength": "Medium",
     "description": "Manufacturing time pressure to prevent careful evaluation. The urgency compels action before scrutiny is possible, exploiting the tendency to prioritise speed over accuracy under perceived threat.",
     "detection": ["Tight deadlines on decisions that do not require them", "Consequences of inaction described as immediate and severe", "Pressure to act before all information is available"],
     "countermeasures": ["Test whether the urgency is real by questioning its basis", "Slow down when pressure is applied unexpectedly", "Ask who benefits from a fast decision"]},
    {"id": "manufactured-consent", "name": "Manufactured Consent", "strength": "High",
     "description": "Creating the appearance of broad public or expert agreement where none exists. Achieved through coordinated messaging, astroturfing, or suppressing dissent.",
     "detection": ["Claims of consensus without citation of polling or evidence", "Multiple sources using identical language without attribution", "Apparent grassroots support with coordinated messaging"],
     "countermeasures": ["Trace apparent consensus to its source", "Check for astroturfing or coordinated campaign structures", "Distinguish genuine agreement from managed perception"]},
    {"id": "overgeneralisation", "name": "Overgeneralisation", "strength": "Low",
     "description": "Drawing sweeping conclusions from limited, unrepresentative, or anecdotal data. The inference is larger than the evidence supports.",
     "detection": ["Specific cases presented as universal patterns", "N-of-one examples used to characterise whole populations", "Statistical findings extrapolated beyond their tested conditions"],
     "countermeasures": ["Examine the sample size and representativeness", "Ask for the base rate before evaluating anecdotes", "Identify the conditions under which the finding holds"]},
    {"id": "fear-appeal", "name": "Fear Appeal", "strength": "High",
     "description": "Using threats, danger, or worst-case scenarios to override rational deliberation. The emotional response to fear reduces willingness to evaluate evidence critically.",
     "detection": ["Threat scenarios emphasised beyond their evidential support", "Worst-case outcomes presented as likely or inevitable", "Acceptance of the actor's position framed as the only protection"],
     "countermeasures": ["Assess threat probability independently", "Evaluate whether the proposed solution actually addresses the threat", "Note when fear is invoked to prevent rather than inform evaluation"]},
    {"id": "social-proof", "name": "Social Proof", "strength": "Medium",
     "description": "Citing the behaviour or belief of a group to pressure conformity. Exploits the human tendency to look to others when uncertain, regardless of whether the group actually holds the claimed view.",
     "detection": ["Appeals to what 'most people' or 'everyone' believes without evidence", "Polling or survey data cited without methodology", "Social acceptance used as a substitute for evidence"],
     "countermeasures": ["Verify group behaviour or belief claims with independent sources", "Distinguish popularity from accuracy", "Examine whether the cited group is representative"]},
    {"id": "red-herring", "name": "Red Herring", "strength": "Low",
     "description": "Introducing irrelevant information to distract from the main argument. The new topic is designed to seem related while actually shifting the focus away from the central issue.",
     "detection": ["Topic shifts that seem relevant but do not address the core question", "Emotional or controversial tangents introduced when primary evidence is challenged", "Long responses that never return to the original point"],
     "countermeasures": ["Name the topic shift when it occurs", "Return explicitly to the original question after the tangent", "Evaluate whether the new information is actually relevant"]},
    {"id": "slippery-slope", "name": "Slippery Slope", "strength": "Low",
     "description": "Claiming that one event will inevitably lead to a chain of events culminating in a harmful outcome, without evidence for the claimed causal chain.",
     "detection": ["Chains of consequences presented without evidence for each link", "'If X then inevitably Y then inevitably Z' arguments", "Extreme final outcomes used to dismiss modest initial proposals"],
     "countermeasures": ["Evaluate each causal link independently", "Ask for evidence that the chain has occurred in analogous cases", "Separate the immediate proposal from the speculated consequences"]},
    {"id": "guilt-by-association", "name": "Guilt by Association", "strength": "Medium",
     "description": "Discrediting a person, organisation, or claim by associating them with a disreputable party, regardless of whether the association is meaningful or relevant.",
     "detection": ["Arguments structured around connections rather than conduct", "Indirect or historical associations presented as current or causal", "Legitimate relationships used to imply illegitimate ones"],
     "countermeasures": ["Evaluate the claim or conduct independently of the association", "Assess whether the association is actual, relevant, and causal", "Apply the same standard to all parties under investigation"]},
    {"id": "normalisation", "name": "Normalisation", "strength": "High",
     "description": "Gradually shifting the boundaries of acceptable conduct or discourse so that positions that were previously considered extreme become unremarkable over time.",
     "detection": ["Language that describes extreme positions as merely 'controversial'", "Incremental steps that individually seem modest but collectively shift the frame", "Historical comparisons that treat the new norm as having always been acceptable"],
     "countermeasures": ["Maintain a fixed reference point outside the current discourse", "Track incremental shifts over time rather than evaluating each step in isolation", "Compare current norms against a baseline from before the shift began"]},
    {"id": "scapegoating", "name": "Scapegoating", "strength": "High",
     "description": "Attributing complex systemic failures to a single identifiable group, person, or cause. Simplifies multi-causal problems and redirects grievance toward a target.",
     "detection": ["Single-cause explanations for multi-causal events", "One group consistently identified as responsible across unrelated problems", "Evidence that challenges the attribution ignored or suppressed"],
     "countermeasures": ["Map the actual causal structure of the problem independently", "Ask who is excluded from scrutiny by the attribution", "Test the attribution against historical or comparative cases"]},
    {"id": "circular-reasoning", "name": "Circular Reasoning", "strength": "Low",
     "description": "Using the conclusion as a premise in its own argument. The argument appears to provide justification but in fact assumes what it needs to prove.",
     "detection": ["Arguments that return to their starting point without independent support", "Evidence described as self-evident when it requires justification", "Trust cited as a reason to accept claims where trust is what is in dispute"],
     "countermeasures": ["Identify the foundational claim and seek external evidence for it", "Map the argument structure to see whether it forms a circle", "Demand an argument that doesn't require the conclusion to be accepted first"]},
    {"id": "false-dichotomy", "name": "False Dichotomy", "strength": "Medium",
     "description": "Presenting a situation as having only two possible positions or outcomes when additional options exist. Forces a choice between extremes to exclude middle ground.",
     "detection": ["'You're either with us or against us' framing", "Binary choices presented in situations with multiple viable alternatives", "Third options dismissed as impractical without evidence"],
     "countermeasures": ["Generate additional options before evaluating", "Ask what is excluded by the binary framing", "Evaluate the options presented against independent criteria"]},
    {"id": "gish-gallop", "name": "Gish Gallop", "strength": "Medium",
     "description": "Overwhelming an opponent with a large number of weak, questionable, or irrelevant arguments. The volume makes systematic rebuttal impractical, and failure to address every point is presented as defeat.",
     "detection": ["Responses containing many more claims than can be addressed in proportion", "Arguments that vary widely in quality and relevance", "Any unaddressed point treated as conceded"],
     "countermeasures": ["Identify and address the strongest arguments, not all arguments", "Name the tactic explicitly and explain why not every point will be addressed", "Require proportionality: depth over volume"]},
    {"id": "strategic-ambiguity", "name": "Strategic Ambiguity", "strength": "High",
     "description": "Deliberate vagueness that allows multiple audiences to interpret a statement according to their own preferences, while maintaining plausible deniability about the intended meaning.",
     "detection": ["Statements that different audiences claim as support simultaneously", "Denials that the obvious reading was intended when challenged", "Language precise enough to imply meaning but vague enough to disclaim it"],
     "countermeasures": ["Ask for explicit commitment to a specific interpretation", "Document the statement and the context in which it was made", "Compare stated intent against the logical or natural reading"]},
]


@app.get("/tactics", response_class=HTMLResponse)
async def tactics_page(request: Request):
    return templates.TemplateResponse(request, "tactics.html", {"tactics": _TACTIC_DATA})


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
