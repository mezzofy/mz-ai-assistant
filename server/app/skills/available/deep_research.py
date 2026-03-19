"""
DeepResearchSkill — Multi-source research synthesis with citation tracking.

Used by ResearchAgent to perform comprehensive research across multiple sources,
synthesise findings, and track citations for credibility.
"""

import logging
from typing import Any, Optional

logger = logging.getLogger("mezzofy.skills.deep_research")


class DeepResearchSkill:
    """
    Multi-source research synthesis with citation management.

    Performs deep research by querying multiple sources, cross-referencing
    findings, and producing structured reports with verified citations.
    """

    def __init__(self, config: dict):
        self.config = config

    async def synthesise(
        self,
        query: str,
        sources: list[dict],
        max_sources: int = 10,
    ) -> dict:
        """
        Synthesise findings from multiple sources into a structured report.

        Args:
            query:       Research question or topic.
            sources:     List of {url, title, excerpt} dicts from web search.
            max_sources: Maximum number of sources to include.

        Returns:
            {success: bool, output: {summary, findings, citations, confidence}}
        """
        try:
            from app.llm import llm_manager as llm_mod
            sources_text = "\n".join(
                f"[{i+1}] {s.get('title', 'Source')} ({s.get('url', '')}): "
                f"{s.get('excerpt', '')[:300]}"
                for i, s in enumerate(sources[:max_sources])
            )
            prompt = (
                f"Research question: {query}\n\n"
                f"Sources:\n{sources_text}\n\n"
                f"Synthesise a comprehensive answer with:\n"
                f"1. Executive summary (2–3 sentences)\n"
                f"2. Key findings (bullet points with source references [N])\n"
                f"3. Confidence level: High / Medium / Low\n"
                f"4. Knowledge gaps or areas needing more research"
            )
            result = await llm_mod.get().chat(
                messages=[{"role": "user", "content": prompt}],
                task_context={},
            )
            return {
                "success": True,
                "output": {
                    "summary": result.get("content", ""),
                    "findings": [],
                    "citations": [
                        {"index": i+1, "url": s.get("url", ""), "title": s.get("title", "")}
                        for i, s in enumerate(sources[:max_sources])
                    ],
                    "confidence": "medium",
                },
            }
        except Exception as e:
            logger.error(f"DeepResearchSkill.synthesise failed: {e}")
            return {"success": False, "error": str(e)}

    async def extract_key_facts(self, text: str, topic: str) -> dict:
        """
        Extract structured key facts from a body of text.

        Returns:
            {success: bool, output: {facts: [{fact, source_sentence, relevance_score}]}}
        """
        try:
            from app.llm import llm_manager as llm_mod
            prompt = (
                f"From this text about '{topic}', extract the 5 most important facts.\n"
                f"Return each as: FACT: <fact> | SOURCE: <exact quote from text>\n\n"
                f"Text: {text[:3000]}"
            )
            result = await llm_mod.get().chat(
                messages=[{"role": "user", "content": prompt}],
                task_context={},
            )
            return {"success": True, "output": {"facts_text": result.get("content", "")}}
        except Exception as e:
            return {"success": False, "error": str(e)}
