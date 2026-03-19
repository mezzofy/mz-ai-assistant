"""
DocumentReviewSkill — Extract and analyse legal documents.

Provides tools for text extraction from PDF and DOCX legal documents,
document type classification, party detection, and governing law detection.

CRITICAL: All Ops class imports (PDFOps, DOCXOps) are INSIDE method bodies
          to follow the lazy import pattern — never at module top.
"""

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger("mezzofy.skills.document_review")

# Constraints
MAX_FILE_SIZE_MB = 50
MAX_PAGES = 200

# Supported legal document types for classification
_DOCUMENT_TYPES = [
    "Non-Disclosure Agreement (NDA)",
    "Service Agreement",
    "Employment Contract",
    "Memorandum of Understanding (MOU)",
    "Vendor Agreement",
    "Consultancy Agreement",
    "IP Assignment Agreement",
    "Distribution Agreement",
    "Letter of Intent (LOI)",
    "Shareholders Agreement",
    "Term Sheet",
    "Software Licence Agreement",
    "Lease Agreement",
    "Settlement Agreement",
    "Partnership Agreement",
]


class DocumentReviewSkill:
    """
    Skill for extracting and analysing legal documents.

    Provides:
      - extract_legal_document: full text extraction from PDF / DOCX
      - identify_document_type: LLM-powered classification
      - detect_parties: contracting party extraction
      - detect_governing_law: governing law and jurisdiction detection
    """

    async def extract_legal_document(
        self,
        file_path: str,
        file_type: str = "auto",
    ) -> dict:
        """
        Extract text from a legal document file (PDF or DOCX).

        Args:
            file_path: Absolute path to the file.
            file_type: "pdf", "docx", or "auto" (infer from extension).

        Returns:
            {
                "success": bool,
                "text": str,
                "page_count": int,
                "file_type": str,
                "truncated": bool,
                "error": str | None,
            }
        """
        path = Path(file_path)

        # Validate file exists
        if not path.exists():
            return {"success": False, "text": "", "error": f"File not found: {file_path}"}

        # Check file size
        size_mb = path.stat().st_size / (1024 * 1024)
        if size_mb > MAX_FILE_SIZE_MB:
            return {
                "success": False,
                "text": "",
                "error": f"File size {size_mb:.1f}MB exceeds {MAX_FILE_SIZE_MB}MB limit",
            }

        # Detect file type
        if file_type == "auto":
            ext = path.suffix.lower()
            if ext == ".pdf":
                file_type = "pdf"
            elif ext in (".docx", ".doc"):
                file_type = "docx"
            else:
                return {
                    "success": False,
                    "text": "",
                    "error": f"Unsupported file extension: {ext}. Supported: .pdf, .docx",
                }

        try:
            if file_type == "pdf":
                return await self._extract_pdf(path)
            elif file_type == "docx":
                return await self._extract_docx(path)
            else:
                return {
                    "success": False,
                    "text": "",
                    "error": f"Unsupported file_type: {file_type}",
                }
        except Exception as e:
            logger.error(f"DocumentReviewSkill.extract_legal_document failed: {e}", exc_info=True)
            return {"success": False, "text": "", "error": str(e)}

    async def identify_document_type(self, document_text: str) -> dict:
        """
        Classify the legal document type using keyword analysis.

        Args:
            document_text: Extracted text from the document.

        Returns:
            {
                "success": bool,
                "document_type": str,
                "confidence": str,  # "high" / "medium" / "low"
                "indicators": list[str],
            }
        """
        if not document_text:
            return {
                "success": False,
                "document_type": "Unknown",
                "confidence": "low",
                "indicators": [],
            }

        text_lower = document_text.lower()

        # Pattern-based classification
        type_patterns = {
            "Non-Disclosure Agreement (NDA)": [
                "non-disclosure", "nda", "confidential information", "shall not disclose",
                "confidentiality obligations",
            ],
            "Service Agreement": [
                "services agreement", "service agreement", "scope of services",
                "statement of work", "deliverables",
            ],
            "Employment Contract": [
                "employment agreement", "employment contract", "employee", "employer",
                "salary", "remuneration", "probationary period",
            ],
            "Memorandum of Understanding (MOU)": [
                "memorandum of understanding", "mou", "heads of agreement",
                "non-binding", "letter of intent",
            ],
            "Shareholders Agreement": [
                "shareholders agreement", "shareholder agreement", "share transfer",
                "drag-along", "tag-along", "pre-emption",
            ],
            "Vendor Agreement": [
                "vendor agreement", "supplier agreement", "purchase order",
                "vendor", "goods and services",
            ],
        }

        best_match = "Unknown"
        best_score = 0
        matched_indicators = []

        for doc_type, patterns in type_patterns.items():
            matches = [p for p in patterns if p in text_lower]
            if len(matches) > best_score:
                best_score = len(matches)
                best_match = doc_type
                matched_indicators = matches

        confidence = "high" if best_score >= 3 else "medium" if best_score >= 1 else "low"

        return {
            "success": True,
            "document_type": best_match,
            "confidence": confidence,
            "indicators": matched_indicators[:5],
        }

    async def detect_parties(self, document_text: str) -> dict:
        """
        Extract the names and roles of contracting parties from document text.

        Looks for patterns like "between [Party A] and [Party B]",
        "PARTY A:", "Party 1:", registration numbers, etc.

        Args:
            document_text: Extracted text from the document.

        Returns:
            {
                "success": bool,
                "parties": list[dict],  # [{"name": str, "role": str, "description": str}]
                "party_count": int,
            }
        """
        if not document_text:
            return {"success": False, "parties": [], "party_count": 0}

        import re

        parties = []
        text = document_text[:3000]  # Check first 3000 chars (preamble)

        # Pattern: "between [Name] ... and [Name]"
        between_pattern = re.compile(
            r"between\s+(.+?)\s+(?:\(hereinafter|,?\s*(?:the\s+)?[\"']?[A-Z][a-z]+[\"']?)?.*?and\s+(.+?)(?:\(hereinafter|,|\.|$)",
            re.IGNORECASE | re.DOTALL,
        )
        match = between_pattern.search(text)
        if match:
            parties.append({"name": match.group(1).strip()[:80], "role": "Party A", "description": "First contracting party"})
            parties.append({"name": match.group(2).strip()[:80], "role": "Party B", "description": "Second contracting party"})

        # Pattern: "COMPANY: [Name]" or "Employer:" / "Employee:" / "Client:"
        role_patterns = [
            (re.compile(r"(?:employer|company|client|licensor|disclosing party)[:\s]+([A-Z][^\n,]+)", re.IGNORECASE), "Principal"),
            (re.compile(r"(?:employee|contractor|vendor|licensee|receiving party)[:\s]+([A-Z][^\n,]+)", re.IGNORECASE), "Counter-party"),
        ]
        for pattern, role in role_patterns:
            m = pattern.search(text)
            if m and not parties:  # Only use if "between" pattern didn't work
                parties.append({"name": m.group(1).strip()[:80], "role": role, "description": ""})

        if not parties:
            return {
                "success": True,
                "parties": [{"name": "Could not automatically detect parties", "role": "Unknown", "description": "Manual review required"}],
                "party_count": 0,
            }

        return {
            "success": True,
            "parties": parties,
            "party_count": len(parties),
        }

    async def detect_governing_law(self, document_text: str) -> dict:
        """
        Identify the governing law and dispute resolution jurisdiction.

        Args:
            document_text: Extracted text from the document.

        Returns:
            {
                "success": bool,
                "governing_law": str,
                "dispute_resolution": str,
                "arbitration_centre": str | None,
                "clause_text": str,
            }
        """
        if not document_text:
            return {
                "success": False,
                "governing_law": "Not detected",
                "dispute_resolution": "Not detected",
                "arbitration_centre": None,
                "clause_text": "",
            }

        import re

        # Search in last 30% of document (governing law is typically at the end)
        search_text = document_text[max(0, len(document_text) - 3000):]
        text_lower = search_text.lower()

        governing_law = "Not specified"
        dispute_resolution = "Not specified"
        arbitration_centre = None
        clause_text = ""

        # Governing law patterns
        law_map = {
            "Singapore": ["laws of singapore", "singapore law", "republic of singapore"],
            "Hong Kong": ["laws of hong kong", "hong kong law", "hksar"],
            "Malaysia": ["laws of malaysia", "malaysian law"],
            "UAE / DIFC": ["laws of the uae", "difc law", "adgm law", "united arab emirates law"],
            "England and Wales": ["laws of england", "english law", "england and wales"],
            "Cayman Islands": ["laws of the cayman islands", "cayman islands law"],
        }

        for jurisdiction, patterns in law_map.items():
            if any(p in text_lower for p in patterns):
                governing_law = jurisdiction
                break

        # Dispute resolution
        if "arbitration" in text_lower:
            dispute_resolution = "Arbitration"
            arb_centres = {
                "SIAC": ["siac", "singapore international arbitration"],
                "HKIAC": ["hkiac", "hong kong international arbitration"],
                "ICC": ["icc", "international chamber of commerce"],
                "DIAC": ["diac", "dubai international arbitration"],
                "LCIA": ["lcia", "london court of international arbitration"],
            }
            for centre, patterns in arb_centres.items():
                if any(p in text_lower for p in patterns):
                    arbitration_centre = centre
                    break
        elif "courts" in text_lower or "litigation" in text_lower:
            dispute_resolution = "Court Litigation"

        # Try to extract the actual clause text
        governing_law_re = re.compile(
            r"governing law[\s\S]{0,300}",
            re.IGNORECASE,
        )
        m = governing_law_re.search(search_text)
        if m:
            clause_text = m.group(0)[:200].strip()

        return {
            "success": True,
            "governing_law": governing_law,
            "dispute_resolution": dispute_resolution,
            "arbitration_centre": arbitration_centre,
            "clause_text": clause_text,
        }

    # ── Private helpers ────────────────────────────────────────────────────────

    async def _extract_pdf(self, path: Path) -> dict:
        """Extract text from a PDF using PDFOps (lazy import)."""
        # CRITICAL: import inside method body — never at module top
        from app.tools.document.pdf_ops import PDFOps

        try:
            config = {}
            pdf_ops = PDFOps(config)
            result = await pdf_ops.execute("read_pdf", file_path=str(path))

            text = result.get("content", "") or result.get("text", "")
            page_count = result.get("page_count", 0)
            truncated = False

            # Truncate if exceeds page limit (rough estimate: 500 chars/page)
            max_chars = MAX_PAGES * 500
            if len(text) > max_chars:
                text = text[:max_chars]
                truncated = True
                logger.warning(
                    f"DocumentReviewSkill: PDF truncated to {MAX_PAGES} pages equivalent"
                )

            return {
                "success": True,
                "text": text,
                "page_count": page_count,
                "file_type": "pdf",
                "truncated": truncated,
                "error": None,
            }
        except Exception as e:
            logger.error(f"DocumentReviewSkill._extract_pdf: {e}")
            return {"success": False, "text": "", "page_count": 0, "file_type": "pdf",
                    "truncated": False, "error": str(e)}

    async def _extract_docx(self, path: Path) -> dict:
        """Extract text from a DOCX using DOCXOps (lazy import)."""
        # CRITICAL: import inside method body — never at module top
        from app.tools.document.docx_ops import DOCXOps

        try:
            config = {}
            docx_ops = DOCXOps(config)
            result = await docx_ops.execute("read_docx", file_path=str(path))

            text = result.get("content", "") or result.get("text", "")
            truncated = False

            max_chars = MAX_PAGES * 500
            if len(text) > max_chars:
                text = text[:max_chars]
                truncated = True
                logger.warning(
                    f"DocumentReviewSkill: DOCX truncated to {MAX_PAGES} pages equivalent"
                )

            return {
                "success": True,
                "text": text,
                "page_count": 0,  # DOCX doesn't have a reliable page count
                "file_type": "docx",
                "truncated": truncated,
                "error": None,
            }
        except Exception as e:
            logger.error(f"DocumentReviewSkill._extract_docx: {e}")
            return {"success": False, "text": "", "page_count": 0, "file_type": "docx",
                    "truncated": False, "error": str(e)}
