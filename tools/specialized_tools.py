"""Specialized source tools: ArXiv, GitHub, Reddit, WHOIS, DNS, government portals,
Shodan, HackerNews, StackExchange, dataset repositories, vintage web."""

import json
import os
import re
import socket
from urllib.parse import quote_plus

import arxiv
import requests
from crewai.tools import BaseTool
from duckduckgo_search import DDGS

from config import GITHUB_TOKEN, REQUEST_HEADERS, REQUEST_TIMEOUT, SHODAN_API_KEY, STACK_EXCHANGE_KEY


class ArXivSearchTool(BaseTool):
    name: str = "arxiv_search"
    description: str = (
        "Search ArXiv for academic papers in physics, mathematics, CS, biology, economics, etc. "
        "Returns paper titles, authors, abstracts, and PDF links. "
        "Input: JSON with 'query' (str), optional 'max_results' (int), 'category' (str)."
    )

    def _run(self, query: str) -> str:
        try:
            params = json.loads(query) if query.strip().startswith("{") else {"query": query}
            q = params.get("query", query)
            n = min(int(params.get("max_results", 10)), 30)
            category = params.get("category", "")
        except (json.JSONDecodeError, ValueError):
            q, n, category = query, 10, ""

        search_query = f"cat:{category} AND {q}" if category else q

        client = arxiv.Client()
        search = arxiv.Search(query=search_query, max_results=n, sort_by=arxiv.SortCriterion.Relevance)

        results = []
        for paper in client.results(search):
            results.append(
                f"TITLE: {paper.title}\n"
                f"AUTHORS: {', '.join(a.name for a in paper.authors[:5])}\n"
                f"DATE: {paper.published.strftime('%Y-%m-%d')}\n"
                f"ABSTRACT: {paper.summary[:600]}\n"
                f"PDF: {paper.pdf_url}\n"
                f"ARXIV: {paper.entry_id}"
            )

        return "\n---\n".join(results) if results else "No ArXiv results found."


