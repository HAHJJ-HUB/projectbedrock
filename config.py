import os
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
SERPAPI_KEY = os.getenv("SERPAPI_KEY", "")
FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY", "")

CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")
MEMORY_PATH = os.getenv("MEMORY_PATH", "./memory/chroma_db")

MAX_SOURCES = int(os.getenv("MAX_SOURCES", "40"))
CRAWL_DEPTH = int(os.getenv("CRAWL_DEPTH", "2"))

REQUEST_TIMEOUT = 20
REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; ResearchBot/1.0; "
        "+https://github.com/research-agent)"
    )
}

# Paste sites to search for public content
PASTE_SITES = [
    "pastebin.com",
    "paste.ee",
    "ghostbin.co",
    "hastebin.com",
    "dpaste.com",
    "rentry.co",
    "0bin.net",
]

# Academic / government repositories
ACADEMIC_SOURCES = [
    "arxiv.org",
    "semanticscholar.org",
    "core.ac.uk",
    "researchgate.net",
    "academia.edu",
    "jstor.org",
    "scholar.google.com",
    "pubmed.ncbi.nlm.nih.gov",
    "ssrn.com",
]

GOVERNMENT_SOURCES = [
    "data.gov",
    "govinfo.gov",
    "federalregister.gov",
    "cia.gov/readingroom",
    "nsa.gov/news-features",
    "foia.gov",
    "archives.gov",
    "eric.ed.gov",
]
