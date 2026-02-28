"""
ContentGenerationSkill — Marketing content creation in Mezzofy brand voice.

Loads brand guidelines from the knowledge base, fetches product data,
and uses the LLM (via LLMManager) to generate on-brand content.
Used by MarketingAgent.
"""

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger("mezzofy.skills.content_generation")

# Default Mezzofy brand guidelines (used when no KB file found)
_DEFAULT_BRAND_GUIDELINES = """
Mezzofy Brand Voice:
- Confident and authoritative — we're the leader in coupon/loyalty exchange
- Friendly and approachable — we build partnerships, not just transactions
- Results-focused — always tie features to business outcomes
- Clear and concise — no jargon, no fluff

Brand colors: Orange (#f97316), Black (#000000), White (#ffffff)
Tagline: "The Smarter Way to Loyalty"
"""

_CONTENT_LENGTHS = {
    "short": 200,
    "medium": 500,
    "long": 1000,
}

_CONTENT_DESCRIPTIONS = {
    "website": "website landing page copy",
    "playbook": "customer playbook document",
    "blog": "blog post article",
    "social": "social media posts (LinkedIn, Facebook, Instagram)",
    "newsletter": "email newsletter",
}


class ContentGenerationSkill:
    """
    Generates marketing content using the LLM with Mezzofy brand context.

    Loads brand guidelines and product data to ensure content accuracy
    and consistency with Mezzofy's voice and positioning.
    """

    def __init__(self, config: dict):
        self.config = config
        from app.tools.mezzofy.knowledge_ops import KnowledgeOps
        from app.tools.mezzofy.data_ops import MezzofyDataOps
        self._knowledge = KnowledgeOps(config)
        self._data = MezzofyDataOps(config)

    # ── Public methods ────────────────────────────────────────────────────────

    async def generate_content(
        self,
        content_type: str,
        topic: str,
        audience: Optional[str] = None,
        tone: Optional[str] = None,
        length: Optional[str] = None,
    ) -> dict:
        """
        Create marketing content of specified type.

        Args:
            content_type: "website", "playbook", "blog", "social", or "newsletter".
            topic: Content topic or theme.
            audience: "prospects", "customers", or "partners".
            tone: "professional", "casual", or "technical".
            length: "short", "medium", or "long".

        Returns:
            {success: bool, output: str (generated content) | error: str}
        """
        try:
            # Load brand context
            brand_result = await self._knowledge.execute("get_brand_guidelines")
            brand_context = (
                brand_result.get("output", _DEFAULT_BRAND_GUIDELINES)
                if brand_result.get("success")
                else _DEFAULT_BRAND_GUIDELINES
            )

            # Load relevant product data for accuracy
            products_result = await self._data.execute("get_products")
            product_context = (
                str(products_result.get("output", ""))[:1000]
                if products_result.get("success")
                else ""
            )

            # Build generation prompt
            prompt = self._build_prompt(
                content_type=content_type,
                topic=topic,
                audience=audience,
                tone=tone,
                length=length,
                brand_context=brand_context,
                product_context=product_context,
            )

            # Use LLM for generation
            from app.llm import llm_manager as llm_mod
            result = await llm_mod.get().chat(
                messages=[{"role": "user", "content": prompt}],
                task_context={"department": "marketing", "role": "content_writer", "source": "skill"},
            )

            content = result.get("content", "")
            logger.info(
                f"ContentGenerationSkill.generate_content: type={content_type} "
                f"topic='{topic}' chars={len(content)}"
            )
            return {"success": True, "output": content}

        except Exception as e:
            logger.error(f"ContentGenerationSkill.generate_content failed: {e}")
            return {"success": False, "error": str(e)}

    # ── Private helpers ───────────────────────────────────────────────────────

    def _build_prompt(
        self,
        content_type: str,
        topic: str,
        audience: Optional[str],
        tone: Optional[str],
        length: Optional[str],
        brand_context: str,
        product_context: str,
    ) -> str:
        """Build the LLM prompt for content generation."""
        content_desc = _CONTENT_DESCRIPTIONS.get(content_type, f"{content_type} content")
        word_count = _CONTENT_LENGTHS.get(length or "medium", 500)
        tone_desc = tone or "professional"
        audience_desc = audience or "prospects"

        return (
            f"You are a marketing copywriter for Mezzofy, a coupon and loyalty exchange platform.\n\n"
            f"Brand guidelines:\n{brand_context}\n\n"
            f"Product context:\n{product_context}\n\n"
            f"Task: Write {content_desc} about the following topic:\n{topic}\n\n"
            f"Requirements:\n"
            f"- Target audience: {audience_desc}\n"
            f"- Tone: {tone_desc}\n"
            f"- Approximate length: {word_count} words\n"
            f"- Follow Mezzofy brand voice strictly\n"
            f"- Focus on business outcomes and ROI\n"
            f"- Use clear headings and bullet points where appropriate\n\n"
            f"Generate the content now:"
        )
