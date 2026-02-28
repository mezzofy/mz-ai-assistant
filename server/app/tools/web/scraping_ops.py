"""
Scraping Tool — lightweight HTTP + BeautifulSoup extraction (no browser required).

Tools provided:
    scrape_url          — Fetch and extract text/HTML from a URL (optional CSS selector)
    extract_tables      — Extract all HTML tables as structured data
    extract_links       — Get all hyperlinks from a page
    extract_contact_info — Find emails, phone numbers, and addresses on a page

Config section: config["tools"]["browser"] (timeout_seconds reused)
Libraries: aiohttp, beautifulsoup4, lxml (all lazy-imported)

Security: Same SSRF URL blocklist as browser_ops.
"""

import logging
import re
from typing import Optional

from app.tools.base_tool import BaseTool

logger = logging.getLogger("mezzofy.tools.scraping")

# Shared SSRF blocklist
_BLOCKED_URL_PATTERNS = [
    r"localhost",
    r"127\.\d+\.\d+\.\d+",
    r"0\.0\.0\.0",
    r"10\.\d+\.\d+\.\d+",
    r"192\.168\.\d+\.\d+",
    r"172\.(1[6-9]|2\d|3[01])\.\d+\.\d+",
    r"169\.254\.\d+\.\d+",
    r"::1",
    r"^file://",
    r"^data://",
    r"^javascript:",
]

# Regex patterns for contact info extraction
_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", re.IGNORECASE)
_PHONE_RE = re.compile(
    r"(?:\+?\d{1,3}[\s\-.]?)?"          # country code
    r"(?:\(?\d{2,4}\)?[\s\-.]?)?"       # area code
    r"\d{3,4}[\s\-.]?\d{4}"             # number
)
_ADDRESS_COMMON_KEYWORDS = [
    r"\d+\s+\w+\s+(Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Lane|Ln|Blvd|Boulevard|Way|Court|Ct)",
]


