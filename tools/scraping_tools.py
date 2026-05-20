"""Content extraction tools: full page text, PDF, metadata, recursive link following."""

import json
import re
from urllib.parse import urljoin, urlparse

import pdfplumber
import requests
import trafilatura
from bs4 import BeautifulSoup
from crewai.tools import BaseTool
from markdownify import markdownify
from tenacity import retry, stop_after_attempt, wait_fixed

from config import CRAWL_DEPTH, REQUEST_HEADERS, REQUEST_TIMEOUT


def _fetch_raw(url: str) -> tuple[bytes, str]:
    resp = requests.get(
        url,
        headers=REQUEST_HEADERS,
        timeout=REQUEST_TIMEOUT,
        allow_redirects=True,
    )
    resp.raise_for_status()
    content_type = resp.headers.get("content-type", "")
    return resp.content, content_type


def _extract_text(url: str, raw: bytes, content_type: str) -> str:
    if "pdf" in content_type or url.lower().endswith(".pdf"):
        return _extract_pdf(raw)

    html = raw.decode("utf-8", errors="replace")

    # Try trafilatura first — it's excellent at main-content extraction
    text = trafilatura.extract(
        html,
        include_links=True,
        include_tables=True,
        include_comments=False,
        output_format="markdown",
    )
    if text and len(text.strip()) > 200:
        return text[:12000]

    # Fallback: BeautifulSoup with markdownify
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "nav", "footer", "aside", "iframe"]):
        tag.decompose()
    main = soup.find("main") or soup.find("article") or soup.find("body") or soup
    md = markdownify(str(main), heading_style="ATX")
    return md[:12000]


def _extract_pdf(raw: bytes) -> str:
    import io
    text_parts = []
    try:
        with pdfplumber.open(io.BytesIO(raw)) as pdf:
            for page in pdf.pages[:30]:
                t = page.extract_text()
                if t:
                    text_parts.append(t)
    except Exception as e:
        return f"PDF extraction error: {e}"
    return "\n\n".join(text_parts)[:12000]


class PageExtractorTool(BaseTool):
    name: str = "extract_page"
    description: str = (
        "Fetch a URL and extract its full readable text content. Handles HTML and PDFs. "
        "Also returns page title, description meta tag, and all outbound links. "
        "Input: the URL to fetch."
    )

    def _run(self, url: str) -> str:
        url = url.strip().strip('"').strip("'")
        try:
            raw, content_type = _fetch_raw(url)
        except Exception as e:
            return f"Fetch error for {url}: {e}"

        text = _extract_text(url, raw, content_type)

        if "pdf" not in content_type and not url.lower().endswith(".pdf"):
            html = raw.decode("utf-8", errors="replace")
            soup = BeautifulSoup(html, "lxml")
            title = soup.title.string.strip() if soup.title else "N/A"
            desc_tag = soup.find("meta", attrs={"name": "description"})
            desc = desc_tag["content"].strip() if desc_tag and desc_tag.get("content") else "N/A"
            links = list({
                urljoin(url, a["href"])
                for a in soup.find_all("a", href=True)
                if not a["href"].startswith(("javascript:", "mailto:", "#"))
            })[:30]
            link_block = "\n".join(links)
        else:
            title, desc, link_block = "PDF Document", "N/A", ""

        return (
            f"URL: {url}\n"
            f"TITLE: {title}\n"
            f"DESCRIPTION: {desc}\n\n"
            f"--- CONTENT ---\n{text}\n\n"
            f"--- OUTBOUND LINKS ---\n{link_block}"
        )


