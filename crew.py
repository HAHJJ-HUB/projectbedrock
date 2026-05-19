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


def build_crew(topic: str, scope: str = "") -> Crew:
    llm = build_llm()

    infiltrator = create_infiltrator(llm)
    ghost = create_ghost(llm)
    nexus = create_nexus(llm)
    oracle = create_oracle(llm)

    scope_clause = f"\n\nResearch scope / constraints: {scope}" if scope else ""

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

    # ── Task 4: Final Report ────────────────────────────────────────────────
    task_report = Task(
        description=(
            f"Write the comprehensive intelligence report on: **{topic}**\n\n"
            f"The report must be thorough, well-organized, and immediately useful to "
            f"a reader who wants to deeply understand the topic.\n\n"
            f"REQUIRED REPORT STRUCTURE:\n\n"
            f"# Intelligence Report: {{topic}}\n"
            f"*Generated: {{date}} | Sources: {{N}} | Confidence: {{level}}*\n\n"
            f"## Executive Summary\n"
            f"What we know, the most significant findings, overall confidence. 3-5 paragraphs.\n\n"
            f"## Detailed Findings\n"
            f"Organized thematically. Each finding cited with source URL. "
            f"Minimum 10 substantive findings. Distinguish facts from inferences.\n\n"
            f"## Entity Map\n"
            f"All key entities with descriptions and source citations.\n\n"
            f"## Timeline\n"
            f"Chronological events with dates and citations.\n\n"
            f"## Source Inventory\n"
            f"Every source consulted: URL | Type | Reliability | Key content contributed.\n\n"
            f"## Gaps & Next Steps\n"
            f"What remains unknown and the best leads for further investigation.\n\n"
            f"## Confidence Assessment\n"
            f"What is CONFIRMED vs REPORTED vs INFERRED, with reasoning.\n\n"
            f"Pull everything from memory. Use retrieve_memory with multiple queries "
            f"to ensure you have all findings. Write for depth, not brevity.{scope_clause}"
        ),
        expected_output=(
            "A complete intelligence report in Markdown format, minimum 2000 words. "
            "All sections present and fully populated. Every factual claim cited. "
            "Source inventory complete. Gaps identified. Confidence levels assigned."
        ),
        agent=oracle,
        context=[task_discover, task_extract, task_analyze],
        output_file="output/report.md",
    )

    return Crew(
        agents=[infiltrator, ghost, nexus, oracle],
        tasks=[task_discover, task_extract, task_analyze, task_report],
        process=Process.sequential,
        verbose=True,
        memory=True,
        embedder={
            "provider": "anthropic",
            "config": {
                "model": "voyage-3",
                "api_key": ANTHROPIC_API_KEY,
            },
        },
        output_log_file="output/crew_log.txt",
    )