class ScrapingOps(BaseTool):

    def get_tools(self) -> list[dict]:
        return [
            {
                "name": "scrape_url",
                "description": (
                    "Fetch a URL with HTTP and extract its text content using BeautifulSoup. "
                    "Optionally filter to a specific CSS selector. "
                    "Faster than browser_ops for static pages that don't require JavaScript."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "Public URL to scrape",
                        },
                        "css_selector": {
                            "type": "string",
                            "description": (
                                "Optional CSS selector to extract a specific element "
                                "(e.g. 'article', '.content', '#main')"
                            ),
                        },
                    },
                    "required": ["url"],
                },
                "handler": self._scrape_url,
            },
            {
                "name": "extract_tables",
                "description": (
                    "Extract all HTML tables from a web page and return them as lists of rows. "
                    "Useful for financial data, pricing tables, or any tabular content."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "Public URL containing tables to extract",
                        },
                    },
                    "required": ["url"],
                },
                "handler": self._extract_tables,
            },
            {
                "name": "extract_links",
                "description": (
                    "Extract all hyperlinks from a web page. "
                    "Can optionally filter to same-domain links only."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "Public URL to extract links from",
                        },
                        "same_domain_only": {
                            "type": "boolean",
                            "description": "If true, only return links on the same domain (default: false)",
                            "default": False,
                        },
                    },
                    "required": ["url"],
                },
                "handler": self._extract_links,
            },
            {
                "name": "extract_contact_info",
                "description": (
                    "Find email addresses, phone numbers, and physical addresses on a web page "
                    "using regex pattern matching on the page text."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "Public URL to scan for contact information",
                        },
                    },
                    "required": ["url"],
                },
                "handler": self._extract_contact_info,
            },
        ]

    # ── Private helpers ────────────────────────────────────────────────────────

    def _validate_url(self, url: str) -> Optional[str]:
        if not url.startswith(("http://", "https://")):
            return "URL must start with http:// or https://"
        for pattern in _BLOCKED_URL_PATTERNS:
            if re.search(pattern, url, re.IGNORECASE):
                return "URL blocked: internal/private addresses are not permitted"
        return None

    def _timeout(self) -> int:
        """Total HTTP request timeout in seconds."""
        return self.config.get("tools", {}).get("browser", {}).get("timeout_seconds", 30)

    async def _fetch_html(self, url: str) -> tuple[str, str]:
        """
        Fetch URL with aiohttp, return (html_text, final_url).
        Raises on HTTP error or connection failure.
        """
        import aiohttp

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (compatible; MezzofyAI/1.0; +https://mezzofy.com)"
            )
        }
        timeout = aiohttp.ClientTimeout(total=self._timeout())
        async with aiohttp.ClientSession(headers=headers, timeout=timeout) as session:
            async with session.get(url, allow_redirects=True) as resp:
                resp.raise_for_status()
                html = await resp.text(errors="replace")
                return html, str(resp.url)

    # ── Handlers ──────────────────────────────────────────────────────────────

    async def _scrape_url(self, url: str, css_selector: Optional[str] = None) -> dict:
        err = self._validate_url(url)
        if err:
            return self._err(err)
        try:
            from bs4 import BeautifulSoup

            html, final_url = await self._fetch_html(url)
            soup = BeautifulSoup(html, "lxml")

            # Remove script/style noise
            for tag in soup(["script", "style", "noscript"]):
                tag.decompose()

            if css_selector:
                elements = soup.select(css_selector)
                if not elements:
                    return self._err(f"CSS selector '{css_selector}' matched no elements")
                text = "\n\n".join(el.get_text(separator="\n", strip=True) for el in elements)
                raw_html = "\n".join(str(el) for el in elements)
            else:
                text = soup.get_text(separator="\n", strip=True)
                raw_html = str(soup.body) if soup.body else html[:50_000]

            # Collapse excessive blank lines
            text = re.sub(r"\n{3,}", "\n\n", text)

            logger.info(f"scrape_url: {url}, {len(text)} chars")
            return self._ok({
                "text": text,
                "html": raw_html[:50_000],  # Truncate large pages
                "url": final_url,
            })
        except Exception as e:
            logger.error(f"scrape_url failed for {url}: {e}")
            return self._err(f"Scraping failed: {e}")

    async def _extract_tables(self, url: str) -> dict:
        err = self._validate_url(url)
        if err:
            return self._err(err)
        try:
            from bs4 import BeautifulSoup

            html, _ = await self._fetch_html(url)
            soup = BeautifulSoup(html, "lxml")

            tables: list[list[list[str]]] = []
            for table_tag in soup.find_all("table"):
                rows: list[list[str]] = []
                for tr in table_tag.find_all("tr"):
                    cells = [
                        cell.get_text(strip=True)
                        for cell in tr.find_all(["th", "td"])
                    ]
                    if cells:
                        rows.append(cells)
                if rows:
                    tables.append(rows)

            logger.info(f"extract_tables: {url}, {len(tables)} tables found")
            return self._ok({"tables": tables, "count": len(tables)})
        except Exception as e:
            logger.error(f"extract_tables failed for {url}: {e}")
            return self._err(f"Table extraction failed: {e}")

    async def _extract_links(self, url: str, same_domain_only: bool = False) -> dict:
        err = self._validate_url(url)
        if err:
            return self._err(err)
        try:
            from urllib.parse import urljoin, urlparse

            from bs4 import BeautifulSoup

            html, final_url = await self._fetch_html(url)
            soup = BeautifulSoup(html, "lxml")
            base_domain = urlparse(final_url).netloc

            links: list[dict] = []
            seen: set[str] = set()

            for a_tag in soup.find_all("a", href=True):
                href = a_tag["href"].strip()
                if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
                    continue

                absolute = urljoin(final_url, href)
                if absolute in seen:
                    continue
                seen.add(absolute)

                if same_domain_only and urlparse(absolute).netloc != base_domain:
                    continue

                links.append({
                    "url": absolute,
                    "text": a_tag.get_text(strip=True)[:200],
                })

            logger.info(f"extract_links: {url}, {len(links)} links")
            return self._ok({"links": links, "count": len(links)})
        except Exception as e:
            logger.error(f"extract_links failed for {url}: {e}")
            return self._err(f"Link extraction failed: {e}")

    async def _extract_contact_info(self, url: str) -> dict:
        err = self._validate_url(url)
        if err:
            return self._err(err)
        try:
            from bs4 import BeautifulSoup

            html, _ = await self._fetch_html(url)
            soup = BeautifulSoup(html, "lxml")
            text = soup.get_text(separator=" ", strip=True)

            emails = list(set(_EMAIL_RE.findall(text)))
            phones = list(set(m.strip() for m in _PHONE_RE.findall(text) if len(m.strip()) >= 7))

            # Simple address heuristic
            addresses: list[str] = []
            for pattern in _ADDRESS_COMMON_KEYWORDS:
                for match in re.finditer(pattern, text, re.IGNORECASE):
                    start = max(0, match.start() - 10)
                    snippet = text[start : match.end() + 60].strip()
                    if snippet not in addresses:
                        addresses.append(snippet)

            logger.info(
                f"extract_contact_info: {url}, "
                f"{len(emails)} emails, {len(phones)} phones, {len(addresses)} addresses"
            )
            return self._ok({
                "emails": emails,
                "phones": phones,
                "addresses": addresses,
            })
        except Exception as e:
            logger.error(f"extract_contact_info failed for {url}: {e}")
            return self._err(f"Contact info extraction failed: {e}")
