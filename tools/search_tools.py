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
        "Run advanced search dorks via DuckDuckGo to surface hard-to-find public content. "
        "Construct dork strings using these operators and templates:\n\n"

        "DOCUMENT DISCOVERY:\n"
        "  filetype:pdf site:.gov \"topic\"          — government PDFs\n"
        "  filetype:pdf site:.edu \"topic\"          — academic PDFs\n"
        "  filetype:csv OR filetype:xlsx \"topic\"   — data files\n"
        "  filetype:sql \"topic\" \"CREATE TABLE\"     — public database dumps\n"
        "  filetype:xml OR filetype:json \"topic\" site:github.com\n"
        "  filetype:doc OR filetype:docx \"topic\" site:.gov\n"
        "  filetype:ppt OR filetype:pptx \"topic\" site:.edu\n\n"

        "OPEN DIRECTORY HUNTING:\n"
        "  intitle:\"index of\" \"topic\" (pdf OR doc OR txt OR csv)\n"
        "  intitle:\"index of\" /files/ \"topic\"\n"
        "  intitle:\"index of\" /data/ \"topic\"\n"
        "  intitle:\"index of\" /backup/ \"topic\"\n"
        "  intitle:\"index of\" /dump/ OR /export/ \"topic\"\n\n"

        "FORUM AND DISCUSSION ARCHAEOLOGY:\n"
        "  inurl:viewtopic \"topic\" -site:reddit.com\n"
        "  inurl:showthread \"topic\" -site:reddit.com\n"
        "  inurl:phpbb \"topic\"\n"
        "  inurl:forum \"topic\" -site:reddit.com -site:quora.com\n"
        "  site:groups.google.com \"topic\"\n"
        "  site:news.ycombinator.com \"topic\"\n\n"

        "PASTE AND DUMP SITES:\n"
        "  site:pastebin.com \"topic\"\n"
        "  site:gist.github.com \"topic\"\n"
        "  site:justpaste.it \"topic\"\n\n"

        "VINTAGE AND FORGOTTEN WEB:\n"
        "  site:angelfire.com OR site:geocities.com OR site:tripod.com \"topic\"\n"
        "  site:sourceforge.net \"topic\"\n"
        "  site:web.archive.org \"topic\" inurl:1999 OR inurl:2000 OR inurl:2001\n\n"

        "ACADEMIC AND RESEARCH:\n"
        "  site:researchgate.net \"topic\"\n"
        "  site:academia.edu \"topic\"\n"
        "  site:ssrn.com \"topic\"\n"
        "  site:zenodo.org \"topic\"\n\n"

        "GOVERNMENT AND FOIA:\n"
        "  site:.gov \"topic\" filetype:pdf\n"
        "  site:foia.gov \"topic\"\n"
        "  site:cia.gov/readingroom \"topic\"\n"
        "  site:archives.gov \"topic\"\n\n"

        "TEMPORAL OPERATORS:\n"
        "  \"topic\" before:2010                     — pre-2010 results only\n"
        "  \"topic\" after:2005 before:2008\n\n"

        "EXCLUSION PATTERNS:\n"
        "  \"topic\" -site:wikipedia.org -site:reddit.com -site:quora.com\n\n"

        "Input: JSON with 'dork' (str) and optional 'max_results' (int, default 20). "
        "Construct the most targeted dork possible for the information sought."
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
        "Search the deepest available public discussion archives: 4chan archives "
        "(4plebs, Desuarchive, archived.moe, Fireden), HackerNews full-text via Algolia, "
        "Stack Exchange network, public mailing list archives (LKML, Debian, Apache, MARC), "
        "Google Groups / Usenet going back to the 1990s, IRC log archives, "
        "and Wayback snapshots of defunct phpBB/vBulletin forums. "
        "Input: JSON with 'query' (str), optional 'board' (str), "
        "'source' (str: '4chan'|'hn'|'stackexchange'|'mailing_lists'|'irc'|'forums'|'all')."
    )

    _ARCHIVES: dict = {
        "4plebs": {
            "boards": ["adv", "f", "hr", "o", "pol", "s4s", "sp", "tg", "trv", "tv", "x"],
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
            source = params.get("source", "all")
        except (json.JSONDecodeError, ValueError):
            q, board, source = query, "", "all"

        all_results = []

        # ── 4chan archives ───────────────────────────────────────────────────
        if source in ("all", "4chan"):
            for archive_name, cfg in self._ARCHIVES.items():
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
                        for post in posts[:6]:
                            thread_num = post.get("thread_num", post.get("num", ""))
                            board_val = post.get("board", {})
                            board_name = (
                                board_val.get("shortname", board)
                                if isinstance(board_val, dict) else board
                            )
                            all_results.append(
                                f"ARCHIVE: {archive_name} | BOARD: /{board_name}/ "
                                f"| DATE: {post.get('timestamp', '')}\n"
                                f"SUBJECT: {post.get('title', '(no subject)')}\n"
                                f"EXCERPT: {str(post.get('comment', ''))[:400]}\n"
                                f"URL: https://{archive_name.replace('_', '.')}.org"
                                f"/{board_name}/thread/{thread_num}/"
                            )
                except Exception:
                    pass
                time.sleep(0.3)

        # ── HackerNews via Algolia API (free, no key, full corpus) ───────────
        if source in ("all", "hn"):
            for hn_endpoint in ["search", "search_by_date"]:
                try:
                    resp = requests.get(
                        f"https://hn.algolia.com/api/v1/{hn_endpoint}",
                        params={"query": q, "hitsPerPage": 15, "tags": "story,comment"},
                        headers=REQUEST_HEADERS,
                        timeout=REQUEST_TIMEOUT,
                    )
                    if resp.status_code == 200:
                        for hit in resp.json().get("hits", [])[:8]:
                            obj_id = hit.get("objectID", "")
                            story_id = hit.get("story_id") or hit.get("objectID", "")
                            all_results.append(
                                f"ARCHIVE: HackerNews ({hn_endpoint})\n"
                                f"TITLE: {hit.get('title') or hit.get('story_title', '(comment)')}\n"
                                f"AUTHOR: {hit.get('author', 'N/A')} | "
                                f"POINTS: {hit.get('points', 'N/A')} | "
                                f"DATE: {hit.get('created_at', 'N/A')}\n"
                                f"EXCERPT: {str(hit.get('comment_text') or hit.get('story_text', ''))[:300]}\n"
                                f"URL: https://news.ycombinator.com/item?id={story_id}"
                            )
                except Exception:
                    pass
                time.sleep(0.2)

        # ── Stack Exchange network (free API, no key needed for read) ────────
        if source in ("all", "stackexchange"):
            se_sites = ["stackoverflow", "superuser", "serverfault", "security",
                        "unix", "askubuntu", "physics", "chemistry", "biology"]
            for site in se_sites[:4]:
                try:
                    resp = requests.get(
                        "https://api.stackexchange.com/2.3/search/advanced",
                        params={
                            "q": q, "site": site, "pagesize": 8, "order": "desc",
                            "sort": "relevance", "filter": "withbody",
                        },
                        headers=REQUEST_HEADERS,
                        timeout=REQUEST_TIMEOUT,
                    )
                    if resp.status_code == 200:
                        for item in resp.json().get("items", [])[:5]:
                            all_results.append(
                                f"ARCHIVE: StackExchange/{site}\n"
                                f"TITLE: {item.get('title', 'N/A')}\n"
                                f"SCORE: {item.get('score')} | "
                                f"ANSWERS: {item.get('answer_count')} | "
                                f"DATE: {item.get('creation_date')}\n"
                                f"TAGS: {', '.join(item.get('tags', []))}\n"
                                f"URL: {item.get('link', 'N/A')}"
                            )
                except Exception:
                    pass
                time.sleep(0.3)

        # ── Public mailing list archives ─────────────────────────────────────
        if source in ("all", "mailing_lists"):
            # LKML (Linux Kernel Mailing List) — lkml.org has public search
            try:
                resp = requests.get(
                    f"https://lkml.org/lkml/find?q={quote_plus(q)}",
                    headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT,
                )
                if resp.status_code == 200:
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(resp.text, "lxml")
                    for a in soup.select("a[href*='/lkml/']")[:6]:
                        all_results.append(
                            f"ARCHIVE: LKML\n"
                            f"TITLE: {a.get_text(strip=True)}\n"
                            f"URL: https://lkml.org{a['href']}"
                        )
            except Exception:
                pass

            # mail-archive.com — public search across thousands of lists
            try:
                resp = requests.get(
                    f"https://www.mail-archive.com/search",
                    params={"l": "all", "q": q},
                    headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT,
                )
                if resp.status_code == 200:
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(resp.text, "lxml")
                    for item in soup.select(".subject a")[:8]:
                        all_results.append(
                            f"ARCHIVE: mail-archive.com\n"
                            f"TITLE: {item.get_text(strip=True)}\n"
                            f"URL: https://www.mail-archive.com{item.get('href', '')}"
                        )
            except Exception:
                pass

            # MARC (Mailing list ARChives) — huge public archive
            with DDGS() as ddgs:
                for r in ddgs.text(f"site:marc.info {q}", max_results=5):
                    all_results.append(
                        f"ARCHIVE: MARC\n"
                        f"TITLE: {r.get('title', '')}\n"
                        f"URL: {r.get('href', '')}\n"
                        f"SNIPPET: {r.get('body', '')[:200]}"
                    )

        # ── Public IRC log archives ───────────────────────────────────────────
        if source in ("all", "irc"):
            irc_dork = (
                f'"{q}" (site:irclogs.ubuntu.com OR site:echelog.com '
                f'OR site:irc.netsplit.de OR site:logs.ossasepia.com)'
            )
            with DDGS() as ddgs:
                for r in ddgs.text(irc_dork, max_results=8):
                    all_results.append(
                        f"ARCHIVE: IRC Logs\n"
                        f"TITLE: {r.get('title', '')}\n"
                        f"URL: {r.get('href', '')}\n"
                        f"SNIPPET: {r.get('body', '')[:300]}"
                    )

        # ── Google Groups / Usenet ────────────────────────────────────────────
        if source in ("all", "forums"):
            with DDGS() as ddgs:
                for r in ddgs.text(f"site:groups.google.com {q}", max_results=8):
                    all_results.append(
                        f"ARCHIVE: Google Groups / Usenet\n"
                        f"TITLE: {r.get('title', '')}\n"
                        f"URL: {r.get('href', '')}\n"
                        f"SNIPPET: {r.get('body', '')[:300]}"
                    )

            # Archived phpBB/vBulletin/SMF forums via Wayback
            forum_dork = (
                f'site:web.archive.org "{q}" '
                f'(inurl:viewtopic OR inurl:showthread OR inurl:phpbb OR inurl:smf)'
            )
            with DDGS() as ddgs:
                for r in ddgs.text(forum_dork, max_results=8):
                    all_results.append(
                        f"ARCHIVE: Wayback/Forum snapshot\n"
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
