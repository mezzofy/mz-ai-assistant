"""
JurisdictionAdvisorySkill — Jurisdiction-specific legal advisory.

Provides business law advisory across 7 jurisdictions: Singapore, Hong Kong,
Malaysia, UAE, Saudi Arabia, Qatar, and Cayman Islands.

Uses knowledge base files under server/knowledge/legal/jurisdictions/ as primary
context for all advisory responses.
"""

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger("mezzofy.skills.jurisdiction_advisory")

# Knowledge base root
_KNOWLEDGE_BASE_PATH = Path(__file__).parent.parent.parent.parent / "knowledge" / "legal"

_JURISDICTION_DISPLAY_NAMES = {
    "singapore": "Singapore",
    "hong_kong": "Hong Kong SAR",
    "malaysia": "Malaysia",
    "uae": "United Arab Emirates (UAE)",
    "saudi_arabia": "Kingdom of Saudi Arabia",
    "qatar": "State of Qatar",
    "cayman_islands": "Cayman Islands",
}

_JURISDICTION_STRENGTHS = {
    "singapore": [
        "Asia's premier financial hub and regional HQ location",
        "Strong rule of law and independent judiciary (SIAC)",
        "Extensive double-tax treaty network (90+ countries)",
        "World-class IP protection regime (IPOS)",
        "Pro-business regulatory environment (ACRA, MAS)",
    ],
    "hong_kong": [
        "Gateway to mainland China and Greater Bay Area",
        "Low and simple tax regime (profits tax max 16.5%)",
        "Free capital flows — no restrictions on repatriation",
        "Common law jurisdiction with strong contract enforcement",
        "HKIAC arbitration centre — globally recognised",
    ],
    "malaysia": [
        "Cost-competitive ASEAN manufacturing and services hub",
        "MSC Malaysia status — digital economy incentives",
        "Strong English language and professional services base",
        "AIAC arbitration — established Southeast Asia venue",
        "Corridor development zones (Iskandar, KL, Penang)",
    ],
    "uae": [
        "DIFC and ADGM — common law financial centre enclaves",
        "Zero personal income tax and zero capital gains tax",
        "100% foreign ownership in free zones",
        "Strategic Middle East, Africa, South Asia hub",
        "Efficient company setup (1–3 business days in free zones)",
    ],
    "saudi_arabia": [
        "Largest economy in the Middle East (GDP ~$1.1 trillion)",
        "Vision 2030 — massive privatisation and investment pipeline",
        "NEOM, Red Sea Project, Diriyah — giga-project opportunities",
        "New Regional Headquarters (RHQ) programme with incentives",
        "100% foreign ownership in selected sectors post-reform",
    ],
    "qatar": [
        "Highest per-capita GDP in the world",
        "QFC — common law financial centre with 100% foreign ownership",
        "Post-FIFA 2022 infrastructure buildout and diversification",
        "Gas-based sovereign wealth (Qatar Investment Authority)",
        "Low political risk — stable long-term governance",
    ],
    "cayman_islands": [
        "Zero corporate tax, capital gains tax, withholding tax",
        "Leading global offshore fund domicile",
        "Flexible exempted company and ELP structures",
        "Recognised by institutional investors globally",
        "Cayman court — experienced in complex commercial disputes",
    ],
}


