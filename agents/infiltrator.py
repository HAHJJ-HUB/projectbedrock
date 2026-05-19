"""
Infiltrator — source discovery specialist.

Maps every reachable public information source about the target topic:
mainstream, academic, governmental, archived, obscure forums, paste sites,
code repositories, and deep-indexed corners of the public web.
"""

from crewai import Agent, LLM

from config import CLAUDE_MODEL
from tools.archive_tools import ArchiveOrgSearchTool, WaybackSearchTool
from tools.memory_tools import (
    ListSourcesTool,
    RetrieveMemoryTool,
    StoreMemoryTool,
    StoreSourceMapTool,
)
from tools.search_tools import (
    DorkSearchTool,
    NewsSearchTool,
    PasteSiteSearchTool,
    WebSearchTool,
    CommonCrawlSearchTool,
)
from tools.specialized_tools import (
    ArXivSearchTool,
    GitHubSearchTool,
    GovernmentDocsSearchTool,
    RedditSearchTool,
    SemanticScholarTool,
    WHOISLookupTool,
)


def create_infiltrator(llm: LLM) -> Agent:
    return Agent(
        role="Intelligence Source Mapper",
        goal=(
            "Discover every publicly reachable source of information about the research topic. "
            "Cast the widest possible net: mainstream media, academic papers, government documents, "
            "public code repositories, paste sites, archived pages, obscure forums, RSS feeds, "
            "and any other publicly indexed or archived source. "
            "Produce a comprehensive, prioritized source map for Ghost to harvest."
        ),
        backstory=(
            "You are an expert in open-source intelligence (OSINT) and deep web research. "
            "You know that the most valuable information often hides in forgotten archive snapshots, "
            "niche academic papers, government FOIA releases, public GitHub repositories, "
            "old forum threads, and paste sites. You use advanced search operators, "
            "multi-engine strategies, and specialized APIs to surface sources that a "
            "standard web search would never find. You never guess — you verify that each "
            "source URL is real and publicly accessible before adding it to your map. "
            "You check memory first to avoid duplicating work."
        ),
        tools=[
            # General search
            WebSearchTool(),
            DorkSearchTool(),
            NewsSearchTool(),
            PasteSiteSearchTool(),
            CommonCrawlSearchTool(),
            # Archive
            WaybackSearchTool(),
            ArchiveOrgSearchTool(),
            # Specialized sources
            ArXivSearchTool(),
            GitHubSearchTool(),
            RedditSearchTool(),
            GovernmentDocsSearchTool(),
            SemanticScholarTool(),
            WHOISLookupTool(),
            # Memory
            StoreMemoryTool(),
            RetrieveMemoryTool(),
            ListSourcesTool(),
            StoreSourceMapTool(),
        ],
        llm=llm,
        verbose=True,
        memory=True,
        max_iter=25,
        respect_context_window=True,
    )
