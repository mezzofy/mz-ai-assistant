"""
LinkedIn Tool — profile search and extraction via authenticated Playwright session.

Tools provided:
    linkedin_search   — Search LinkedIn for people or companies by keyword
    linkedin_extract  — Extract profile data from a LinkedIn profile URL

Config section: config["tools"]["linkedin"]
  linkedin.session_cookie — LinkedIn 'li_at' cookie value (from env LINKEDIN_COOKIE)
  linkedin.rate_limit_per_session — max profiles per session (default: 50)

Library: playwright (lazy-imported; uses existing Chromium binary)

Constraints:
  - Authentication via session cookie — no passwords stored.
  - Rate limit: max 50 profile page loads per running instance (counters resets on restart).
  - Internal sales research use only — respects LinkedIn ToS.
  - Long searches should be enqueued as Celery background tasks for large result sets.
"""

import logging
import os

from app.tools.base_tool import BaseTool

logger = logging.getLogger("mezzofy.tools.linkedin")

_LINKEDIN_BASE = "https://www.linkedin.com"

# Per-instance counters for rate limiting
_session_counter: int = 0


class LinkedInOps(BaseTool):

    def __init__(self, config: dict):
        super().__init__(config)
        self._li_cfg = config.get("tools", {}).get("linkedin", {})
        self._cookie = (
            self._li_cfg.get("session_cookie")
            or os.getenv("LINKEDIN_COOKIE", "")
        )
        self._rate_limit = self._li_cfg.get("rate_limit_per_session", 50)

    def get_tools(self) -> list[dict]:
        return [
            {
                "name": "linkedin_search",
                "description": (
                    "Search LinkedIn for people or companies matching a keyword query. "
                    "Returns a list of profile/company names, titles, and URLs. "
                    "Requires valid LinkedIn session cookie. "
                    "Rate limited to 50 page loads per session."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search keyword, e.g. 'restaurant owner Singapore' or 'F&B director'",
                        },
                        "type": {
                            "type": "string",
                            "description": "Search type: 'people' (default) or 'companies'",
                            "default": "people",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Max number of results to return (default: 10, max: 25)",
                            "default": 10,
                        },
                    },
                    "required": ["query"],
                },
                "handler": self._linkedin_search,
            },
            {
                "name": "linkedin_extract",
                "description": (
                    "Extract structured profile data from a LinkedIn profile URL. "
                    "Returns name, job title, company, location, and profile summary."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "profile_url": {
                            "type": "string",
                            "description": "Full LinkedIn profile URL, e.g. https://www.linkedin.com/in/john-tan/",
                        },
                    },
                    "required": ["profile_url"],
                },
                "handler": self._linkedin_extract,
            },
        ]

    # ── Private helpers ────────────────────────────────────────────────────────

    def _check_rate_limit(self) -> bool:
        """Returns False if rate limit exceeded."""
        global _session_counter
        return _session_counter < self._rate_limit

    def _increment_counter(self) -> None:
        global _session_counter
        _session_counter += 1

    async def _make_browser(self):
        """Launch a new Playwright browser context with the LinkedIn session cookie."""
        from playwright.async_api import async_playwright

        pw = await async_playwright().start()
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        )
        if self._cookie:
            await context.add_cookies([{
                "name": "li_at",
                "value": self._cookie,
                "domain": ".linkedin.com",
                "path": "/",
                "httpOnly": True,
                "secure": True,
            }])
        return pw, browser, context

    # ── Handlers ──────────────────────────────────────────────────────────────

    async def _linkedin_search(
        self,
        query: str,
        type: str = "people",
        limit: int = 10,
    ) -> dict:
        if not self._cookie:
            return self._err("LinkedIn session cookie not configured. Set LINKEDIN_COOKIE env var.")
        if not self._check_rate_limit():
            return self._err(
                f"LinkedIn rate limit reached ({self._rate_limit} page loads per session). "
                "Restart the server or wait for the next session."
            )

        limit = min(limit, 25)
        search_type = "people" if type.lower() != "companies" else "companies"
        encoded_query = query.replace(" ", "%20")
        search_url = (
            f"{_LINKEDIN_BASE}/search/results/{search_type}/"
            f"?keywords={encoded_query}&origin=GLOBAL_SEARCH_HEADER"
        )

        pw = browser = context = None
        try:
            pw, browser, context = await self._make_browser()
            page = await context.new_page()
            self._increment_counter()

            timeout_ms = self._li_cfg.get("timeout_seconds", 30) * 1000
            await page.goto(search_url, wait_until="domcontentloaded", timeout=timeout_ms)
            await page.wait_for_timeout(2000)  # let results render

            # Extract search result cards
            results: list[dict] = []
            cards = await page.query_selector_all(
                ".reusable-search__result-container"
            )

            for card in cards[:limit]:
                try:
                    name_el = await card.query_selector(
                        ".entity-result__title-text a span[aria-hidden='true']"
                    )
                    name = (await name_el.inner_text()).strip() if name_el else ""

                    subtitle_el = await card.query_selector(".entity-result__primary-subtitle")
                    subtitle = (await subtitle_el.inner_text()).strip() if subtitle_el else ""

                    link_el = await card.query_selector(".entity-result__title-text a")
                    href = await link_el.get_attribute("href") if link_el else ""
                    profile_url = href.split("?")[0] if href else ""

                    if name:
                        results.append({
                            "name": name,
                            "subtitle": subtitle,
                            "url": profile_url,
                        })
                except Exception:
                    continue

            logger.info(f"linkedin_search: '{query}' → {len(results)} results")
            return self._ok({"results": results, "count": len(results), "query": query})
        except Exception as e:
            logger.error(f"linkedin_search failed for '{query}': {e}")
            return self._err(f"LinkedIn search failed: {e}")
        finally:
            if context:
                await context.close()
            if browser:
                await browser.close()
            if pw:
                await pw.stop()

    async def _linkedin_extract(self, profile_url: str) -> dict:
        if not profile_url.startswith("https://www.linkedin.com/"):
            return self._err("Invalid LinkedIn profile URL. Must start with https://www.linkedin.com/")
        if not self._cookie:
            return self._err("LinkedIn session cookie not configured. Set LINKEDIN_COOKIE env var.")
        if not self._check_rate_limit():
            return self._err(
                f"LinkedIn rate limit reached ({self._rate_limit} page loads per session)."
            )

        pw = browser = context = None
        try:
            pw, browser, context = await self._make_browser()
            page = await context.new_page()
            self._increment_counter()

            timeout_ms = self._li_cfg.get("timeout_seconds", 30) * 1000
            await page.goto(profile_url, wait_until="domcontentloaded", timeout=timeout_ms)
            await page.wait_for_timeout(2000)

            async def _text(selector: str) -> str:
                el = await page.query_selector(selector)
                return (await el.inner_text()).strip() if el else ""

            name = await _text("h1.text-heading-xlarge")
            title = await _text(".text-body-medium.break-words")
            location = await _text(".text-body-small.inline.t-black--light.break-words")

            # Company from experience section (first entry)
            company = await _text(
                "#experience ~ .pvs-list__container .pvs-entity .t-bold span[aria-hidden='true']"
            )

            # About/summary section
            summary = await _text("#about ~ .pvs-list__container .pv-shared-text-with-see-more")

            if not name:
                return self._err(
                    "Could not extract profile. Session cookie may be expired or profile is private."
                )

            logger.info(f"linkedin_extract: {profile_url} → {name!r}")
            return self._ok({
                "name": name,
                "title": title,
                "company": company,
                "location": location,
                "summary": summary,
                "url": profile_url,
            })
        except Exception as e:
            logger.error(f"linkedin_extract failed for {profile_url}: {e}")
            return self._err(f"LinkedIn profile extraction failed: {e}")
        finally:
            if context:
                await context.close()
            if browser:
                await browser.close()
            if pw:
                await pw.stop()
