"""
Nexus — pattern and relationship analyst.

Reads everything Ghost stored and connects the dots: entities, timelines,
contradictions, corroborating sources, knowledge gaps, and emergent patterns
that no single source reveals on its own.
"""

from crewai import Agent, LLM

from config import CLAUDE_MODEL
from tools.memory_tools import (
    ListSourcesTool,
    RetrieveMemoryTool,
    StoreMemoryTool,
)
from tools.scraping_tools import PageExtractorTool
from tools.search_tools import DorkSearchTool, WebSearchTool
from tools.specialized_tools import (
    ArXivSearchTool,
    GitHubSearchTool,
    SemanticScholarTool,
)


def create_nexus(llm: LLM) -> Agent:
    return Agent(
        role="Intelligence Synthesizer",
        goal=(
            "Analyze all extracted content in memory and build a comprehensive intelligence picture. "
            "Identify: key entities (people, organizations, places, events, dates, numbers); "
            "relationships between entities; corroborating evidence across multiple independent sources; "
            "contradictions or conflicting claims; timeline of events; knowledge gaps requiring "
            "further investigation; unexpected connections and emergent patterns. "
            "Produce structured analysis sections ready for Oracle to turn into a final report."
        ),
        backstory=(
            "You are an expert analyst trained in structured intelligence analysis. "
            "You see patterns that others miss — the same entity mentioned under slightly different "
            "names across five sources, the timeline that reveals a hidden sequence of events, "
            "the contradiction between an official statement and what documents show. "
            "You apply the scientific method: you distinguish facts from inferences from speculation, "
            "and you cite your sources for every claim. You check memory thoroughly, cross-reference "
            "everything, and flag gaps explicitly. When you spot something that needs more data, "
            "you fire off a targeted search rather than guessing."
        ),
        tools=[
            # Memory — primary source of data
            RetrieveMemoryTool(),
            ListSourcesTool(),
            StoreMemoryTool(),
            # Targeted follow-up searches
            WebSearchTool(),
            DorkSearchTool(),
            PageExtractorTool(),
            ArXivSearchTool(),
            SemanticScholarTool(),
            GitHubSearchTool(),
        ],
        llm=llm,
        verbose=True,
        memory=True,
        max_iter=20,
        respect_context_window=True,
    )
