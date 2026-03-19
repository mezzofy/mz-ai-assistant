"""
LegalResearchSkill — Research jurisdiction-specific laws and compliance requirements.

Provides tools for looking up applicable law, regulatory requirements, and
compliance obligations across 7 supported jurisdictions.

Uses the knowledge base (KB) files under server/knowledge/legal/ as the primary
source, with optional web search for deep-depth research.
"""

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger("mezzofy.skills.legal_research")

# Knowledge base root — resolved relative to server/
_KNOWLEDGE_BASE_PATH = Path(__file__).parent.parent.parent.parent / "knowledge" / "legal"

_SUPPORTED_JURISDICTIONS = [
    "singapore", "hong_kong", "malaysia", "uae",
    "saudi_arabia", "qatar", "cayman_islands",
]


class LegalResearchSkill:
    """
    Skill for researching jurisdiction-specific legal and regulatory matters.

    Provides:
      - research_jurisdiction_law: KB lookup + optional web search
      - lookup_regulatory_requirements: KB lookup for regulatory needs
      - check_compliance_requirements: multi-jurisdiction compliance check
    """

    async def research_jurisdiction_law(
        self,
        topic: str,
        jurisdiction: str,
        depth: str = "standard",
    ) -> dict:
        """
        Research the applicable law and legal framework for a topic in a jurisdiction.

        Args:
            topic: Legal topic to research (e.g., "employment termination", "IP registration").
            jurisdiction: Target jurisdiction key (e.g., "singapore", "hong_kong").
            depth: "overview" | "standard" | "deep" (deep includes web search).

        Returns:
            {
                "success": bool,
                "jurisdiction": str,
                "topic": str,
                "summary": str,
                "key_statutes": list[str],
                "source": str,
                "web_results": list | None,
            }
        """
        jurisdiction = self._normalise_jurisdiction(jurisdiction)

        # Load KB file
        kb_content = self._load_jurisdiction_kb(jurisdiction)

        # Extract relevant sections
        relevant_content = self._extract_relevant_sections(kb_content, topic)

        # For deep research, supplement with web search
        web_results = None
        if depth == "deep":
            try:
                web_results = await self._web_search_legal(topic, jurisdiction)
            except Exception as e:
                logger.warning(f"LegalResearchSkill: web search failed: {e}")

        # Extract key statutes from KB content
        key_statutes = self._extract_statutes(kb_content, topic)

        summary = relevant_content or (
            f"Legal research for '{topic}' in {jurisdiction.replace('_', ' ').title()} "
            f"is not yet available in the knowledge base. "
            f"Please consult official government resources or a qualified legal professional."
        )

        return {
            "success": True,
            "jurisdiction": jurisdiction,
            "topic": topic,
            "summary": summary[:3000],
            "key_statutes": key_statutes,
            "source": f"knowledge/legal/jurisdictions/{jurisdiction}.md",
            "web_results": web_results,
        }

    async def lookup_regulatory_requirements(
        self,
        activity: str,
        jurisdiction: str,
        entity_type: Optional[str] = None,
    ) -> dict:
        """
        Look up regulatory requirements for a business activity in a jurisdiction.

        Args:
            activity: The business activity (e.g., "payment processing", "fund management").
            jurisdiction: Target jurisdiction key.
            entity_type: Optional entity type (e.g., "private limited company", "branch").

        Returns:
            {
                "success": bool,
                "jurisdiction": str,
                "activity": str,
                "entity_type": str,
                "requirements": list[dict],
                "regulators": list[str],
                "notes": str,
            }
        """
        jurisdiction = self._normalise_jurisdiction(jurisdiction)
        kb_content = self._load_jurisdiction_kb(jurisdiction)

        # Look for regulatory sections
        relevant = self._extract_relevant_sections(kb_content, activity)
        regulators = self._extract_regulators(kb_content, jurisdiction)

        requirements = []
        if relevant:
            # Parse numbered requirements from KB content
            import re
            req_pattern = re.compile(r"\d+\.\s+(.+)", re.MULTILINE)
            matches = req_pattern.findall(relevant)
            requirements = [{"requirement": m.strip(), "source": "knowledge base"} for m in matches[:10]]

        if not requirements:
            requirements = [
                {
                    "requirement": (
                        f"Regulatory requirements for '{activity}' in "
                        f"{jurisdiction.replace('_', ' ').title()} require professional legal review."
                    ),
                    "source": "advisory",
                }
            ]

        return {
            "success": True,
            "jurisdiction": jurisdiction,
            "activity": activity,
            "entity_type": entity_type or "Not specified",
            "requirements": requirements,
            "regulators": regulators,
            "notes": (
                f"Requirements are based on knowledge base as of training date. "
                f"Regulations change — always verify with the relevant regulator."
            ),
        }

    async def check_compliance_requirements(
        self,
        company_type: str,
        jurisdictions: list,
        industry: Optional[str] = None,
        annual_revenue_usd: Optional[float] = None,
    ) -> dict:
        """
        Check compliance requirements across multiple jurisdictions.

        Args:
            company_type: Type of company (e.g., "private limited", "fund").
            jurisdictions: List of jurisdiction keys to check.
            industry: Industry sector (e.g., "fintech", "manufacturing").
            annual_revenue_usd: Annual revenue for threshold-based requirements.

        Returns:
            {
                "success": bool,
                "company_type": str,
                "jurisdictions_checked": list[str],
                "compliance_matrix": dict,
                "summary": str,
            }
        """
        compliance_matrix = {}

        for jur in jurisdictions:
            normalised = self._normalise_jurisdiction(jur)
            kb_content = self._load_jurisdiction_kb(normalised)

            # Extract key compliance areas
            areas = {}

            # Annual filing
            filing_section = self._extract_relevant_sections(kb_content, "annual filing")
            areas["annual_filing"] = bool(filing_section)

            # Tax registration
            tax_section = self._extract_relevant_sections(kb_content, "tax")
            areas["tax_registration"] = bool(tax_section)

            # Employment compliance
            emp_section = self._extract_relevant_sections(kb_content, "employment")
            areas["employment_compliance"] = bool(emp_section)

            # Data protection
            dp_section = self._extract_relevant_sections(kb_content, "data protection")
            areas["data_protection"] = bool(dp_section)

            # Industry-specific
            if industry:
                ind_section = self._extract_relevant_sections(kb_content, industry)
                areas[f"{industry}_specific"] = bool(ind_section)

            # Revenue-based thresholds
            if annual_revenue_usd and annual_revenue_usd > 1_000_000:
                areas["audit_required"] = True  # Most jurisdictions require audit above threshold

            compliance_matrix[normalised] = {
                "jurisdiction_name": normalised.replace("_", " ").title(),
                "compliance_areas": areas,
                "kb_available": bool(kb_content),
                "notes": (
                    f"Review {'available' if kb_content else 'not available'} in knowledge base. "
                    f"Always verify with qualified local counsel."
                ),
            }

        return {
            "success": True,
            "company_type": company_type,
            "jurisdictions_checked": [self._normalise_jurisdiction(j) for j in jurisdictions],
            "compliance_matrix": compliance_matrix,
            "summary": (
                f"Compliance check completed for {len(jurisdictions)} jurisdiction(s). "
                f"Key areas reviewed: annual filing, tax, employment, data protection"
                + (f", {industry}" if industry else "")
                + ". Engage local counsel for definitive compliance advice."
            ),
        }

    # ── Private helpers ────────────────────────────────────────────────────────

    def _normalise_jurisdiction(self, jurisdiction: str) -> str:
        """Normalise jurisdiction string to KB folder key."""
        jur_lower = jurisdiction.lower().strip().replace(" ", "_")
        aliases = {
            "sg": "singapore",
            "hk": "hong_kong",
            "hongkong": "hong_kong",
            "my": "malaysia",
            "uae": "uae",
            "dubai": "uae",
            "abu_dhabi": "uae",
            "ksa": "saudi_arabia",
            "saudi": "saudi_arabia",
            "qa": "qatar",
            "cayman": "cayman_islands",
        }
        return aliases.get(jur_lower, jur_lower if jur_lower in _SUPPORTED_JURISDICTIONS else "general")

    def _load_jurisdiction_kb(self, jurisdiction: str) -> str:
        """Load jurisdiction knowledge base file. Returns empty string on failure."""
        kb_file = _KNOWLEDGE_BASE_PATH / "jurisdictions" / f"{jurisdiction}.md"
        try:
            if kb_file.exists():
                return kb_file.read_text(encoding="utf-8")
        except Exception as e:
            logger.warning(f"LegalResearchSkill: could not load KB {kb_file}: {e}")
        return ""

    def _extract_relevant_sections(self, content: str, topic: str) -> str:
        """Extract sections from KB content relevant to the topic."""
        if not content or not topic:
            return ""

        topic_lower = topic.lower()
        lines = content.split("\n")
        relevant_lines = []
        in_relevant_section = False

        for line in lines:
            line_lower = line.lower()
            # Section headers that match the topic
            if line.startswith("#") and topic_lower in line_lower:
                in_relevant_section = True
            elif line.startswith("#") and not topic_lower in line_lower:
                in_relevant_section = False

            if in_relevant_section:
                relevant_lines.append(line)
            elif topic_lower in line_lower:
                relevant_lines.append(line)

        return "\n".join(relevant_lines[:50])

    def _extract_statutes(self, content: str, topic: str) -> list:
        """Extract relevant statute/act names from KB content."""
        import re
        if not content:
            return []
        # Pattern: "Xxx Act" / "Xxx Ordinance" / "Xxx Law"
        statute_pattern = re.compile(
            r"[A-Z][a-zA-Z\s]+(?:Act|Ordinance|Law|Code|Regulation|Order)\s*(?:\d{4})?",
            re.MULTILINE,
        )
        matches = statute_pattern.findall(content)
        statutes = list(set(m.strip() for m in matches if len(m.strip()) > 5))
        return statutes[:10]

    def _extract_regulators(self, content: str, jurisdiction: str) -> list:
        """Extract regulatory body names from KB content."""
        regulators_by_jurisdiction = {
            "singapore": ["ACRA", "MAS", "MOM", "PDPC", "IRAS"],
            "hong_kong": ["CR", "SFC", "HKMA", "Labour Department", "PCPD"],
            "malaysia": ["SSM", "Bank Negara Malaysia", "LHDN", "PDPC Malaysia"],
            "uae": ["DED", "CBUAE", "DFSA", "FSRA", "MOHRE"],
            "saudi_arabia": ["MISA", "CMA", "SAMA", "Ministry of Commerce", "MHRSD"],
            "qatar": ["MOCI", "QCB", "QFC Regulatory Authority"],
            "cayman_islands": ["CIMA", "Registrar of Companies"],
        }
        return regulators_by_jurisdiction.get(jurisdiction, [])

    async def _web_search_legal(self, topic: str, jurisdiction: str) -> list:
        """Perform web search for legal topic (deep research mode)."""
        # Web search is handled by ResearchAgent / LLM web_search tool
        # This skill signals that web search is needed — LegalAgent handles the tool call
        return [
            {
                "query": f"{topic} {jurisdiction.replace('_', ' ')} law regulation",
                "note": "Web search recommended for current regulatory information",
            }
        ]
