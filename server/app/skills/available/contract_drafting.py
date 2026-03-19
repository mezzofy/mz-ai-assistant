"""
ContractDraftingSkill — Draft and customise legal contracts.

Generates business contracts from jurisdiction-specific templates in the
knowledge base. Supports 11 contract types across 8 jurisdictions.

CRITICAL: All Ops class imports (DOCXOps, PDFOps) are INSIDE method bodies
          to follow the lazy import pattern — never at module top.
"""

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger("mezzofy.skills.contract_drafting")

# Knowledge base root — resolved relative to server/
_KNOWLEDGE_BASE_PATH = Path(__file__).parent.parent.parent.parent / "knowledge" / "legal"

_SUPPORTED_CONTRACT_TYPES = [
    "nda",
    "service_agreement",
    "employment_contract",
    "mou",
    "vendor_agreement",
    "consultancy_agreement",
    "ip_assignment",
    "distribution_agreement",
    "loi",
    "shareholders_agreement",
    "exempted_company_mou",
]

_SUPPORTED_JURISDICTIONS = [
    "singapore",
    "hong_kong",
    "malaysia",
    "uae",
    "saudi_arabia",
    "qatar",
    "cayman_islands",
    "general",
]


class ContractDraftingSkill:
    """
    Skill for drafting and customising legal contracts.

    Provides:
      - draft_contract: full contract generation from template
      - customise_clauses: apply modifications to existing draft
      - get_contract_template: load KB template for type + jurisdiction
    """

    async def draft_contract(
        self,
        contract_type: str,
        party_a: str,
        party_b: str,
        commercial_terms: Optional[dict] = None,
        governing_law: Optional[str] = None,
        special_clauses: Optional[list] = None,
        output_format: str = "docx",
    ) -> dict:
        """
        Generate a complete legal contract from a template.

        Args:
            contract_type: One of the supported contract types (e.g., "nda", "mou").
            party_a: Name of the first contracting party.
            party_b: Name of the second contracting party.
            commercial_terms: Dict of commercial terms (e.g., {"fee": "SGD 10,000/month"}).
            governing_law: Jurisdiction governing the contract (e.g., "Singapore").
            special_clauses: List of additional clauses to include.
            output_format: "docx" or "pdf".

        Returns:
            {
                "success": bool,
                "draft_text": str,
                "contract_type": str,
                "jurisdiction": str,
                "placeholders": list[str],
                "error": str | None,
            }
        """
        if contract_type.lower() not in _SUPPORTED_CONTRACT_TYPES:
            return {
                "success": False,
                "draft_text": "",
                "error": f"Unsupported contract type: {contract_type}. "
                         f"Supported: {', '.join(_SUPPORTED_CONTRACT_TYPES)}",
            }

        # Determine jurisdiction key from governing_law string
        jurisdiction = self._resolve_jurisdiction(governing_law or "")

        # Load template
        template_text = await self.get_contract_template(contract_type, jurisdiction)
        if not template_text.get("success"):
            # Fall back to general template
            template_text = await self.get_contract_template(contract_type, "general")

        base_template = template_text.get("template_text", "")

        # Apply party name substitutions
        draft = base_template
        draft = draft.replace("[PARTY A]", party_a)
        draft = draft.replace("[PARTY_A]", party_a)
        draft = draft.replace("[COMPANY NAME]", party_a)
        draft = draft.replace("[PARTY B]", party_b)
        draft = draft.replace("[PARTY_B]", party_b)
        draft = draft.replace("[COUNTERPARTY NAME]", party_b)

        # Apply commercial terms
        if commercial_terms:
            for key, value in commercial_terms.items():
                placeholder = f"[{key.upper()}]"
                draft = draft.replace(placeholder, str(value))

        # Apply governing law
        if governing_law:
            draft = draft.replace("[GOVERNING LAW]", governing_law)
            draft = draft.replace("[JURISDICTION]", governing_law)

        # Append special clauses
        if special_clauses:
            clauses_text = "\n\n".join(f"## {i+1}. {clause}" for i, clause in enumerate(special_clauses))
            draft += f"\n\n## ADDITIONAL CLAUSES\n\n{clauses_text}"

        # Identify remaining placeholders
        import re
        placeholders = re.findall(r"\[[A-Z_\s]+\]", draft)
        placeholders = list(set(placeholders))

        return {
            "success": True,
            "draft_text": draft,
            "contract_type": contract_type,
            "jurisdiction": jurisdiction,
            "placeholders": placeholders,
            "error": None,
        }

    async def customise_clauses(
        self,
        base_contract_text: str,
        modifications: list,
        governing_law: Optional[str] = None,
    ) -> dict:
        """
        Apply specific modifications to an existing contract draft.

        Args:
            base_contract_text: The existing contract text to modify.
            modifications: List of modifications, each as:
                           {"clause": str, "action": "replace|add|remove", "new_text": str}
            governing_law: Optional override for governing law clause.

        Returns:
            {
                "success": bool,
                "modified_text": str,
                "changes_applied": list[str],
                "error": str | None,
            }
        """
        if not base_contract_text:
            return {
                "success": False,
                "modified_text": "",
                "changes_applied": [],
                "error": "base_contract_text is required",
            }

        modified = base_contract_text
        changes_applied = []

        for mod in modifications:
            action = mod.get("action", "").lower()
            clause = mod.get("clause", "")
            new_text = mod.get("new_text", "")

            if action == "replace" and clause and new_text:
                if clause in modified:
                    modified = modified.replace(clause, new_text, 1)
                    changes_applied.append(f"Replaced clause: {clause[:50]}...")
                else:
                    changes_applied.append(f"WARNING: Clause not found for replacement: {clause[:50]}...")

            elif action == "add" and new_text:
                modified = modified + f"\n\n{new_text}"
                changes_applied.append(f"Added clause: {new_text[:50]}...")

            elif action == "remove" and clause:
                if clause in modified:
                    modified = modified.replace(clause, "", 1)
                    changes_applied.append(f"Removed clause: {clause[:50]}...")
                else:
                    changes_applied.append(f"WARNING: Clause not found for removal: {clause[:50]}...")

        # Apply governing law override
        if governing_law:
            import re
            modified = re.sub(
                r"governed by.+?(?:laws?|law)\s+of\s+\S+",
                f"governed by the laws of {governing_law}",
                modified,
                flags=re.IGNORECASE,
            )
            changes_applied.append(f"Updated governing law to: {governing_law}")

        return {
            "success": True,
            "modified_text": modified,
            "changes_applied": changes_applied,
            "error": None,
        }

    async def get_contract_template(
        self,
        contract_type: str,
        jurisdiction: str,
    ) -> dict:
        """
        Load a contract template from the knowledge base.

        Tries jurisdiction-specific first, then falls back to general.

        Args:
            contract_type: Template file name without extension (e.g., "nda").
            jurisdiction: Jurisdiction folder name (e.g., "singapore").

        Returns:
            {
                "success": bool,
                "template_text": str,
                "source_path": str,
                "jurisdiction": str,
                "contract_type": str,
            }
        """
        for jur in (jurisdiction, "general"):
            template_path = _KNOWLEDGE_BASE_PATH / "templates" / jur / f"{contract_type}.md"
            try:
                if template_path.exists():
                    template_text = template_path.read_text(encoding="utf-8")
                    return {
                        "success": True,
                        "template_text": template_text,
                        "source_path": str(template_path),
                        "jurisdiction": jur,
                        "contract_type": contract_type,
                    }
            except Exception as e:
                logger.warning(f"ContractDraftingSkill: could not read template {template_path}: {e}")

        # No template found — return a minimal placeholder
        minimal_template = self._get_minimal_template(contract_type, jurisdiction)
        return {
            "success": True,
            "template_text": minimal_template,
            "source_path": "generated",
            "jurisdiction": jurisdiction,
            "contract_type": contract_type,
        }

    # ── Private helpers ────────────────────────────────────────────────────────

    def _resolve_jurisdiction(self, governing_law: str) -> str:
        """Map a governing law string to a jurisdiction folder name."""
        law_lower = governing_law.lower()
        jurisdiction_map = {
            "singapore": "singapore",
            "hong kong": "hong_kong",
            "malaysia": "malaysia",
            "uae": "uae",
            "united arab emirates": "uae",
            "difc": "uae",
            "adgm": "uae",
            "saudi arabia": "saudi_arabia",
            "ksa": "saudi_arabia",
            "qatar": "qatar",
            "cayman": "cayman_islands",
            "cayman islands": "cayman_islands",
            "england": "general",
            "english law": "general",
        }
        for keyword, jur in jurisdiction_map.items():
            if keyword in law_lower:
                return jur
        return "general"

    def _get_minimal_template(self, contract_type: str, jurisdiction: str) -> str:
        """Return a minimal contract skeleton when no template file is found."""
        return f"""# {contract_type.replace('_', ' ').title()}

**PARTIES:**
This {contract_type.replace('_', ' ')} ("Agreement") is entered into as of [EFFECTIVE DATE]

**BETWEEN:** [PARTY A] (hereinafter referred to as "Party A")

**AND:** [PARTY B] (hereinafter referred to as "Party B")

## 1. DEFINITIONS
[DEFINITIONS CLAUSE]

## 2. SCOPE AND OBLIGATIONS
[OBLIGATIONS CLAUSE]

## 3. TERM AND TERMINATION
This Agreement commences on [EFFECTIVE DATE] and continues until [END DATE] or until terminated in accordance with this Agreement.

## 4. CONFIDENTIALITY
[CONFIDENTIALITY CLAUSE]

## 5. LIMITATION OF LIABILITY
[LIABILITY CLAUSE]

## 6. GOVERNING LAW AND JURISDICTION
This Agreement is governed by the laws of [GOVERNING LAW].

## 7. DISPUTE RESOLUTION
[DISPUTE RESOLUTION CLAUSE]

## 8. ENTIRE AGREEMENT
This Agreement constitutes the entire agreement between the parties.

**SIGNED:** [SIGNATURE BLOCK]
"""