class DeepCrawlTool(BaseTool):
    name: str = "deep_crawl"
    description: str = (
        "Recursively crawl a starting URL up to the configured depth, extracting content "
        "from each discovered page on the same domain. Best for wikis, forums, document dumps. "
        "Input: JSON with 'url' (str) and optional 'depth' (int 1-3, default 1)."
    )

    def _run(self, query: str) -> str:
        try:
            params = json.loads(query) if query.strip().startswith("{") else {"url": query}
            start_url = params.get("url", query).strip()
            depth = min(int(params.get("depth", 1)), CRAWL_DEPTH)
        except (json.JSONDecodeError, ValueError):
            start_url, depth = query.strip(), 1

        base_domain = urlparse(start_url).netloc
        visited: set[str] = set()
        queue = [(start_url, 0)]
        all_content = []

        while queue and len(visited) < 20:
            url, d = queue.pop(0)
            if url in visited or d > depth:
                continue
            visited.add(url)

            try:
                raw, content_type = _fetch_raw(url)
                text = _extract_text(url, raw, content_type)
                all_content.append(f"=== {url} ===\n{text[:3000]}")

                if d < depth and "pdf" not in content_type:
                    html = raw.decode("utf-8", errors="replace")
                    soup = BeautifulSoup(html, "lxml")
                    for a in soup.find_all("a", href=True):
                        child = urljoin(url, a["href"])
                        if urlparse(child).netloc == base_domain and child not in visited:
                            queue.append((child, d + 1))
            except Exception as e:
                all_content.append(f"=== {url} ===\nERROR: {e}")

        return "\n\n".join(all_content)


class MetadataExtractorTool(BaseTool):
    name: str = "extract_metadata"
    description: str = (
        "Extract metadata from a URL: Open Graph tags, schema.org JSON-LD, "
        "author, publish date, keywords, canonical URL, HTTP headers. "
        "Input: the URL."
    )

    def _run(self, url: str) -> str:
        url = url.strip().strip('"').strip("'")
        try:
            resp = requests.get(
                url, headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT, allow_redirects=True
            )
            resp.raise_for_status()
        except Exception as e:
            return f"Fetch error: {e}"

        headers_info = {
            k: v for k, v in resp.headers.items()
            if k.lower() in (
                "content-type", "last-modified", "server", "x-powered-by",
                "content-language", "x-frame-options"
            )
        }
        soup = BeautifulSoup(resp.text, "lxml")

        og = {
            tag["property"]: tag.get("content", "")
            for tag in soup.find_all("meta", property=re.compile(r"^og:"))
        }
        json_ld_tags = soup.find_all("script", type="application/ld+json")
        json_ld = []
        for tag in json_ld_tags:
            try:
                json_ld.append(json.loads(tag.string))
            except Exception:
                pass

        author_tag = soup.find("meta", attrs={"name": "author"})
        date_tag = soup.find("meta", attrs={"name": re.compile(r"date|published", re.I)})
        keywords_tag = soup.find("meta", attrs={"name": "keywords"})
        canonical = soup.find("link", rel="canonical")

        return json.dumps({
            "url": url,
            "http_headers": headers_info,
            "open_graph": og,
            "json_ld": json_ld,
            "author": author_tag["content"] if author_tag else None,
            "date": date_tag["content"] if date_tag else None,
            "keywords": keywords_tag["content"] if keywords_tag else None,
            "canonical": canonical["href"] if canonical else None,
        }, indent=2)


class RSSFeedTool(BaseTool):
    name: str = "fetch_rss_feed"
    description: str = (
        "Fetch and parse an RSS or Atom feed URL, returning recent entries with "
        "titles, links, dates, and summaries. Input: the feed URL."
    )

    def _run(self, url: str) -> str:
        import feedparser
        url = url.strip().strip('"').strip("'")
        feed = feedparser.parse(url)
        if not feed.entries:
            return f"No entries found in feed at {url}."
        results = []
        for entry in feed.entries[:20]:
            results.append(
                f"TITLE: {entry.get('title', 'N/A')}\n"
                f"LINK: {entry.get('link', 'N/A')}\n"
                f"DATE: {entry.get('published', entry.get('updated', 'N/A'))}\n"
                f"SUMMARY: {entry.get('summary', '')[:500]}\n"
            )
        return "\n---\n".join(results)
