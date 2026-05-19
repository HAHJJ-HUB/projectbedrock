import os
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
SERPAPI_KEY = os.getenv("SERPAPI_KEY", "")
FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY", "")
SHODAN_API_KEY = os.getenv("SHODAN_API_KEY", "")
STACK_EXCHANGE_KEY = os.getenv("STACK_EXCHANGE_KEY", "")

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

# ---------------------------------------------------------------------------
# Paste / text-dump sites — all publicly indexed, no authentication required
# ---------------------------------------------------------------------------
PASTE_SITES = [
    # Major general-purpose paste sites
    "pastebin.com",
    "paste.ee",
    "dpaste.com",
    "rentry.co",
    "0bin.net",
    "hastebin.com",
    "ghostbin.co",
    # Code / developer paste sites
    "gist.github.com",
    "ideone.com",
    "codepad.org",
    "termbin.com",
    "ix.io",
    "sprunge.us",
    "clbin.com",
    "bpaste.net",
    # Community / project paste sites
    "paste.mozilla.org",
    "paste.debian.net",
    "paste.ubuntu.com",
    "paste.centos.org",
    "paste.opensuse.org",
    "paste.kde.org",
    "fpaste.org",
    "paste.fedoraproject.org",
    # Misc public paste sites
    "justpaste.it",
    "pastebin.pl",
    "paste.ofcode.org",
    "controlc.com",
    "paste.laravel.io",
    "privatebin.net",
    "paste.rs",
]

# ---------------------------------------------------------------------------
# Academic / government repositories
# ---------------------------------------------------------------------------
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
    "zenodo.org",
    "figshare.com",
    "osf.io",
    "eric.ed.gov",
    "hal.science",
    "europepmc.org",
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
    "gao.gov",
    "congress.gov",
    "regulations.gov",
    "ftc.gov",
    "sec.gov/cgi-bin/srqsb",
]

# ---------------------------------------------------------------------------
# Public mailing list archive hosts
# ---------------------------------------------------------------------------
MAILING_LIST_ARCHIVES = [
    "mail-archive.com",
    "marc.info",
    "lists.debian.org",
    "lists.ubuntu.com",
    "lists.apache.org",
    "lists.freedesktop.org",
    "lkml.org",
    "spinics.net",
    "sourceware.org/ml",
]

# ---------------------------------------------------------------------------
# Dead / vintage web hosting platforms (good Wayback targets)
# ---------------------------------------------------------------------------
VINTAGE_HOSTS = [
    "angelfire.com",
    "geocities.com",
    "tripod.com",
    "fortunecity.com",
    "freewebs.com",
    "brinkster.com",
    "homestead.com",
    "bizland.com",
]
