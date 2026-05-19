"""Archive and historical web tools: Wayback Machine, Archive.org, cached pages."""

import json
import re
from datetime import datetime
from urllib.parse import quote_plus

import requests
from crewai.tools import BaseTool

from config import REQUEST_HEADERS, REQUEST_TIMEOUT


class WaybackSearchTool(BaseTool):
    name: str = "wayback_search"
    description: str = (
        "Search the Wayback Machine (archive.org) for archived snapshots of a URL. "
        "Returns available snapshots with timestamps. Great for finding deleted or changed pages. "
        "Input: JSON with 'url' (str) and optional 'from_year' (int), 'to_year' (int), 'limit' (int)."
    )

    def _run(self, query: str) -> str:
        try:
            params = json.loads(query) if query.strip().startswith("{") else {"url": query}
            url = params.get("url", query).strip()
            from_year = params.get("from_year", "")
            to_year = params.get("to_year", "")
            limit = min(int(params.get("limit", 20)), 100)
        except (json.JSONDecodeError, ValueError):
            url, from_year, to_year, limit = query.strip(), "", "", 20

        cdx_url = (
            f"https://web.archive.org/cdx/search/cdx"
            f"?url={quote_plus(url)}&output=json&limit={limit}&fl=timestamp,statuscode,mimetype,length"
        )
        if from_year:
            cdx_url += f"&from={from_year}0101000000"
        if to_year:
            cdx_url += f"&to={to_year}1231235959"

        try:
            resp = requests.get(cdx_url, headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            rows = resp.json()
        except Exception as e:
            return f"Wayback search error: {e}"

        if not rows or len(rows) <= 1:
            return f"No Wayback Machine snapshots found for: {url}"

        header = rows[0]
        results = []
        for row in rows[1:]:
            data = dict(zip(header, row))
            ts = data.get("timestamp", "")
            dt = (
                datetime.strptime(ts, "%Y%m%d%H%M%S").strftime("%Y-%m-%d %H:%M")
                if len(ts) == 14 else ts
            )
            snapshot_url = f"https://web.archive.org/web/{ts}/{url}"
            results.append(
                f"DATE: {dt} | STATUS: {data.get('statuscode')} | "
                f"TYPE: {data.get('mimetype')} | SIZE: {data.get('length')} bytes\n"
                f"SNAPSHOT: {snapshot_url}"
            )

        return f"Found {len(results)} snapshots for {url}:\n\n" + "\n---\n".join(results)


class WaybackFetchTool(BaseTool):
    name: str = "wayback_fetch"
    description: str = (
        "Fetch the content of a specific Wayback Machine snapshot, or the nearest snapshot "
        "to a given date. Input: JSON with 'url' (str) and optional 'date' (str, YYYYMMDD)."
    )

    def _run(self, query: str) -> str:
        from tools.scraping_tools import _extract_text, _fetch_raw
        try:
            params = json.loads(query) if query.strip().startswith("{") else {"url": query}
            url = params.get("url", query).strip()
            date = params.get("date", "")
        except (json.JSONDecodeError, ValueError):
            url, date = query.strip(), ""

        if "web.archive.org" in url:
            archive_url = url
        else:
            date_part = date if date else "20240101"
            archive_url = f"https://web.archive.org/web/{date_part}/{url}"

        try:
            raw, content_type = _fetch_raw(archive_url)
            text = _extract_text(archive_url, raw, content_type)
            return f"SOURCE: {archive_url}\n\n{text}"
        except Exception as e:
            return f"Wayback fetch error: {e}"


class ArchiveOrgSearchTool(BaseTool):
    name: str = "archive_org_search"
    description: str = (
        "Search Archive.org's collection of texts, books, PDFs, audio, video, and software. "
        "Returns items with metadata and download links. "
        "Input: JSON with 'query' (str), optional 'mediatype' "
        "('texts'|'audio'|'movies'|'software'|'image'), 'rows' (int)."
    )

    def _run(self, query: str) -> str:
        try:
            params = json.loads(query) if query.strip().startswith("{") else {"query": query}
            q = params.get("query", query)
            mediatype = params.get("mediatype", "texts")
            rows = min(int(params.get("rows", 15)), 50)
        except (json.JSONDecodeError, ValueError):
            q, mediatype, rows = query, "texts", 15

        search_url = "https://archive.org/advancedsearch.php"
        api_params = {
            "q": f"{q} AND mediatype:{mediatype}",
            "fl[]": ["identifier", "title", "creator", "date", "description", "downloads"],
            "rows": rows,
            "output": "json",
        }
        try:
            resp = requests.get(
                search_url, params=api_params, headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            return f"Archive.org search error: {e}"

        docs = data.get("response", {}).get("docs", [])
        if not docs:
            return "No Archive.org results found."

        results = []
        for doc in docs:
            identifier = doc.get("identifier", "")
            results.append(
                f"TITLE: {doc.get('title', 'N/A')}\n"
                f"CREATOR: {doc.get('creator', 'N/A')}\n"
                f"DATE: {doc.get('date', 'N/A')}\n"
                f"DOWNLOADS: {doc.get('downloads', 'N/A')}\n"
                f"DESCRIPTION: {str(doc.get('description', ''))[:300]}\n"
                f"URL: https://archive.org/details/{identifier}\n"
                f"DOWNLOAD: https://archive.org/download/{identifier}"
            )
        return "\n---\n".join(results)


class CachedPageTool(BaseTool):
    name: str = "fetch_cached_page"
    description: str = (
        "Attempt to retrieve a cached version of a page using multiple cache providers "
        "(Google Cache, Bing Cache, Wayback Machine). Useful when the original is unavailable. "
        "Input: the original URL."
    )

    def _run(self, url: str) -> str:
        from tools.scraping_tools import _extract_text, _fetch_raw
        url = url.strip().strip('"').strip("'")

        cache_urls = [
            f"https://webcache.googleusercontent.com/search?q=cache:{quote_plus(url)}",
            f"https://web.archive.org/web/{url}",
        ]

        for cache_url in cache_urls:
            try:
                raw, content_type = _fetch_raw(cache_url)
                text = _extract_text(cache_url, raw, content_type)
                if text and len(text.strip()) > 100:
                    return f"CACHED FROM: {cache_url}\n\n{text}"
            except Exception:
                continue

        return f"No cached version found for: {url}"
