"""CrewAI tool wrappers around the persistent ChromaDB memory store."""

import json

from crewai.tools import BaseTool

from memory.persistent_memory import (
    get_all_sources,
    get_source_map,
    retrieve_findings,
    store_finding,
    store_source_map,
)


class StoreMemoryTool(BaseTool):
    name: str = "store_memory"
    description: str = (
        "Persist a research finding to long-term memory for later retrieval. "
        "Input: JSON with 'content' (str), 'source_url' (str), 'agent' (str), "
        "'topic' (str), optional 'metadata' (dict)."
    )

    def _run(self, query: str) -> str:
        try:
            params = json.loads(query)
        except json.JSONDecodeError:
            return "Error: input must be valid JSON."

        return store_finding(
            content=params.get("content", ""),
            source_url=params.get("source_url", "unknown"),
            agent=params.get("agent", "unknown"),
            topic=params.get("topic", "general"),
            metadata=params.get("metadata"),
        )


class RetrieveMemoryTool(BaseTool):
    name: str = "retrieve_memory"
    description: str = (
        "Search long-term memory for relevant findings using semantic similarity. "
        "Input: JSON with 'query' (str), optional 'topic' (str), 'n_results' (int)."
    )

    def _run(self, query: str) -> str:
        try:
            params = json.loads(query) if query.strip().startswith("{") else {"query": query}
            q = params.get("query", query)
            topic = params.get("topic", "")
            n = int(params.get("n_results", 10))
        except (json.JSONDecodeError, ValueError):
            q, topic, n = query, "", 10

        findings = retrieve_findings(q, topic=topic, n_results=n)
        if not findings:
            return "No relevant findings in memory."

        lines = []
        for f in findings:
            lines.append(
                f"SOURCE: {f.get('source_url')}\n"
                f"AGENT: {f.get('agent')} | TOPIC: {f.get('topic')} | WHEN: {f.get('timestamp')}\n"
                f"CONTENT: {str(f.get('content', ''))[:800]}"
            )
        return "\n---\n".join(lines)


class ListSourcesTool(BaseTool):
    name: str = "list_known_sources"
    description: str = (
        "List all URLs already stored in memory for a given topic, to avoid re-visiting them. "
        "Input: JSON with optional 'topic' (str)."
    )

    def _run(self, query: str) -> str:
        try:
            params = json.loads(query) if query.strip().startswith("{") else {}
            topic = params.get("topic", "")
        except json.JSONDecodeError:
            topic = ""

        sources = get_all_sources(topic=topic)
        if not sources:
            return "No sources in memory yet."
        return "Known sources:\n" + "\n".join(f"- {s}" for s in sources)


class StoreSourceMapTool(BaseTool):
    name: str = "store_source_map"
    description: str = (
        "Save the discovered source map (list of URLs with metadata) for a research topic. "
        "Input: JSON with 'topic' (str) and 'sources' (list of dicts with url, type, priority)."
    )

    def _run(self, query: str) -> str:
        try:
            params = json.loads(query)
            store_source_map(params["topic"], params["sources"])
            return f"Stored source map with {len(params['sources'])} entries for topic '{params['topic']}'."
        except Exception as e:
            return f"Error storing source map: {e}"


class GetSourceMapTool(BaseTool):
    name: str = "get_source_map"
    description: str = (
        "Retrieve the previously stored source map for a research topic. "
        "Input: JSON with 'topic' (str)."
    )

    def _run(self, query: str) -> str:
        try:
            params = json.loads(query) if query.strip().startswith("{") else {}
            topic = params.get("topic", query)
        except json.JSONDecodeError:
            topic = query

        sources = get_source_map(topic)
        if not sources:
            return f"No source map stored for topic: {topic}"
        return json.dumps(sources, indent=2)
