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


class ForumArchiveSearchTool(BaseTool):
    name: str = "forum_archive_search"
    description: str = (
        "Search public archives of defunct and active forums, imageboards, and discussion boards. "
        "Covers 4chan archives (4plebs, Desuarchive, archived.moe, Fireden), Google Groups, "
        "and Wayback Machine snapshots of old forums (phpBB, vBulletin, etc.). "
        "Invaluable for finding technical discussions, historical debates, and content "
        "that has been deleted from the live web but preserved in archives. "
        "Input: JSON with 'query' (str), optional 'board' (str, e.g. 'g', 'sci', 'his'), "
        "'archive' (str: '4plebs'|'desuarchive'|'fireden'|'all')."
    )

    # Public 4chan archive endpoints (all are openly indexed, no auth required)
    _ARCHIVES: dict = {
        "4plebs": {
            "boards": ["adv", "f", "hr", "o", "pol", "s4s", "sp", "tg", "trv", "tv", "x"],
            "search_url": "https://archive.4plebs.org/{board}/search/text/{query}/",
            "api_url": "https://archive.4plebs.org/_/api/chan/search/?boards={board}&text={query}",
        },
        "desuarchive": {
            "boards": ["a", "aco", "an", "c", "cgl", "co", "d", "fit", "g", "gif", "his",
                       "int", "k", "m", "mlp", "mu", "q", "qa", "r9k", "sci", "tg", "trash", "wsg"],
            "api_url": "https://desuarchive.org/_/api/chan/search/?boards={board}&text={query}",
        },
        "fireden": {
            "boards": ["cm", "co", "ic", "sci", "vip", "x", "y"],
            "api_url": "https://boards.fireden.net/_/api/chan/search/?boards={board}&text={query}",
        },
        "archived_moe": {
            "boards": ["3", "biz", "diy", "fa", "g", "gd", "i", "ic", "jp", "lit",
                       "n", "news", "out", "p", "po", "qst", "r", "s", "sci", "vr", "wg"],
            "api_url": "https://archived.moe/_/api/chan/search/?boards={board}&text={query}",
        },
    }

    def _run(self, query: str) -> str:
        try:
            params = json.loads(query) if query.strip().startswith("{") else {"query": query}
            q = params.get("query", query)
            board = params.get("board", "")
            target_archive = params.get("archive", "all")
        except (json.JSONDecodeError, ValueError):
            q, board, target_archive = query, "", "all"

        all_results = []

        # ── 4chan-style API archives ─────────────────────────────────────────
        archives_to_search = (
            {target_archive: self._ARCHIVES[target_archive]}
            if target_archive in self._ARCHIVES
            else self._ARCHIVES
        )

        for archive_name, cfg in archives_to_search.items():
            board_param = board if board in cfg.get("boards", []) else ""
            api_url = cfg["api_url"].format(
                board=board_param or ",".join(cfg.get("boards", [""])),
                query=quote_plus(q),
            )
            try:
                resp = requests.get(api_url, headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT)
                if resp.status_code == 200:
                    data = resp.json()
                    posts = data.get("0", {}).get("posts", []) if isinstance(data, dict) else []
                    for post in posts[:8]:
                        thread_num = post.get("thread_num", post.get("num", ""))
                        board_val = post.get("board", {})
                        board_name = board_val.get("shortname", board) if isinstance(board_val, dict) else board
                        ts = post.get("timestamp", "")
                        all_results.append(
                            f"ARCHIVE: {archive_name} | BOARD: /{board_name}/ | DATE: {ts}\n"
                            f"SUBJECT: {post.get('title', '(no subject)')}\n"
                            f"EXCERPT: {str(post.get('comment', ''))[:400]}\n"
                            f"URL: https://{archive_name.replace('_', '.')}.org"
                            f"/{board_name}/thread/{thread_num}/"
                        )
            except Exception:
                pass
            time.sleep(0.3)

        # ── Google Groups (Usenet / mailing list archives) ───────────────────
        with DDGS() as ddgs:
            for r in ddgs.text(f"site:groups.google.com {q}", max_results=6):
                all_results.append(
                    f"ARCHIVE: Google Groups\n"
                    f"TITLE: {r.get('title', '')}\n"
                    f"URL: {r.get('href', '')}\n"
                    f"SNIPPET: {r.get('body', '')[:300]}"
                )

        # ── Wayback snapshots of old phpBB / vBulletin forums ───────────────
        forum_dork = f'site:web.archive.org "{q}" (inurl:viewtopic OR inurl:showthread OR inurl:phpbb)'
        with DDGS() as ddgs:
            for r in ddgs.text(forum_dork, max_results=6):
                all_results.append(
                    f"ARCHIVE: Wayback/Forum\n"
                    f"TITLE: {r.get('title', '')}\n"
                    f"URL: {r.get('href', '')}\n"
                    f"SNIPPET: {r.get('body', '')[:300]}"
                )

        return "\n---\n".join(all_results) if all_results else "No forum archive results found."


