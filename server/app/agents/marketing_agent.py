"""
MarketingAgent — Content generation, playbooks, and campaign support.

Handles: website copy, blog posts, playbooks, social media posts,
newsletters, and campaign briefs using Mezzofy brand guidelines.

Sources:
  - mobile: User request from Marketing department
"""

import logging

from app.agents.base_agent import BaseAgent
from app.llm import llm_manager as llm_mod

logger = logging.getLogger("mezzofy.agents.marketing")

_TRIGGER_KEYWORDS = {
    "content", "website", "blog", "playbook", "campaign", "social media",
    "newsletter", "copy", "brand", "landing page", "post", "write", "draft",
    "marketing", "email blast", "announcement", "feature description",
}


class MarketingAgent(BaseAgent):
    """
    Generates marketing content in Mezzofy brand voice.

    Workflow:
    1. Load content_generation skill
    2. Fetch brand guidelines and product data (via skill)
    3. LLM generates content with brand context
    4. Optionally generate PDF for playbooks
    5. Return content + artifacts
    """

    def can_handle(self, task: dict) -> bool:
        department = task.get("department", "").lower()
        if department == "marketing":
            return True
        message = task.get("message", "").lower()
        return any(kw in message for kw in _TRIGGER_KEYWORDS)

    async def execute(self, task: dict) -> dict:
        message = task.get("message", "")

        try:
            skill = self._load_skill("content_generation")
        except ValueError as e:
            return self._err(str(e))

        # Detect content type from message
        content_type = self._detect_content_type(message)
        tone = self._detect_tone(message)
        length = self._detect_length(message)

        tools_called = ["generate_content"]

        try:
            # Step 1: Generate content
            gen_result = await skill.generate_content(
                content_type=content_type,
                topic=message,
                audience=self._detect_audience(message),
                tone=tone,
                length=length,
            )

            if not gen_result.get("success"):
                return self._err(f"Content generation failed: {gen_result.get('error')}")

            content = gen_result.get("output", "")
            artifacts = []

            # Step 2: For playbooks → generate PDF
            if content_type == "playbook":
                from app.tools.document.pdf_ops import PDFOps
                pdf_ops = PDFOps(self.config)
                pdf_result = await pdf_ops.execute(
                    "create_pdf",
                    content=content,
                    title="Mezzofy Playbook",
                )
                tools_called.append("create_pdf")
                if pdf_result.get("success") and pdf_result.get("output"):
                    artifacts.append({
                        "name": f"mezzofy_playbook_{content_type}.pdf",
                        "path": pdf_result["output"],
                        "type": "pdf",
                    })

            # Step 3: For website copy → save as .md
            if content_type == "website":
                from app.tools.document.docx_ops import DocxOps
                docx_ops = DocxOps(self.config)
                doc_result = await docx_ops.execute(
                    "create_document",
                    content=content,
                    title="Website Copy",
                )
                tools_called.append("create_document")
                if doc_result.get("success") and doc_result.get("output"):
                    artifacts.append({
                        "name": "website_copy.docx",
                        "path": doc_result["output"],
                        "type": "docx",
                    })

            return self._ok(
                content=content,
                artifacts=artifacts,
                tools_called=tools_called,
            )

        except Exception as e:
            logger.error(f"MarketingAgent.execute failed: {e}")
            return self._err(f"Marketing content generation failed: {e}")

    # ── Private helpers ───────────────────────────────────────────────────────

    def _detect_content_type(self, message: str) -> str:
        msg = message.lower()
        if any(w in msg for w in ("playbook", "guide", "manual", "how-to")):
            return "playbook"
        if any(w in msg for w in ("blog", "article", "post")):
            return "blog"
        if any(w in msg for w in ("social", "linkedin post", "facebook", "instagram", "tweet")):
            return "social"
        if any(w in msg for w in ("newsletter", "email blast", "digest")):
            return "newsletter"
        if any(w in msg for w in ("website", "landing page", "homepage", "copy")):
            return "website"
        return "website"

    def _detect_tone(self, message: str) -> str:
        msg = message.lower()
        if any(w in msg for w in ("casual", "friendly", "conversational")):
            return "casual"
        if any(w in msg for w in ("technical", "detailed", "in-depth")):
            return "technical"
        return "professional"

    def _detect_length(self, message: str) -> str:
        msg = message.lower()
        if any(w in msg for w in ("short", "brief", "quick", "concise")):
            return "short"
        if any(w in msg for w in ("long", "detailed", "comprehensive", "full")):
            return "long"
        return "medium"

    def _detect_audience(self, message: str) -> str:
        msg = message.lower()
        if any(w in msg for w in ("customer", "existing", "user")):
            return "customers"
        if any(w in msg for w in ("partner", "reseller", "channel")):
            return "partners"
        return "prospects"
