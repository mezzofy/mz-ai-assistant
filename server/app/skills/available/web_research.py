"""
WebResearchSkill — Company and market research via web scraping.

Uses ScrapingOps and BrowserOps to research companies from their websites
and public data. Returns structured summaries for use in pitch decks,
CRM enrichment, and competitive analysis.
Used by SalesAgent and ManagementAgent.
"""

import logging
from typing import Optional

logger = logging.getLogger("mezzofy.skills.web_research")


class WebResearchSkill:
    """
    Researches companies and markets via web scraping.

    Extracts: company overview, products/services, team, contact info,
    and recent news/announcements for prospect qualification.
    """

    def __init__(self, config: dict):
        self.config = config
        from app.tools.web.scraping_ops import ScrapingOps
        from app.tools.web.browser_ops import BrowserOps
        self._scraping = ScrapingOps(config)
        self._browser = BrowserOps(config)

    # ── Public methods ────────────────────────────────────────────────────────

    async def research_company(
        self,
        company_name: str,
        website_url: Optional[str] = None,
        focus_areas: Optional[list] = None,
    ) -> dict:
        """
        Research a company from their website and public data.

        Args:
            company_name: Target company name.
            website_url: Company website URL (if known).
            focus_areas: Aspects to extract: "products", "team", "funding", "news".

        Returns:
            {success: bool, output: dict with company profile | error: str}
        """
        try:
            profile: dict = {"company_name": company_name}
            focus = set(focus_areas or ["products", "team"])

            if website_url:
                # Extract main page text
                scrape_result = await self._scraping.execute(
                    "scrape_url",
                    url=website_url,
                    extract_text=True,
                )
                if scrape_result.get("success"):
                    profile["website_content"] = str(scrape_result.get("output", ""))[:3000]

                # Extract contact info
                if "team" in focus:
                    contact_result = await self._scraping.execute(
                        "extract_contact_info",
                        url=website_url,
                    )
                    if contact_result.get("success"):
                        profile["contact_info"] = contact_result.get("output", {})

            logger.info(
                f"WebResearchSkill.research_company: '{company_name}' "
                f"url={website_url} focus={focus}"
            )
            return {"success": True, "output": profile}

        except Exception as e:
            logger.error(f"WebResearchSkill.research_company failed: {e}")
            return {"success": False, "error": str(e)}

    async def search_web(self, query: str, max_results: int = 10) -> dict:
        """
        Perform a web search and extract relevant information.

        Args:
            query: Search query string.
            max_results: Maximum number of results to return (default 10).

        Returns:
            {success: bool, output: list[dict] with search results | error: str}
        """
        try:
            # Use browser to open a search page and extract results
            search_url = f"https://www.google.com/search?q={query.replace(' ', '+')}&num={max_results}"
            result = await self._browser.execute("extract_text", url=search_url)
            if result.get("success"):
                logger.info(
                    f"WebResearchSkill.search_web: query='{query}' max={max_results}"
                )
                return {
                    "success": True,
                    "output": {"query": query, "results": str(result.get("output", ""))[:3000]},
                }

            # Fall back to scraping links from search
            links_result = await self._scraping.execute(
                "extract_links",
                url=search_url,
            )
            return links_result

        except Exception as e:
            logger.error(f"WebResearchSkill.search_web failed: {e}")
            return {"success": False, "error": str(e)}