class PublicLeakJournalismTool(BaseTool):
    name: str = "public_leak_journalism_search"
    description: str = (
        "Search public-interest investigative leak repositories: WikiLeaks, "
        "Distributed Denial of Secrets (DDoSecrets), ICIJ Offshore Leaks Database, "
        "and similar outlets that publish leaked government/corporate documents "
        "in the public interest. NOT for personal data or credential dumps. "
        "Input: JSON with 'query' (str) and optional 'source' "
        "('wikileaks'|'ddosecrets'|'icij'|'all')."
    )

    def _run(self, query: str) -> str:
        try:
            params = json.loads(query) if query.strip().startswith("{") else {"query": query}
            q = params.get("query", query)
            source = params.get("source", "all")
        except (json.JSONDecodeError, ValueError):
            q, source = query, "all"

        all_results = []

        # ── WikiLeaks full-text search ───────────────────────────────────────
        if source in ("all", "wikileaks"):
            try:
                resp = requests.get(
                    f"https://search.wikileaks.org/advanced?q={quote_plus(q)}&include_external_sources=True",
                    headers=REQUEST_HEADERS,
                    timeout=REQUEST_TIMEOUT,
                )
                if resp.status_code == 200:
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(resp.text, "lxml")
                    for item in soup.select(".result")[:8]:
                        title_el = item.select_one("h4 a, h3 a")
                        snippet_el = item.select_one(".snippet, p")
                        if title_el:
                            all_results.append(
                                f"SOURCE: WikiLeaks\n"
                                f"TITLE: {title_el.get_text(strip=True)}\n"
                                f"URL: https://wikileaks.org{title_el.get('href', '')}\n"
                                f"SNIPPET: {snippet_el.get_text(strip=True)[:300] if snippet_el else ''}"
                            )
            except Exception:
                # Fallback: dork search
                with DDGS() as ddgs:
                    for r in ddgs.text(f"site:wikileaks.org {q}", max_results=8):
                        all_results.append(
                            f"SOURCE: WikiLeaks\n"
                            f"TITLE: {r.get('title', '')}\n"
                            f"URL: {r.get('href', '')}\n"
                            f"SNIPPET: {r.get('body', '')[:300]}"
                        )

        # ── DDoSecrets ───────────────────────────────────────────────────────
        if source in ("all", "ddosecrets"):
            with DDGS() as ddgs:
                for r in ddgs.text(f"site:ddosecrets.com {q}", max_results=8):
                    all_results.append(
                        f"SOURCE: DDoSecrets\n"
                        f"TITLE: {r.get('title', '')}\n"
                        f"URL: {r.get('href', '')}\n"
                        f"SNIPPET: {r.get('body', '')[:300]}"
                    )

        # ── ICIJ Offshore Leaks (Panama Papers, Paradise Papers, etc.) ───────
        if source in ("all", "icij"):
            try:
                resp = requests.get(
                    f"https://offshoreleaks.icij.org/search?q={quote_plus(q)}&c=&j=&e=0",
                    headers=REQUEST_HEADERS,
                    timeout=REQUEST_TIMEOUT,
                )
                if resp.status_code == 200:
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(resp.text, "lxml")
                    for row in soup.select("table tbody tr")[:10]:
                        cells = [td.get_text(strip=True) for td in row.select("td")]
                        link = row.select_one("a")
                        if cells:
                            all_results.append(
                                f"SOURCE: ICIJ Offshore Leaks\n"
                                f"ENTITY: {cells[0] if cells else 'N/A'}\n"
                                f"DETAILS: {' | '.join(cells[1:4])}\n"
                                f"URL: https://offshoreleaks.icij.org{link['href'] if link else ''}"
                            )
            except Exception:
                with DDGS() as ddgs:
                    for r in ddgs.text(f"site:offshoreleaks.icij.org {q}", max_results=6):
                        all_results.append(
                            f"SOURCE: ICIJ\n"
                            f"TITLE: {r.get('title', '')}\n"
                            f"URL: {r.get('href', '')}\n"
                            f"SNIPPET: {r.get('body', '')[:300]}"
                        )

        return "\n---\n".join(all_results) if all_results else "No public leak journalism results found."
