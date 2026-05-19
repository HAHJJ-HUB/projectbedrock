"""
Ghost — silent content extractor.

Works through the source map produced by Infiltrator, fetching and extracting
full content from every source. Handles HTML, PDFs, feeds, archives, and cached
copies. Stores everything to persistent memory.
"""

from crewai import Agent, LLM

from config import CLAUDE_MODEL
from tools.archive_tools import (
    ArchiveOrgSearchTool,
    CachedPageTool,
    WaybackFetchTool,
    WaybackSearchTool,
)
from tools.memory_tools import (
    GetSourceMapTool,
    ListSourcesTool,
    RetrieveMemoryTool,
    StoreMemoryTool,
)
from tools.scraping_tools import (
    DeepCrawlTool,
    MetadataExtractorTool,
    PageExtractorTool,
    RSSFeedTool,
)
from tools.search_tools import DorkSearchTool, WebSearchTool


def create_ghost(llm: LLM) -> Agent:
    return Agent(
        role="Deep Content Extractor",
        goal=(
            "Silently and thoroughly extract the full content of every source in the source map. "
            "For each source: fetch the live page, fall back to cached or archived versions if "
            "the live page is unavailable, extract all text, metadata, and outbound links, "
            "identify any embedded documents or feeds, and store every meaningful finding "
            "to persistent memory with proper attribution. "
            "Miss nothing. If a page is down, find its archived version."
        ),
        backstory=(
            "You are a master content extractor who leaves no page unread. "
            "You know how to get text out of anything: HTML, PDFs, RSS feeds, "
            "paywalled pages with publicly cached copies, deleted pages via Wayback Machine. "
            "You work methodically through source lists, tracking what you've visited, "
            "extracting not just the visible text but also metadata, author information, "
            "publication dates, and embedded links. You store findings with full provenance "
            "so nothing is lost. You never fabricate — if you can't reach a source, "
            "you say so and try the next one."
        ),
        tools=[
            # Extraction
            PageExtractorTool(),
            DeepCrawlTool(),
            MetadataExtractorTool(),
            RSSFeedTool(),
            # Archive fallbacks
            WaybackFetchTool(),
            WaybackSearchTool(),
            CachedPageTool(),
            ArchiveOrgSearchTool(),
            # Additional discovery during extraction
            WebSearchTool(),
            DorkSearchTool(),
            # Memory
            StoreMemoryTool(),
            RetrieveMemoryTool(),
            ListSourcesTool(),
            GetSourceMapTool(),
        ],
        llm=llm,
        verbose=True,
        memory=True,
        max_iter=30,
        respect_context_window=True,
    )
