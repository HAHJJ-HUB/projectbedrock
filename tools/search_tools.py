"""Web search tools: DuckDuckGo multi-mode, dork generation, Bing, Common Crawl index."""

import json
import time
from typing import Optional
from urllib.parse import quote_plus

import requests
from crewai.tools import BaseTool
from duckduckgo_search import DDGS
from pydantic import Field
from tenacity import retry, stop_after_attempt, wait_exponential

from config import REQUEST_HEADERS, REQUEST_TIMEOUT, PASTE_SITES


class WebSearchTool(BaseTool):
    name: str = "web_search"
    description: str = (
        "Search the web using DuckDuckGo. Returns titles, URLs, and snippets. "
        "Input: JSON with keys 'query' (str) and optional 'max_results' (int, default 15)."
    )

    def _run(self, query: str) -> str:
        try:
            params = json.loads(query) if query.strip().startswith("{") else {"query": query}
            q = params.get("query", query)
            n = min(int(params.get("max_results", 15)), 40)
        except (json.JSONDecodeError, ValueError):
            q, n = query, 15

        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(q, max_results=n):
                results.append(
                    f"TITLE: {r.get('title', '')}\n"
                    f"URL: {r.get('href', '')}\n"
                    f"SNIPPET: {r.get('body', '')}\n"
                )
        return "\n---\n".join(results) if results else "No results found."


class DorkSearchTool(BaseTool):
    name: str = "dork_search"
    description: str = (
        "Run Google-style search dorks via DuckDuckGo to find hard-to-reach public content. "
        "Supports operators: site:, filetype:, inurl:, intitle:, intext:, -site:. "
        "Input: JSON with 'dork' (str) and optional 'max_results' (int). "
        "Example: {'dork': 'site:pastebin.com \"api keys\" filetype:txt', 'max_results': 20}"
    )

    def _run(self, query: str) -> str:
        try:
            params = json.loads(query) if query.strip().startswith("{") else {"dork": query}
            dork = params.get("dork", query)
            n = min(int(params.get("max_results", 15)), 40)
        except (json.JSONDecodeError, ValueError):
            dork, n = query, 15

        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(dork, max_results=n):
                results.append(
                    f"TITLE: {r.get('title', '')}\n"
                    f"URL: {r.get('href', '')}\n"
                    f"SNIPPET: {r.get('body', '')}\n"
                )
        return "\n---\n".join(results) if results else "No results found for dork."


class PasteSiteSearchTool(BaseTool):
    name: str = "paste_site_search"
    description: str = (
        "Search public paste sites (Pastebin, Rentry, dpaste, etc.) for publicly posted content. "
        "These are sites where people paste text publicly. "
        "Input: JSON with 'query' (str) and optional 'site' (str, leave empty to search all)."
    )

    def _run(self, query: str) -> str:
        try:
            params = json.loads(query) if query.strip().startswith("{") else {"query": query}
            q = params.get("query", query)
            target_site = params.get("site", "")
        except (json.JSONDecodeError, ValueError):
            q, target_site = query, ""

        sites = [target_site] if target_site else PASTE_SITES
        all_results = []

        with DDGS() as ddgs:
            for site in sites:
                dork = f"site:{site} {q}"
                for r in ddgs.text(dork, max_results=8):
                    all_results.append(
                        f"SITE: {site}\n"
                        f"TITLE: {r.get('title', '')}\n"
                        f"URL: {r.get('href', '')}\n"
                        f"SNIPPET: {r.get('body', '')}\n"
                    )
                time.sleep(0.3)

        return "\n---\n".join(all_results) if all_results else "No paste site results found."


class CommonCrawlSearchTool(BaseTool):
    name: str = "commoncrawl_search"
    description: str = (
        "Search the Common Crawl index to find URLs that Common Crawl has archived. "
        "Common Crawl has indexed billions of web pages including obscure and forgotten ones. "
        "Input: JSON with 'url_pattern' (str, e.g. '*.example.com/*') and optional 'limit' (int)."
    )

    def _run(self, query: str) -> str:
        try:
            params = json.loads(query) if query.strip().startswith("{") else {"url_pattern": query}
            pattern = params.get("url_pattern", query)
            limit = min(int(params.get("limit", 20)), 100)
        except (json.JSONDecodeError, ValueError):
            pattern, limit = query, 20

        api_url = (
            f"https://index.commoncrawl.org/CC-MAIN-2024-10-index"
            f"?url={quote_plus(pattern)}&output=json&limit={limit}"
        )
        try:
            resp = requests.get(api_url, headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            lines = resp.text.strip().split("\n")
            results = []
            for line in lines[:limit]:
                try:
                    entry = json.loads(line)
                    results.append(
                        f"URL: {entry.get('url', '')}\n"
                        f"STATUS: {entry.get('status', '')}\n"
                        f"TIMESTAMP: {entry.get('timestamp', '')}\n"
                        f"MIME: {entry.get('mime', '')}\n"
                    )
                except json.JSONDecodeError:
                    continue
            return "\n---\n".join(results) if results else "No Common Crawl results."
        except Exception as e:
            return f"Common Crawl search error: {e}"


class NewsSearchTool(BaseTool):
    name: str = "news_search"
    description: str = (
        "Search news articles and press coverage. Useful for finding historical reporting, "
        "obscure publications, and investigative journalism. "
        "Input: JSON with 'query' (str), optional 'timelimit' ('d', 'w', 'm', 'y')."
    )

    def _run(self, query: str) -> str:
        try:
            params = json.loads(query) if query.strip().startswith("{") else {"query": query}
            q = params.get("query", query)
            timelimit = params.get("timelimit", "")
        except (json.JSONDecodeError, ValueError):
            q, timelimit = query, ""

        kwargs = {"keywords": q, "max_results": 20}
        if timelimit:
            kwargs["timelimit"] = timelimit

        results = []
        with DDGS() as ddgs:
            for r in ddgs.news(**kwargs):
                results.append(
                    f"TITLE: {r.get('title', '')}\n"
                    f"URL: {r.get('url', '')}\n"
                    f"SOURCE: {r.get('source', '')}\n"
                    f"DATE: {r.get('date', '')}\n"
                    f"SNIPPET: {r.get('body', '')}\n"
                )
        return "\n---\n".join(results) if results else "No news results found."


class ImageSearchTool(BaseTool):
    name: str = "image_search"
    description: str = (
        "Search for images by keyword. Returns image URLs and source pages. "
        "Useful for finding diagrams, documents photographed, infographics. "
        "Input: the search query string."
    )

    def _run(self, query: str) -> str:
        results = []
        with DDGS() as ddgs:
            for r in ddgs.images(query, max_results=10):
                results.append(
                    f"TITLE: {r.get('title', '')}\n"
                    f"IMAGE_URL: {r.get('image', '')}\n"
                    f"SOURCE_PAGE: {r.get('url', '')}\n"
                )
        return "\n---\n".join(results) if results else "No image results."
