"""
SourceVerificationSkill — Credibility scoring and cross-referencing sources.

Used by ResearchAgent to verify claims, assess source credibility,
and flag unreliable or unverified information.
"""

import logging

logger = logging.getLogger("mezzofy.skills.source_verification")

# Known high-credibility domain patterns
_HIGH_CREDIBILITY_DOMAINS = {
    "reuters.com", "bloomberg.com", "ft.com", "wsj.com", "economist.com",
    "harvard.edu", "mit.edu", "stanford.edu", "oxford.ac.uk",
    "gov.sg", "mas.gov.sg", "worldbank.org", "imf.org",
    "nature.com", "sciencedirect.com", "pubmed.ncbi.nlm.nih.gov",
}
_LOW_CREDIBILITY_PATTERNS = {"reddit.com", "quora.com", "answers.yahoo.com"}


class SourceVerificationSkill:
    """
    Assess source credibility and verify claims against multiple sources.
    """

    def __init__(self, config: dict):
        self.config = config

    def score_source(self, url: str, title: str = "") -> dict:
        """
        Score a source's credibility based on domain and heuristics.

        Returns:
            {score: 0.0–1.0, tier: "high"|"medium"|"low", reason: str}
        """
        if not url:
            return {"score": 0.3, "tier": "low", "reason": "No URL provided"}

        domain = url.split("/")[2].lower().lstrip("www.") if "://" in url else url.lower()

        if any(hc in domain for hc in _HIGH_CREDIBILITY_DOMAINS):
            return {"score": 0.9, "tier": "high", "reason": f"Trusted domain: {domain}"}
        if any(lc in domain for lc in _LOW_CREDIBILITY_PATTERNS):
            return {"score": 0.3, "tier": "low", "reason": f"Community/forum source: {domain}"}
        if domain.endswith(".gov") or domain.endswith(".edu") or domain.endswith(".ac.uk"):
            return {"score": 0.85, "tier": "high", "reason": f"Official/academic domain: {domain}"}

        return {"score": 0.55, "tier": "medium", "reason": f"Unknown domain: {domain}"}

    async def verify_claim(self, claim: str, supporting_sources: list[dict]) -> dict:
        """
        Verify a claim against provided sources.

        Args:
            claim:              The claim to verify.
            supporting_sources: List of {url, title, excerpt} dicts.

        Returns:
            {success, output: {verdict, confidence, corroborating, contradicting}}
        """
        try:
            from app.llm import llm_manager as llm_mod
            sources_text = "\n".join(
                f"- {s.get('title', 'Source')}: {s.get('excerpt', '')[:200]}"
                for s in supporting_sources[:5]
            )
            prompt = (
                f"Verify this claim using the provided sources.\n\n"
                f"Claim: {claim}\n\n"
                f"Sources:\n{sources_text}\n\n"
                f"Return verdict: Verified / Unverified / Contradicted\n"
                f"And confidence: High / Medium / Low\n"
                f"Brief explanation (1–2 sentences)."
            )
            result = await llm_mod.get().chat(
                messages=[{"role": "user", "content": prompt}],
                task_context={},
            )
            content = result.get("content", "")
            verdict = "Unverified"
            for v in ("Verified", "Contradicted", "Unverified"):
                if v.lower() in content.lower():
                    verdict = v
                    break

            return {
                "success": True,
                "output": {
                    "claim": claim,
                    "verdict": verdict,
                    "confidence": "medium",
                    "explanation": content[:500],
                    "source_scores": [
                        self.score_source(s.get("url", "")) for s in supporting_sources[:5]
                    ],
                },
            }
        except Exception as e:
            logger.error(f"SourceVerificationSkill.verify_claim failed: {e}")
            return {"success": False, "error": str(e)}