class GitHubSearchTool(BaseTool):
    name: str = "github_search"
    description: str = (
        "Search GitHub's public repositories, code, issues, and commits. "
        "Finds research code, data dumps, forgotten projects, and public discussions. "
        "Input: JSON with 'query' (str), 'type' ('repositories'|'code'|'issues'|'commits'), "
        "optional 'language' (str), 'max_results' (int)."
    )

    def _run(self, query: str) -> str:
        try:
            params = json.loads(query) if query.strip().startswith("{") else {"query": query}
            q = params.get("query", query)
            search_type = params.get("type", "repositories")
            language = params.get("language", "")
            n = min(int(params.get("max_results", 10)), 30)
        except (json.JSONDecodeError, ValueError):
            q, search_type, language, n = query, "repositories", "", 10

        if language:
            q = f"{q} language:{language}"

        headers = {**REQUEST_HEADERS, "Accept": "application/vnd.github.v3+json"}
        if GITHUB_TOKEN:
            headers["Authorization"] = f"token {GITHUB_TOKEN}"

        api_url = f"https://api.github.com/search/{search_type}?q={quote_plus(q)}&per_page={n}"

        try:
            resp = requests.get(api_url, headers=headers, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            return f"GitHub search error: {e}"

        items = data.get("items", [])
        if not items:
            return "No GitHub results found."

        results = []
        for item in items:
            if search_type == "repositories":
                results.append(
                    f"REPO: {item.get('full_name')}\n"
                    f"DESCRIPTION: {item.get('description', 'N/A')}\n"
                    f"STARS: {item.get('stargazers_count')} | FORKS: {item.get('forks_count')}\n"
                    f"LANGUAGE: {item.get('language', 'N/A')}\n"
                    f"UPDATED: {item.get('updated_at', 'N/A')}\n"
                    f"URL: {item.get('html_url')}"
                )
            elif search_type == "code":
                results.append(
                    f"FILE: {item.get('path')}\n"
                    f"REPO: {item.get('repository', {}).get('full_name')}\n"
                    f"URL: {item.get('html_url')}"
                )
            else:
                results.append(
                    f"TITLE: {item.get('title')}\n"
                    f"STATE: {item.get('state')}\n"
                    f"URL: {item.get('html_url')}"
                )

        return "\n---\n".join(results)


class RedditSearchTool(BaseTool):
    name: str = "reddit_search"
    description: str = (
        "Search Reddit posts and comments across public subreddits. "
        "Useful for community knowledge, niche discussions, and historical threads. "
        "Input: JSON with 'query' (str), optional 'subreddit' (str), 'sort' ('relevance'|'new'|'top')."
    )

    def _run(self, query: str) -> str:
        try:
            params = json.loads(query) if query.strip().startswith("{") else {"query": query}
            q = params.get("query", query)
            subreddit = params.get("subreddit", "")
            sort = params.get("sort", "relevance")
        except (json.JSONDecodeError, ValueError):
            q, subreddit, sort = query, "", "relevance"

        base = f"https://www.reddit.com"
        if subreddit:
            url = f"{base}/r/{subreddit}/search.json?q={quote_plus(q)}&sort={sort}&limit=20&restrict_sr=1"
        else:
            url = f"{base}/search.json?q={quote_plus(q)}&sort={sort}&limit=20"

        headers = {**REQUEST_HEADERS, "Accept": "application/json"}
        try:
            resp = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            return f"Reddit search error: {e}"

        posts = data.get("data", {}).get("children", [])
        if not posts:
            return "No Reddit results found."

        results = []
        for post in posts:
            p = post.get("data", {})
            results.append(
                f"TITLE: {p.get('title')}\n"
                f"SUBREDDIT: r/{p.get('subreddit')}\n"
                f"SCORE: {p.get('score')} | COMMENTS: {p.get('num_comments')}\n"
                f"DATE: {p.get('created_utc')}\n"
                f"URL: https://reddit.com{p.get('permalink')}\n"
                f"CONTENT: {str(p.get('selftext', ''))[:500]}"
            )
        return "\n---\n".join(results)


class WHOISLookupTool(BaseTool):
    name: str = "whois_lookup"
    description: str = (
        "Look up WHOIS registration data and DNS records for a domain. "
        "Returns registrar, creation date, nameservers, IP, and reverse DNS. "
        "Input: a domain name (e.g. 'example.com')."
    )

    def _run(self, domain: str) -> str:
        domain = domain.strip().strip('"').replace("https://", "").replace("http://", "").split("/")[0]

        results = {}

        # DNS A records
        try:
            ips = socket.gethostbyname_ex(domain)
            results["ip_addresses"] = ips[2]
            results["hostname"] = ips[0]
        except Exception as e:
            results["dns_error"] = str(e)

        # Reverse DNS
        if "ip_addresses" in results:
            try:
                rdns = socket.gethostbyaddr(results["ip_addresses"][0])
                results["reverse_dns"] = rdns[0]
            except Exception:
                pass

        # WHOIS via public API
        try:
            resp = requests.get(
                f"https://rdap.verisign.com/com/v1/domain/{domain}",
                timeout=REQUEST_TIMEOUT,
                headers=REQUEST_HEADERS,
            )
            if resp.status_code == 200:
                rdap = resp.json()
                events = {e["eventAction"]: e["eventDate"] for e in rdap.get("events", [])}
                results["rdap"] = {
                    "name": rdap.get("ldhName"),
                    "status": rdap.get("status", []),
                    "registered": events.get("registration"),
                    "expires": events.get("expiration"),
                    "updated": events.get("last changed"),
                    "nameservers": [
                        ns.get("ldhName") for ns in rdap.get("nameservers", [])
                    ],
                }
        except Exception:
            pass

        return json.dumps(results, indent=2)


class GovernmentDocsSearchTool(BaseTool):
    name: str = "government_docs_search"
    description: str = (
        "Search US government document portals: data.gov, GovInfo, Federal Register, "
        "and FOIA reading rooms. Returns links to official government data and documents. "
        "Input: JSON with 'query' (str) and optional 'source' "
        "('all'|'govinfo'|'federalregister'|'data_gov')."
    )

    def _run(self, query: str) -> str:
        try:
            params = json.loads(query) if query.strip().startswith("{") else {"query": query}
            q = params.get("query", query)
            source = params.get("source", "all")
        except (json.JSONDecodeError, ValueError):
            q, source = query, "all"

        results = []

        if source in ("all", "govinfo"):
            try:
                url = f"https://api.govinfo.gov/search?query={quote_plus(q)}&pageSize=10&offset=0"
                resp = requests.get(url, headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT)
                if resp.status_code == 200:
                    data = resp.json()
                    for item in data.get("results", [])[:5]:
                        results.append(
                            f"SOURCE: GovInfo\n"
                            f"TITLE: {item.get('title')}\n"
                            f"DATE: {item.get('dateIssued')}\n"
                            f"URL: {item.get('detailsLink')}"
                        )
            except Exception:
                pass

        if source in ("all", "federalregister"):
            try:
                url = (
                    f"https://www.federalregister.gov/api/v1/articles.json"
                    f"?conditions[term]={quote_plus(q)}&per_page=10"
                )
                resp = requests.get(url, headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT)
                if resp.status_code == 200:
                    data = resp.json()
                    for item in data.get("results", [])[:5]:
                        results.append(
                            f"SOURCE: Federal Register\n"
                            f"TITLE: {item.get('title')}\n"
                            f"DATE: {item.get('publication_date')}\n"
                            f"TYPE: {item.get('type')}\n"
                            f"URL: {item.get('html_url')}"
                        )
            except Exception:
                pass

        if source in ("all", "data_gov"):
            try:
                url = (
                    f"https://catalog.data.gov/api/3/action/package_search"
                    f"?q={quote_plus(q)}&rows=10"
                )
                resp = requests.get(url, headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT)
                if resp.status_code == 200:
                    data = resp.json()
                    for item in data.get("result", {}).get("results", [])[:5]:
                        results.append(
                            f"SOURCE: Data.gov\n"
                            f"TITLE: {item.get('title')}\n"
                            f"ORG: {item.get('organization', {}).get('title', 'N/A')}\n"
                            f"MODIFIED: {item.get('metadata_modified')}\n"
                            f"URL: https://catalog.data.gov/dataset/{item.get('name')}"
                        )
            except Exception:
                pass

        if not results:
            # Fallback: DuckDuckGo dork on .gov domains
            with DDGS() as ddgs:
                for r in ddgs.text(f"site:.gov {q}", max_results=10):
                    results.append(
                        f"SOURCE: .gov search\n"
                        f"TITLE: {r.get('title')}\n"
                        f"URL: {r.get('href')}\n"
                        f"SNIPPET: {r.get('body', '')[:300]}"
                    )

        return "\n---\n".join(results) if results else "No government document results."


class SemanticScholarTool(BaseTool):
    name: str = "semantic_scholar_search"
    description: str = (
        "Search Semantic Scholar's corpus of 200M+ academic papers across all disciplines. "
        "Returns papers with citation counts, abstracts, and open-access PDF links. "
        "Input: JSON with 'query' (str), optional 'year_range' (str, e.g. '2010-2023'), "
        "'fields' (str, subject area), 'limit' (int)."
    )

    def _run(self, query: str) -> str:
        try:
            params = json.loads(query) if query.strip().startswith("{") else {"query": query}
            q = params.get("query", query)
            year_range = params.get("year_range", "")
            limit = min(int(params.get("limit", 10)), 20)
        except (json.JSONDecodeError, ValueError):
            q, year_range, limit = query, "", 10

        api_url = "https://api.semanticscholar.org/graph/v1/paper/search"
        api_params = {
            "query": q,
            "limit": limit,
            "fields": "title,authors,year,abstract,citationCount,openAccessPdf,externalIds",
        }
        if year_range:
            api_params["year"] = year_range

        try:
            resp = requests.get(
                api_url, params=api_params, headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            return f"Semantic Scholar error: {e}"

        papers = data.get("data", [])
        if not papers:
            return "No Semantic Scholar results."

        results = []
        for p in papers:
            pdf = p.get("openAccessPdf", {})
            results.append(
                f"TITLE: {p.get('title')}\n"
                f"AUTHORS: {', '.join(a['name'] for a in p.get('authors', [])[:4])}\n"
                f"YEAR: {p.get('year')}\n"
                f"CITATIONS: {p.get('citationCount')}\n"
                f"ABSTRACT: {str(p.get('abstract', ''))[:500]}\n"
                f"PDF: {pdf.get('url', 'N/A') if pdf else 'N/A'}\n"
                f"DOI: {p.get('externalIds', {}).get('DOI', 'N/A')}"
            )
        return "\n---\n".join(results)


class ShodanSearchTool(BaseTool):
    name: str = "shodan_search"
    description: str = (
        "Search Shodan for publicly exposed internet-connected devices, services, and hosts. "
        "Returns IP addresses, open ports, banners, hostnames, and geographic data. "
        "Useful for finding exposed servers, public APIs, misconfigured services, "
        "and infrastructure related to an organization or technology. "
        "Uses SHODAN_API_KEY if set; falls back to Shodan web dork via DuckDuckGo. "
        "Input: JSON with 'query' (str) and optional 'max_results' (int). "
        "Example queries: 'org:\"Target Corp\"', 'hostname:example.com', "
        "'product:elasticsearch country:US', 'port:27017 mongodb'."
    )

    def _run(self, query: str) -> str:
        try:
            params = json.loads(query) if query.strip().startswith("{") else {"query": query}
            q = params.get("query", query)
            n = min(int(params.get("max_results", 20)), 100)
        except (json.JSONDecodeError, ValueError):
            q, n = query, 20

        if SHODAN_API_KEY:
            try:
                resp = requests.get(
                    "https://api.shodan.io/shodan/host/search",
                    params={"key": SHODAN_API_KEY, "query": q, "minify": True},
                    headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT,
                )
                resp.raise_for_status()
                data = resp.json()
                matches = data.get("matches", [])
                total = data.get("total", 0)
                results = [f"Shodan API — {total} total matches for: {q}\n"]
                for m in matches[:n]:
                    hostnames = ", ".join(m.get("hostnames", []))
                    results.append(
                        f"IP: {m.get('ip_str')} | PORT: {m.get('port')} | "
                        f"TRANSPORT: {m.get('transport', 'tcp')}\n"
                        f"ORG: {m.get('org', 'N/A')} | ISP: {m.get('isp', 'N/A')}\n"
                        f"COUNTRY: {m.get('location', {}).get('country_name', 'N/A')}\n"
                        f"HOSTNAMES: {hostnames or 'N/A'}\n"
                        f"PRODUCT: {m.get('product', 'N/A')} | VERSION: {m.get('version', 'N/A')}\n"
                        f"BANNER: {str(m.get('data', ''))[:300]}\n"
                        f"LAST SEEN: {m.get('timestamp', 'N/A')}"
                    )
                return "\n---\n".join(results)
            except Exception as e:
                return f"Shodan API error: {e}"

        # Fallback: web dork
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(f"site:shodan.io/host {q}", max_results=n):
                results.append(
                    f"SOURCE: Shodan.io (web)\n"
                    f"TITLE: {r.get('title', '')}\n"
                    f"URL: {r.get('href', '')}\n"
                    f"SNIPPET: {r.get('body', '')[:300]}"
                )
        if not results:
            with DDGS() as ddgs:
                for r in ddgs.text(f"site:search.censys.io {q}", max_results=10):
                    results.append(
                        f"SOURCE: Censys.io (web)\n"
                        f"TITLE: {r.get('title', '')}\n"
                        f"URL: {r.get('href', '')}\n"
                        f"SNIPPET: {r.get('body', '')[:300]}"
                    )
        return "\n---\n".join(results) if results else "No Shodan results. Set SHODAN_API_KEY for full access."


class DatasetSearchTool(BaseTool):
    name: str = "dataset_search"
    description: str = (
        "Search public dataset repositories for raw data files on any topic. "
        "Covers Zenodo, Figshare, Harvard Dataverse, HuggingFace datasets. "
        "Returns dataset titles, DOIs, file formats, and download links. "
        "Input: JSON with 'query' (str) and optional 'source' "
        "('zenodo'|'figshare'|'dataverse'|'huggingface'|'all')."
    )

    def _run(self, query: str) -> str:
        try:
            params = json.loads(query) if query.strip().startswith("{") else {"query": query}
            q = params.get("query", query)
            source = params.get("source", "all")
        except (json.JSONDecodeError, ValueError):
            q, source = query, "all"

        results = []

        if source in ("all", "zenodo"):
            try:
                resp = requests.get(
                    "https://zenodo.org/api/records",
                    params={"q": q, "size": 8, "sort": "bestmatch", "type": "dataset"},
                    headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT,
                )
                if resp.status_code == 200:
                    for hit in resp.json().get("hits", {}).get("hits", [])[:6]:
                        meta = hit.get("metadata", {})
                        files = hit.get("files", [])
                        file_info = ", ".join(
                            f"{f.get('key')} ({f.get('size', 0) // 1024}KB)" for f in files[:3]
                        )
                        results.append(
                            f"SOURCE: Zenodo\n"
                            f"TITLE: {meta.get('title', 'N/A')}\n"
                            f"AUTHORS: {', '.join(c.get('name', '') for c in meta.get('creators', [])[:3])}\n"
                            f"DATE: {meta.get('publication_date', 'N/A')}\n"
                            f"FILES: {file_info or 'N/A'}\n"
                            f"DOI: {hit.get('doi', 'N/A')}\n"
                            f"URL: https://zenodo.org/record/{hit.get('id')}"
                        )
            except Exception:
                pass

        if source in ("all", "dataverse"):
            try:
                resp = requests.get(
                    "https://dataverse.harvard.edu/api/search",
                    params={"q": q, "type": "dataset", "per_page": 8},
                    headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT,
                )
                if resp.status_code == 200:
                    for item in resp.json().get("data", {}).get("items", [])[:6]:
                        results.append(
                            f"SOURCE: Harvard Dataverse\n"
                            f"TITLE: {item.get('name', 'N/A')}\n"
                            f"DESCRIPTION: {str(item.get('description', ''))[:300]}\n"
                            f"PUBLISHED: {item.get('published_at', 'N/A')}\n"
                            f"URL: {item.get('url', 'N/A')}"
                        )
            except Exception:
                pass

        if source in ("all", "figshare"):
            try:
                resp = requests.get(
                    "https://api.figshare.com/v2/articles/search",
                    json={"search_for": q, "item_type": 3, "page_size": 8},
                    headers={**REQUEST_HEADERS, "Content-Type": "application/json"},
                    timeout=REQUEST_TIMEOUT,
                )
                if resp.status_code == 200:
                    for item in resp.json()[:6]:
                        results.append(
                            f"SOURCE: Figshare\n"
                            f"TITLE: {item.get('title', 'N/A')}\n"
                            f"DOI: {item.get('doi', 'N/A')}\n"
                            f"PUBLISHED: {item.get('published_date', 'N/A')}\n"
                            f"URL: {item.get('url_public_html', 'N/A')}"
                        )
            except Exception:
                pass

        if source in ("all", "huggingface"):
            try:
                resp = requests.get(
                    "https://huggingface.co/api/datasets",
                    params={"search": q, "limit": 8, "full": False},
                    headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT,
                )
                if resp.status_code == 200:
                    for ds in resp.json()[:6]:
                        results.append(
                            f"SOURCE: HuggingFace\n"
                            f"DATASET: {ds.get('id', 'N/A')}\n"
                            f"DOWNLOADS: {ds.get('downloads', 'N/A')}\n"
                            f"TAGS: {', '.join(ds.get('tags', [])[:5])}\n"
                            f"URL: https://huggingface.co/datasets/{ds.get('id')}"
                        )
            except Exception:
                pass

        if not results:
            dork = f"({q}) (site:zenodo.org OR site:figshare.com OR site:dataverse.harvard.edu OR site:osf.io)"
            with DDGS() as ddgs:
                for r in ddgs.text(dork, max_results=10):
                    results.append(
                        f"SOURCE: Dataset repo (web)\n"
                        f"TITLE: {r.get('title', '')}\n"
                        f"URL: {r.get('href', '')}\n"
                        f"SNIPPET: {r.get('body', '')[:300]}"
                    )

        return "\n---\n".join(results) if results else "No dataset results found."


class VintageWebSearchTool(BaseTool):
    name: str = "vintage_web_search"
    description: str = (
        "Search for content on defunct and vintage web platforms from the 1990s-2000s: "
        "Geocities, Angelfire, Tripod, FortuneCity, FreeWebs, Homestead, and similar hosts "
        "preserved in Wayback Machine and Common Crawl. Also searches early SourceForge "
        "projects, LiveJournal, Xanga, Diaryland, and other early-web platforms. "
        "Input: JSON with 'query' (str) and optional 'era' ('90s'|'00s'|'all')."
    )

    def _run(self, query: str) -> str:
        try:
            params = json.loads(query) if query.strip().startswith("{") else {"query": query}
            q = params.get("query", query)
            era = params.get("era", "all")
        except (json.JSONDecodeError, ValueError):
            q, era = query, "all"

        results = []

        # Wayback CDX for vintage hosting platforms
        vintage_domains = [
            "geocities.com", "angelfire.com", "tripod.com",
            "fortunecity.com", "freewebs.com", "homestead.com",
        ]
        for domain in vintage_domains:
            try:
                date_filter = ""
                if era == "90s":
                    date_filter = "&from=19940101000000&to=19991231235959"
                elif era == "00s":
                    date_filter = "&from=20000101000000&to=20091231235959"

                cdx_url = (
                    f"https://web.archive.org/cdx/search/cdx"
                    f"?url=*.{domain}/*&output=json&limit=4"
                    f"&fl=timestamp,original,statuscode"
                    f"&filter=statuscode:200&filter=mimetype:text/html{date_filter}"
                )
                resp = requests.get(cdx_url, headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT)
                if resp.status_code == 200:
                    rows = resp.json()
                    for row in rows[1:4]:
                        ts, orig_url, status = row[0], row[1], row[2]
                        results.append(
                            f"PLATFORM: {domain} (archived)\n"
                            f"ORIGINAL URL: {orig_url}\n"
                            f"ARCHIVED: {ts[:8]}\n"
                            f"WAYBACK: https://web.archive.org/web/{ts}/{orig_url}"
                        )
            except Exception:
                pass
            import time; time.sleep(0.2)

        # Live mirrors of old Geocities content
        vintage_dork = (
            f'"{q}" (site:angelfire.com OR site:tripod.com OR '
            f'site:geocities.ws OR site:oocities.org)'
        )
        with DDGS() as ddgs:
            for r in ddgs.text(vintage_dork, max_results=8):
                results.append(
                    f"PLATFORM: Vintage web (live mirror)\n"
                    f"TITLE: {r.get('title', '')}\n"
                    f"URL: {r.get('href', '')}\n"
                    f"SNIPPET: {r.get('body', '')[:300]}"
                )

        # SourceForge
        with DDGS() as ddgs:
            for r in ddgs.text(f"site:sourceforge.net {q}", max_results=6):
                results.append(
                    f"PLATFORM: SourceForge\n"
                    f"TITLE: {r.get('title', '')}\n"
                    f"URL: {r.get('href', '')}\n"
                    f"SNIPPET: {r.get('body', '')[:300]}"
                )

        # Early blogosphere
        blog_dork = f'"{q}" (site:livejournal.com OR site:xanga.com OR site:diaryland.com)'
        with DDGS() as ddgs:
            for r in ddgs.text(blog_dork, max_results=6):
                results.append(
                    f"PLATFORM: Early blogosphere\n"
                    f"TITLE: {r.get('title', '')}\n"
                    f"URL: {r.get('href', '')}\n"
                    f"SNIPPET: {r.get('body', '')[:300]}"
                )

        return "\n---\n".join(results) if results else "No vintage web results found."
