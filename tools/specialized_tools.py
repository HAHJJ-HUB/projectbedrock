"""Specialized source tools: ArXiv, GitHub, Reddit, WHOIS, DNS, government portals."""

import json
import os
import re
import socket
from urllib.parse import quote_plus

import arxiv
import requests
from crewai.tools import BaseTool
from duckduckgo_search import DDGS

from config import GITHUB_TOKEN, REQUEST_HEADERS, REQUEST_TIMEOUT


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
