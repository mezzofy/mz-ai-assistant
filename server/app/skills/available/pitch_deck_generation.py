"""
PitchDeckGenerationSkill — Sales pitch deck creation using Mezzofy product data.

Uses PptxOps to generate branded PPTX decks and MezzofyDataOps to pull
the latest product info, pricing, and case studies.
Used by SalesAgent for customer-specific pitch materials.
"""

import logging
from typing import Optional

logger = logging.getLogger("mezzofy.skills.pitch_deck_generation")


class PitchDeckGenerationSkill:
    """
    Creates PPTX pitch decks tailored to specific customers/prospects.

    Loads the Mezzofy PPTX template, injects customer context,
    product features, case studies, and pricing into slide content.
    """

    def __init__(self, config: dict):
        self.config = config
        from app.tools.document.pptx_ops import PPTXOps
        from app.tools.mezzofy.data_ops import MezzofyDataOps
        self._pptx = PPTXOps(config)
        self._data = MezzofyDataOps(config)

    # ── Public methods ────────────────────────────────────────────────────────

    async def create_pitch_deck(
        self,
        customer_name: str,
        industry: Optional[str] = None,
        focus_products: Optional[list] = None,
        include_pricing: bool = True,
        include_case_studies: bool = True,
    ) -> dict:
        """
        Generate a PPTX pitch deck for a specific customer.

        Args:
            customer_name: Name of the customer/prospect.
            industry: Customer's industry (for context and case study selection).
            focus_products: List of Mezzofy product names to highlight.
            include_pricing: Whether to include a pricing slide.
            include_case_studies: Whether to include relevant case studies.

        Returns:
            {success: bool, output: str (file path) | error: str}
        """
        try:
            # Gather content for the deck
            sections = await self._build_deck_content(
                customer_name=customer_name,
                industry=industry,
                focus_products=focus_products,
                include_pricing=include_pricing,
                include_case_studies=include_case_studies,
            )

            # Delegate PPTX creation to PptxOps
            result = await self._pptx.execute(
                "create_presentation",
                title=f"Mezzofy — {customer_name}",
                sections=sections,
            )
            logger.info(
                f"PitchDeckGenerationSkill.create_pitch_deck: "
                f"customer='{customer_name}' industry={industry}"
            )
            return result

        except Exception as e:
            logger.error(f"PitchDeckGenerationSkill.create_pitch_deck failed: {e}")
            return {"success": False, "error": str(e)}

    async def get_mezzofy_products(self, product_category: Optional[str] = None) -> dict:
        """
        Fetch latest Mezzofy product data, features, and pricing.

        Args:
            product_category: Optional filter (e.g., "loyalty", "coupons").

        Returns:
            {success: bool, output: dict | error: str}
        """
        try:
            result = await self._data.execute(
                "get_products",
                category=product_category,
            )
            logger.info(
                f"PitchDeckGenerationSkill.get_mezzofy_products: category={product_category}"
            )
            return result
        except Exception as e:
            logger.error(f"PitchDeckGenerationSkill.get_mezzofy_products failed: {e}")
            return {"success": False, "error": str(e)}

    # ── Private helpers ───────────────────────────────────────────────────────

    async def _build_deck_content(
        self,
        customer_name: str,
        industry: Optional[str],
        focus_products: Optional[list],
        include_pricing: bool,
        include_case_studies: bool,
    ) -> list[dict]:
        """Build ordered list of slide sections for the pitch deck."""
        sections = [
            {
                "title": "Cover",
                "content": f"Mezzofy — Powering {customer_name}'s Loyalty Strategy",
            },
            {
                "title": "The Challenge",
                "content": (
                    f"{'Industry: ' + industry if industry else 'Your industry'} faces "
                    "increasing competition for customer loyalty. "
                    "Generic discounts erode margins without building lasting relationships."
                ),
            },
            {
                "title": "Our Solution",
                "content": (
                    "Mezzofy delivers a complete coupon and loyalty exchange platform — "
                    "enabling merchants to issue, manage, and redeem loyalty rewards "
                    "across digital and physical channels."
                ),
            },
        ]

        # Products slide
        products_result = await self._data.execute(
            "get_products", category=(focus_products[0] if focus_products else None)
        )
        if products_result.get("success") and products_result.get("output"):
            sections.append({
                "title": "Product Features",
                "content": str(products_result["output"])[:2000],
            })

        # Case studies slide
        if include_case_studies:
            cs_result = await self._data.execute(
                "get_case_studies", industry=industry
            )
            if cs_result.get("success") and cs_result.get("output"):
                sections.append({
                    "title": "Case Studies",
                    "content": str(cs_result["output"])[:2000],
                })

        # Pricing slide
        if include_pricing:
            pricing_result = await self._data.execute("get_pricing")
            if pricing_result.get("success") and pricing_result.get("output"):
                sections.append({
                    "title": "Pricing",
                    "content": str(pricing_result["output"])[:1500],
                })

        sections.append({
            "title": "Next Steps",
            "content": (
                f"Let's schedule a product demo tailored to {customer_name}'s use case.\n"
                "Contact: sales@mezzofy.com"
            ),
        })

        return sections
