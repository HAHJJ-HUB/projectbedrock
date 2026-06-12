"""Crew assembly and task definitions for the four-agent intelligence system."""

from crewai import Crew, LLM, Process, Task

from agents.ghost import create_ghost
from agents.infiltrator import create_infiltrator
from agents.nexus import create_nexus
from agents.oracle import create_oracle
from config import ANTHROPIC_API_KEY, CLAUDE_MODEL


def build_llm() -> LLM:
    return LLM(
        model=f"anthropic/{CLAUDE_MODEL}",
        api_key=ANTHROPIC_API_KEY,
        temperature=0.1,
        max_tokens=8192,
    )


def build_crew(
    topic: str,
    scope: str = "",
    case_id: int = 0,
    step_callback=None,
    task_callback=None,
) -> Crew:
    llm = build_llm()

    infiltrator = create_infiltrator(llm)
    ghost = create_ghost(llm)
    nexus = create_nexus(llm)
    oracle = create_oracle(llm)

    scope_clause = f"\n\nResearch scope / constraints: {scope}" if scope else ""

    from pathlib import Path
    output_dir = Path(f"output/case_{case_id}") if case_id else Path("output")
    output_dir.mkdir(parents=True, exist_ok=True)

    # ── Task 1: Source Discovery ────────────────────────────────────────────
    task_discover = Task(
        description=(
            f"Map every publicly reachable source of information about: **{topic}**\n\n"
            f"Your deliverable is a comprehensive source map, not the content itself.\n\n"
            f"REQUIRED actions:\n"
            f"1. Check memory for any prior research on this topic.\n"
            f"2. Run broad web searches (DuckDuckGo, news) to find mainstream coverage.\n"
            f"3. Use search dorks (site:, filetype:, inurl:, intitle:) to surface obscure pages.\n"
            f"4. Search paste sites for any publicly posted content about the topic.\n"
            f"5. Search GitHub for relevant public repositories and code.\n"
            f"6. Search ArXiv and Semantic Scholar for academic literature.\n"
            f"7. Search government document portals (data.gov, GovInfo, Federal Register).\n"
            f"8. Check Common Crawl index for URLs that may not appear in search engines.\n"
            f"9. Search Archive.org for relevant archived materials.\n"
            f"10. Search Reddit for community discussions.\n"
            f"11. Generate targeted dork queries to find: PDFs, forums, old discussions.\n\n"
            f"For each source found, record: URL, source type, estimated relevance (1-5), "
            f"whether it's live or archived, and a one-line description.\n\n"
            f"Store the complete source map to memory using store_source_map.\n"
            f"Return the source map as structured text — minimum 30 sources.{scope_clause}"
        ),
        expected_output=(
            "A structured source map with 30+ entries. Each entry: "
            "URL | Type | Relevance (1-5) | Status (live/archived) | Description. "
            "Grouped by source type (academic, government, social, paste, archive, etc.)."
        ),
        agent=infiltrator,
    )

    # ── Task 2: Content Extraction ──────────────────────────────────────────
    task_extract = Task(
        description=(
            f"Extract the full content of every source in the source map for: **{topic}**\n\n"
            f"REQUIRED actions:\n"
            f"1. Load the source map from memory (get_source_map).\n"
            f"2. For each source URL in the map:\n"
            f"   a. Attempt to fetch the live page using extract_page.\n"
            f"   b. If the live page fails, try wayback_fetch for an archived version.\n"
            f"   c. If Wayback fails, try fetch_cached_page.\n"
            f"   d. For pages that link to many sub-documents, use deep_crawl (depth=1).\n"
            f"   e. For RSS/Atom feeds, use fetch_rss_feed.\n"
            f"3. For each successfully extracted page:\n"
            f"   a. Store meaningful content to memory with store_memory "
            f"(include source_url, agent='Ghost', topic='{topic}').\n"
            f"   b. Follow any embedded links to primary documents if directly relevant.\n"
            f"4. Note which sources were inaccessible and why.\n\n"
            f"Prioritize depth over speed — extract the actual text, not just snippets.\n"
            f"Store EVERYTHING relevant to memory.{scope_clause}"
        ),
        expected_output=(
            "Extraction report: total sources attempted, successfully extracted, failed. "
            "For each source: URL, extraction status, content length (chars), key facts found. "
            "All content stored to persistent memory."
        ),
        agent=ghost,
        context=[task_discover],
    )

    # ── Task 3: Analysis and Synthesis ─────────────────────────────────────
    task_analyze = Task(
        description=(
            f"Analyze everything extracted about: **{topic}**\n\n"
            f"REQUIRED analysis sections:\n\n"
            f"1. **KEY ENTITIES**: Identify all named persons, organizations, locations, "
            f"technologies, events, dates, and quantities. For each entity: what it is, "
            f"why it matters, which sources mention it.\n\n"
            f"2. **RELATIONSHIPS**: Map relationships between entities. "
            f"Who works with whom? What caused what? What predates what?\n\n"
            f"3. **TIMELINE**: Reconstruct a chronological sequence of events "
            f"with source citations for each date.\n\n"
            f"4. **CORROBORATION**: Which claims appear in multiple independent sources? "
            f"These are your highest-confidence facts.\n\n"
            f"5. **CONTRADICTIONS**: Where do sources disagree? What might explain the conflict?\n\n"
            f"6. **PATTERNS**: What non-obvious patterns, trends, or connections emerge "
            f"when you look across all sources together?\n\n"
            f"7. **GAPS**: What important questions remain unanswered? "
            f"What would you search for next?\n\n"
            f"Use retrieve_memory extensively to pull relevant facts. "
            f"Cite every claim with its source URL. "
            f"If you spot gaps, run targeted searches to fill them before finalizing.{scope_clause}"
        ),
        expected_output=(
            "Structured analysis document with all 7 sections fully populated. "
            "Every factual claim cited with source URL. "
            "Confidence labels: CONFIRMED (2+ independent sources) | REPORTED (1 source) | INFERRED."
        ),
        agent=nexus,
        context=[task_discover, task_extract],
    )

    # ── Task 4: Bind the File ───────────────────────────────────────────────
    task_report = Task(
        description=(
            f"Bind the case file on: **{topic}**\n\n"
            f"Pull everything from memory first. Multiple retrieve_memory calls — "
            f"different query angles for the same topic. Nothing missed.\n\n"
            f"Then write the case file. It is the deliverable the user opens. "
            f"Complete, cited, in Oracle's voice.\n\n"
            f"THE FINDING\n"
            f"Three paragraphs.\n"
            f"  Paragraph 1: the central claim the record supports.\n"
            f"  Paragraph 2: the specific evidence, with citations.\n"
            f"  Paragraph 3: what the unit notes about scope, coincidence, or "
            f"remaining uncertainty.\n\n"
            f"THE MARGIN NOTE\n"
            f"One to three sentences. Three-beat shape: what the anomaly is, "
            f"why it matters, what the reader should do with it.\n\n"
            f"SECTION I — THE RECORD\n"
            f"The record, reconstructed. Entities, parents, subsidiaries, "
            f"dissolutions. Every entry cited.\n\n"
            f"SECTION II — THE TIMELINE\n"
            f"Chronological events. One event per entry. Each entry carries "
            f"its citation.\n\n"
            f"SECTION III — CONTRADICTIONS ON RECORD\n"
            f"Material entries ranked by weight against the subject. For each: "
            f"what Source A says, what Source B says, what would have to be "
            f"true for both to be correct, which one the other evidence supports. "
            f"Non-material entries listed but not elevated.\n\n"
            f"SECTION IV — NARRATIVE DRIFT\n"
            f"Where the language shifted. Where entities disappeared from later "
            f"coverage. Where speculation hardened into stated fact. Where "
            f"certainty inflated without new evidence.\n\n"
            f"SECTION V — THE SOURCE INVENTORY\n"
            f"Every URL. For each: type, confidence tier "
            f"(CONFIRMED / REPORTED / INFERRED), what it contributed to the file.\n\n"
            f"SECTION VI — EXHIBITS\n"
            f"The recovered material Ghost brought back. For each exhibit: "
            f"provenance, chain of custody, what it shows.\n\n"
            f"ATTRIBUTION LINES\n"
            f"One line per filer — what each did on this case, third person, "
            f"past tense. Oracle first, then Nexus, Ghost, Infiltrator.\n\n"
            f"CONFIDENCE\n"
            f"Overall level: High, Medium, or Low. One paragraph of explicit "
            f"reasoning. State what would change it.\n\n"
            f"Voice rules:\n"
            f"  Active voice. Past tense for completed work. Present tense for "
            f"the record's state.\n"
            f"  No hedging language. Use instead: 'appears to,' 'on the record,' "
            f"'to the unit's knowledge.'\n"
            f"  Three confidence tiers, never collapsed: CONFIRMED, REPORTED, "
            f"INFERRED.\n"
            f"  Every factual claim cites its source URL. An uncited claim is "
            f"an opinion.\n\n"
            f"Oracle signs the case file with a timestamp.{scope_clause}"
        ),
        expected_output=(
            "A complete case file in Markdown. Sections in this order:\n"
            "  THE FINDING (three paragraphs, every claim cited)\n"
            "  THE MARGIN NOTE (one to three sentences)\n"
            "  SECTION I — THE RECORD\n"
            "  SECTION II — THE TIMELINE\n"
            "  SECTION III — CONTRADICTIONS ON RECORD\n"
            "  SECTION IV — NARRATIVE DRIFT\n"
            "  SECTION V — THE SOURCE INVENTORY\n"
            "  SECTION VI — EXHIBITS\n"
            "  ATTRIBUTION LINES (one per filer, third person past tense)\n"
            "  CONFIDENCE (High / Medium / Low, explicit reasoning)\n"
            "  ORACLE'S SIGNATURE (timestamp)\n\n"
            "Confidence tiers applied throughout. No uncited factual claims."
        ),
        agent=oracle,
        context=[task_discover, task_extract, task_analyze],
        output_file=str(output_dir / "report.md"),
    )

    crew_kwargs = dict(
        agents=[infiltrator, ghost, nexus, oracle],
        tasks=[task_discover, task_extract, task_analyze, task_report],
        process=Process.sequential,
        verbose=True,
        output_log_file=str(output_dir / "crew_log.txt"),
    )
    if step_callback is not None:
        crew_kwargs["step_callback"] = step_callback
    if task_callback is not None:
        crew_kwargs["task_callback"] = task_callback
    return Crew(**crew_kwargs)
