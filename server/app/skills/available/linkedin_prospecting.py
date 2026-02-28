"""
LinkedInProspectingSkill — LinkedIn search and profile extraction.

Wraps LinkedInOps to provide high-level prospecting methods for the Sales Agent.
Searches for companies/people by industry and location, extracts profile data,
and returns structured results ready for CRM insertion.
"""

import logging
from typing import Optional

logger = logging.getLogger("mezzofy.skills.linkedin_prospecting")


class LinkedInProspectingSkill:
    """
    High-level LinkedIn prospecting skill for the Sales Agent.

    Delegates to LinkedInOps (registered in ToolExecutor) for
    actual Playwright-based scraping. Returns structured dicts.
    """

    def __init__(self, config: dict):
        self.config = config
        from app.tools.web.linkedin_ops import LinkedInOps
        self._ops = LinkedInOps(config)

    # ── Public methods (called by SalesAgent) ────────────────────────────────

    async def search_linkedin(
        self,
        query: str,
        search_type: str,
        location: Optional[str] = None,
        industry: Optional[str] = None,
        max_results: int = 10,
    ) -> dict:
        """
        Search LinkedIn for companies or people.

        Args:
            query: Search keyword(s).
            search_type: "company" or "people".
            location: Optional geographic filter.
            industry: Optional industry filter.
            max_results: Maximum results to return (default 10).

        Returns:
            {success: bool, output: list[dict] | error: str}
        """
        try:
            result = await self._ops.execute(
                "linkedin_search",
                query=query,
                search_type=search_type,
                location=location,
                industry=industry,
                max_results=max_results,
            )
            logger.info(
                f"LinkedInProspectingSkill.search_linkedin: query='{query}' "
                f"type={search_type} results={len(result.get('output', []))}"
            )
            return result
        except Exception as e:
            logger.error(f"LinkedInProspectingSkill.search_linkedin failed: {e}")
            return {"success": False, "error": str(e)}

    async def extract_profile(self, url: str) -> dict:
        """
        Extract details from a LinkedIn company or person profile URL.

        Args:
            url: LinkedIn profile URL.

        Returns:
            {success: bool, output: dict | error: str}
        """
        try:
            result = await self._ops.execute("linkedin_extract", url=url)
            logger.info(f"LinkedInProspectingSkill.extract_profile: url={url}")
            return result
        except Exception as e:
            logger.error(f"LinkedInProspectingSkill.extract_profile failed: {e}")
            return {"success": False, "error": str(e)}