class JurisdictionAdvisorySkill:
    """
    Skill for jurisdiction-specific business legal advisory.

    Provides:
      - get_jurisdiction_overview: load KB file + structured summary
      - compare_jurisdictions: side-by-side comparison of multiple jurisdictions
      - recommend_jurisdiction: recommend best jurisdiction for a business activity
    """

    async def get_jurisdiction_overview(
        self,
        jurisdiction: str,
        topic: Optional[str] = None,
    ) -> dict:
        """
        Get a comprehensive overview of a jurisdiction's legal framework.

        Args:
            jurisdiction: Jurisdiction key (e.g., "singapore", "hong_kong").
            topic: Optional specific topic within the jurisdiction (e.g., "employment law").

        Returns:
            {
                "success": bool,
                "jurisdiction": str,
                "display_name": str,
                "overview": str,
                "key_strengths": list[str],
                "key_statutes": list[str],
                "regulators": list[str],
                "source_available": bool,
            }
        """
        jur_key = self._normalise_jurisdiction(jurisdiction)
        display_name = _JURISDICTION_DISPLAY_NAMES.get(jur_key, jur_key.replace("_", " ").title())

        # Load KB file
        kb_content = self._load_jurisdiction_kb(jur_key)
        source_available = bool(kb_content)

        # Extract topic-specific content if requested
        if topic and kb_content:
            relevant = self._extract_topic_section(kb_content, topic)
            overview = relevant or kb_content[:2000]
        else:
            overview = kb_content[:2500] if kb_content else (
                f"Detailed knowledge base content for {display_name} is being compiled. "
                f"Please consult official government resources or a qualified legal professional."
            )

        strengths = _JURISDICTION_STRENGTHS.get(jur_key, [])
        statutes = self._get_key_statutes(jur_key)
        regulators = self._get_regulators(jur_key)

        return {
            "success": True,
            "jurisdiction": jur_key,
            "display_name": display_name,
            "overview": overview,
            "key_strengths": strengths,
            "key_statutes": statutes,
            "regulators": regulators,
            "source_available": source_available,
        }

    async def compare_jurisdictions(
        self,
        topic: str,
        jurisdictions: list,
    ) -> dict:
        """
        Compare legal and regulatory features across multiple jurisdictions.

        Args:
            topic: The comparison topic (e.g., "company formation", "data protection", "employment").
            jurisdictions: List of jurisdiction keys to compare.

        Returns:
            {
                "success": bool,
                "topic": str,
                "comparison_table": list[dict],
                "recommendation_notes": str,
            }
        """
        if len(jurisdictions) < 2:
            return {
                "success": False,
                "topic": topic,
                "comparison_table": [],
                "recommendation_notes": "At least 2 jurisdictions required for comparison.",
            }

        comparison_rows = []

        for jur in jurisdictions:
            jur_key = self._normalise_jurisdiction(jur)
            kb_content = self._load_jurisdiction_kb(jur_key)
            display_name = _JURISDICTION_DISPLAY_NAMES.get(jur_key, jur_key.replace("_", " ").title())

            # Extract topic-relevant content
            relevant_content = self._extract_topic_section(kb_content, topic)

            row = {
                "jurisdiction": jur_key,
                "display_name": display_name,
                "topic_summary": relevant_content[:500] if relevant_content else (
                    f"Content for {topic} in {display_name} not in knowledge base — recommend professional advice."
                ),
                "strengths": _JURISDICTION_STRENGTHS.get(jur_key, [])[:3],
                "key_statutes": self._get_key_statutes(jur_key)[:3],
                "regulators": self._get_regulators(jur_key)[:3],
                "kb_available": bool(kb_content),
            }
            comparison_rows.append(row)

        recommendation_notes = (
            f"Comparison of {len(jurisdictions)} jurisdictions on '{topic}'. "
            f"This comparison is based on the knowledge base and general legal principles. "
            f"Specific requirements may vary based on business structure and activity. "
            f"Engage qualified legal counsel in each jurisdiction before making decisions."
        )

        return {
            "success": True,
            "topic": topic,
            "comparison_table": comparison_rows,
            "recommendation_notes": recommendation_notes,
        }

    async def recommend_jurisdiction(
        self,
        business_activity: str,
        considerations: Optional[list] = None,
        company_size: Optional[str] = None,
    ) -> dict:
        """
        Recommend the most suitable jurisdiction for a business activity.

        Args:
            business_activity: Description of the intended business (e.g., "fund management", "e-commerce").
            considerations: List of priority factors (e.g., ["tax", "speed of setup", "IP protection"]).
            company_size: "startup" | "sme" | "enterprise".

        Returns:
            {
                "success": bool,
                "business_activity": str,
                "primary_recommendation": str,
                "alternative_recommendations": list[str],
                "rationale": str,
                "comparison_summary": list[dict],
            }
        """
        activity_lower = business_activity.lower()
        considerations = considerations or []

        # Rule-based recommendation logic
        recommendations = []

        # Fund management / VC / PE
        if any(kw in activity_lower for kw in ["fund", "venture", "private equity", "hedge"]):
            recommendations = [
                ("cayman_islands", "Standard domicile for offshore funds; zero tax, institutional recognition"),
                ("singapore", "Asia-based fund management; MAS-regulated; strong LP base"),
                ("hong_kong", "China-proximate fund management; SFC-regulated"),
            ]

        # Financial services / fintech
        elif any(kw in activity_lower for kw in ["fintech", "payment", "banking", "insurance", "crypto"]):
            recommendations = [
                ("singapore", "MAS licensing; regulatory sandbox; Asia's fintech hub"),
                ("uae", "DIFC/ADGM regulatory frameworks; MENA-facing operations"),
                ("hong_kong", "SFC/HKMA licensing; Greater China fintech access"),
            ]

        # Technology / software / SaaS
        elif any(kw in activity_lower for kw in ["tech", "software", "saas", "app", "digital", "ai"]):
            recommendations = [
                ("singapore", "Smart Nation ecosystem; IPB tax exemptions; talent availability"),
                ("hong_kong", "Low tax; R&D deductions; Greater Bay Area access"),
                ("malaysia", "MSC status incentives; lower cost base; skilled IT workforce"),
            ]

        # Manufacturing / trading
        elif any(kw in activity_lower for kw in ["manufactur", "trading", "export", "import", "supply chain"]):
            recommendations = [
                ("malaysia", "Industrial zone incentives; ASEAN manufacturing hub"),
                ("singapore", "Major global trading hub; extensive FTA network"),
                ("uae", "Jebel Ali Free Zone; transshipment hub for MENA/Africa"),
            ]

        # Holding company / HQ
        elif any(kw in activity_lower for kw in ["holding", "headquarter", "hq", "regional"]):
            recommendations = [
                ("singapore", "Asia's premier regional HQ; extensive tax treaty network"),
                ("hong_kong", "China-proximate holding; low dividends withholding tax"),
                ("cayman_islands", "Offshore holding; zero tax; fund structuring vehicle"),
            ]

        # Middle East / GCC focus
        elif any(kw in activity_lower for kw in ["middle east", "gcc", "gulf", "mena", "saudi", "qatar"]):
            recommendations = [
                ("uae", "DIFC/ADGM hub; free zone 100% ownership; MENA gateway"),
                ("saudi_arabia", "Vision 2030 opportunities; RHQ programme; largest GCC economy"),
                ("qatar", "QFC; stable economy; post-FIFA growth"),
            ]

        # Default: Singapore as primary recommendation
        else:
            recommendations = [
                ("singapore", "Globally ranked #1 for ease of doing business in Asia; strong rule of law"),
                ("hong_kong", "Low tax regime; free capital flows; China access"),
                ("uae", "Zero personal tax; fast setup; MENA hub"),
            ]

        primary = recommendations[0] if recommendations else ("singapore", "Default recommendation")
        alternatives = [r[0] for r in recommendations[1:]]

        # Build comparison summary
        comparison_summary = []
        for jur_key, rationale in recommendations:
            comparison_summary.append({
                "jurisdiction": jur_key,
                "display_name": _JURISDICTION_DISPLAY_NAMES.get(jur_key, jur_key),
                "rationale": rationale,
                "top_strengths": _JURISDICTION_STRENGTHS.get(jur_key, [])[:2],
            })

        full_rationale = (
            f"For '{business_activity}', "
            f"{_JURISDICTION_DISPLAY_NAMES.get(primary[0], primary[0])} is recommended as the "
            f"primary jurisdiction. Reason: {primary[1]}. "
            + (f"Key considerations: {', '.join(considerations)}. " if considerations else "")
            + (f"Company size context: {company_size}. " if company_size else "")
            + "This recommendation is based on general principles. Engage legal counsel for definitive advice."
        )

        return {
            "success": True,
            "business_activity": business_activity,
            "primary_recommendation": primary[0],
            "alternative_recommendations": alternatives,
            "rationale": full_rationale,
            "comparison_summary": comparison_summary,
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
            "ksa": "saudi_arabia",
            "saudi": "saudi_arabia",
            "qa": "qatar",
            "cayman": "cayman_islands",
        }
        valid = set(_JURISDICTION_DISPLAY_NAMES.keys())
        return aliases.get(jur_lower, jur_lower if jur_lower in valid else "singapore")

    def _load_jurisdiction_kb(self, jurisdiction: str) -> str:
        """Load jurisdiction KB file. Returns empty string on failure."""
        kb_file = _KNOWLEDGE_BASE_PATH / "jurisdictions" / f"{jurisdiction}.md"
        try:
            if kb_file.exists():
                return kb_file.read_text(encoding="utf-8")
        except Exception as e:
            logger.warning(f"JurisdictionAdvisorySkill: could not load KB {kb_file}: {e}")
        return ""

    def _extract_topic_section(self, content: str, topic: str) -> str:
        """Extract sections from KB content relevant to the topic."""
        if not content or not topic:
            return ""
        topic_lower = topic.lower()
        lines = content.split("\n")
        relevant = []
        in_section = False
        for line in lines:
            if line.startswith("#") and topic_lower in line.lower():
                in_section = True
            elif line.startswith("## ") and topic_lower not in line.lower():
                in_section = False
            if in_section:
                relevant.append(line)
            elif topic_lower in line.lower():
                relevant.append(line)
        return "\n".join(relevant[:40])

    def _get_key_statutes(self, jurisdiction: str) -> list:
        """Return key business statutes for each jurisdiction."""
        statutes = {
            "singapore": [
                "Companies Act (Cap. 50)",
                "Employment Act (Cap. 91A)",
                "Personal Data Protection Act 2012 (PDPA)",
                "Securities and Futures Act (Cap. 289)",
                "Intellectual Property Acts (Trade Marks, Patents, Copyright)",
            ],
            "hong_kong": [
                "Companies Ordinance (Cap. 622)",
                "Employment Ordinance (Cap. 57)",
                "Personal Data (Privacy) Ordinance (Cap. 486)",
                "Securities and Futures Ordinance (Cap. 571)",
                "Trade Marks Ordinance (Cap. 559)",
            ],
            "malaysia": [
                "Companies Act 2016",
                "Employment Act 1955",
                "Personal Data Protection Act 2010 (PDPA)",
                "Capital Markets and Services Act 2007",
                "Patents Act 1983",
            ],
            "uae": [
                "Federal Law No. 32 of 2021 (Commercial Companies Law)",
                "UAE Labour Law (Federal Law No. 33 of 2021)",
                "DIFC Data Protection Law (DIFC Law No. 5 of 2020)",
                "UAE Personal Data Protection Law (Federal Decree-Law No. 45 of 2021)",
                "DIFC Companies Law (DIFC Law No. 5 of 2018)",
            ],
            "saudi_arabia": [
                "Companies Law (Royal Decree M/3, 1437H)",
                "Labor Law (Royal Decree M/51, 2005)",
                "Investment Law (Royal Decree M/1, 2021)",
                "Personal Data Protection Law (Royal Decree M/19, 2021)",
                "Capital Market Law (Royal Decree M/30, 2003)",
            ],
            "qatar": [
                "Commercial Companies Law (Law No. 11 of 2015)",
                "Labor Law (Law No. 14 of 2004)",
                "Personal Data Privacy Protection Law (Law No. 13 of 2016)",
                "QFC Companies Regulations",
                "Investment Promotion Law (Law No. 1 of 2019)",
            ],
            "cayman_islands": [
                "Companies Act (2023 Revision)",
                "Exempted Limited Partnership Act (2021 Revision)",
                "Limited Liability Companies Act (2021 Revision)",
                "Mutual Funds Act (2021 Revision)",
                "Private Funds Act (2020)",
            ],
        }
        return statutes.get(jurisdiction, [])

    def _get_regulators(self, jurisdiction: str) -> list:
        """Return key regulatory bodies for each jurisdiction."""
        regulators = {
            "singapore": ["ACRA (Corporate)", "MAS (Financial Services)", "MOM (Employment)", "PDPC (Data)", "IPOS (IP)"],
            "hong_kong": ["CR (Corporate)", "SFC (Securities)", "HKMA (Banking)", "Labour Dept (Employment)", "PCPD (Data)"],
            "malaysia": ["SSM (Corporate)", "Bank Negara Malaysia (Financial)", "LHDN (Tax)", "SC Malaysia (Securities)"],
            "uae": ["DED (Mainland)", "DFSA (DIFC)", "FSRA (ADGM)", "CBUAE (Banking)", "MOHRE (Employment)"],
            "saudi_arabia": ["MISA (Investment)", "CMA (Capital Markets)", "SAMA (Banking/Insurance)", "Ministry of Commerce"],
            "qatar": ["MOCI (Commerce)", "QCB (Banking)", "QFC Regulatory Authority", "QFMA (Financial Markets)"],
            "cayman_islands": ["CIMA (Financial Services)", "Registrar of Companies", "Cayman Islands Grand Court"],
        }
        return regulators.get(jurisdiction, [])
