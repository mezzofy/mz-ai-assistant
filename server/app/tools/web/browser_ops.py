"""
Browser Tool — Playwright headless Chromium for page loading, screenshots, and text extraction.

Tools provided:
    open_page       — Load a URL and return title, final URL, HTTP status
    screenshot_page — Take a full-page screenshot and return base64 JPEG
    extract_text    — Extract all visible body text from a page

Config section: config["tools"]["browser"]
Library: playwright (lazy-imported; headless Chromium)

Security: SSRF blocklist applied — private/internal IP ranges and non-HTTP schemes are rejected.
          A singleton browser instance is reused across calls to avoid per-call launch overhead.
"""

import logging
import re
from typing import Optional

from app.tools.base_tool import BaseTool

logger = logging.getLogger("mezzofy.tools.browser")

# SSRF protection — block access to internal/private networks
_BLOCKED_URL_PATTERNS = [
    r"localhost",
    r"127\.\d+\.\d+\.\d+",
    r"0\.0\.0\.0",
    r"10\.\d+\.\d+\.\d+",
    r"192\.168\.\d+\.\d+",
    r"172\.(1[6-9]|2\d|3[01])\.\d+\.\d+",
    r"169\.254\.\d+\.\d+",   # link-local
    r"::1",                    # IPv6 loopback
    r"fc00:",                  # IPv6 private
    r"^file://",
    r"^data://",
    r"^javascript:",
]

# Singleton browser instance — lazily initialised and reused
_playwright_instance = None
_browser_instance = None


class BrowserOps(BaseTool):

    def get_tools(self) -> list[dict]:
        return [
            {
                "name": "open_page",
                "description": (
                    "Load a URL in a headless browser and return the page title, "
                    "final URL (after redirects), and HTTP status code. "
                    "Use before screenshot_page or extract_text."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "Public HTTPS URL to load",
                        },
                        "wait_for": {
                            "type": "string",
                            "description": (
                                "Page load wait condition: "
                                "'networkidle' (default), 'load', 'domcontentloaded'"
                            ),
                            "default": "networkidle",
                        },
                        "timeout_seconds": {
                            "type": "integer",
                            "description": "Page load timeout in seconds (default: 30, max: 60)",
                            "default": 30,
                        },
                    },
                    "required": ["url"],
                },
                "handler": self._open_page,
            },
            {
                "name": "screenshot_page",
                "description": (
                    "Take a full-page screenshot of a URL using a headless browser. "
                    "Returns the screenshot as a base64-encoded JPEG image."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "Public URL to screenshot",
                        },
                    },
                    "required": ["url"],
                },
                "handler": self._screenshot_page,
            },
            {
                "name": "extract_text",
                "description": (
                    "Extract all visible body text from a web page using a headless browser. "
                    "Useful for reading articles, blog posts, or text-heavy content "
                    "where JavaScript rendering is required."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "Public URL to extract text from",
                        },
                    },
                    "required": ["url"],
                },
                "handler": self._extract_text,
            },
        ]

    # ── Private helpers ────────────────────────────────────────────────────────

    def _validate_url(self, url: str) -> Optional[str]:
        """Return an error string if the URL is blocked; None if it is safe."""
        if not url.startswith(("http://", "https://")):
            return "URL must start with http:// or https://"
        for pattern in _BLOCKED_URL_PATTERNS:
            if re.search(pattern, url, re.IGNORECASE):
                return "URL blocked: internal/private addresses are not permitted"
        return None

    async def _get_browser(self):
        """Return the singleton Playwright Chromium browser, launching if needed."""
        global _playwright_instance, _browser_instance
        from playwright.async_api import async_playwright

        if _browser_instance is None:
            cfg = self.config.get("tools", {}).get("browser", {})
            _playwright_instance = await async_playwright().start()
            _browser_instance = await _playwright_instance.chromium.launch(
                headless=cfg.get("headless", True),
            )
        return _browser_instance

    def _timeout_ms(self) -> int:
        cfg = self.config.get("tools", {}).get("browser", {})
        return min(cfg.get("timeout_seconds", 30), 60) * 1000

    # ── Handlers ──────────────────────────────────────────────────────────────

    async def _open_page(
        self,
        url: str,
        wait_for: str = "networkidle",
        timeout_seconds: int = 30,
    ) -> dict:
        err = self._validate_url(url)
        if err:
            return self._err(err)
        try:
            browser = await self._get_browser()
            timeout_ms = min(timeout_seconds, 60) * 1000
            page = await browser.new_page()
            try:
                response = await page.goto(url, wait_until=wait_for, timeout=timeout_ms)
                title = await page.title()
                final_url = page.url
                status = response.status if response else None
                logger.info(f"open_page: {url} → status={status}, title={title!r}")
                return self._ok({"title": title, "url": final_url, "status": status})
            finally:
                await page.close()
        except Exception as e:
            logger.error(f"open_page failed for {url}: {e}")
            return self._err(f"Failed to open page: {e}")

    async def _screenshot_page(self, url: str) -> dict:
        err = self._validate_url(url)
        if err:
            return self._err(err)
        try:
            import base64

            browser = await self._get_browser()
            page = await browser.new_page()
            try:
                await page.goto(url, wait_until="networkidle", timeout=self._timeout_ms())
                screenshot = await page.screenshot(full_page=True, type="jpeg")
                b64 = base64.b64encode(screenshot).decode()
                logger.info(f"screenshot_page: {url}, {len(screenshot)} bytes")
                return self._ok({"image_bytes": b64, "url": page.url})
            finally:
                await page.close()
        except Exception as e:
            logger.error(f"screenshot_page failed for {url}: {e}")
            return self._err(f"Screenshot failed: {e}")

    async def _extract_text(self, url: str) -> dict:
        err = self._validate_url(url)
        if err:
            return self._err(err)
        try:
            browser = await self._get_browser()
            page = await browser.new_page()
            try:
                await page.goto(
                    url, wait_until="domcontentloaded", timeout=self._timeout_ms()
                )
                text = await page.inner_text("body")
                # Collapse excessive blank lines
                text = re.sub(r"\n{3,}", "\n\n", text.strip())
                logger.info(f"extract_text: {url}, {len(text)} chars")
                return self._ok({"text": text, "url": page.url, "length": len(text)})
            finally:
                await page.close()
        except Exception as e:
            logger.error(f"extract_text failed for {url}: {e}")
            return self._err(f"Text extraction failed: {e}")
