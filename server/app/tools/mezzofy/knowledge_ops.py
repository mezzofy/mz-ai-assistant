"""
KnowledgeOps — Mezzofy knowledge base search and retrieval tools.

Searches and loads templates, brand guidelines, and playbooks
from the knowledge base directory (config: tools.knowledge_base.directory).

Tools:
    search_knowledge    — Search knowledge base by keyword/topic
    get_template        — Load a specific template (email, PDF, PPTX)
    get_brand_guidelines — Load brand voice, colors, logo specs
    get_playbook        — Load existing playbook content
"""

import json
import logging
import re
from pathlib import Path
from typing import Optional

from app.tools.base_tool import BaseTool

logger = logging.getLogger("mezzofy.tools.knowledge_ops")


class KnowledgeOps(BaseTool):
    """Knowledge base search and retrieval tools."""

    def __init__(self, config: dict):
        super().__init__(config)
        kb_cfg = config.get("tools", {}).get("knowledge_base", {})
        kb_dir = kb_cfg.get("directory", "knowledge")
        # Resolve relative to server root (two levels up from app/tools/mezzofy/)
        server_root = Path(__file__).parent.parent.parent.parent
        self._kb_path = server_root / kb_dir

    # ── Tool Definitions ──────────────────────────────────────────────────────

    def get_tools(self) -> list[dict]:
        return [
            {
                "name": "search_knowledge",
                "description": (
                    "Search the Mezzofy knowledge base by keyword or topic. "
                    "Returns matching documents, sections, and templates. "
                    "Use when you need to find specific information or guidance."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search keyword or topic to find in the knowledge base.",
                        },
                        "category": {
                            "type": "string",
                            "description": (
                                "Optional category to search within "
                                "(e.g., 'templates', 'playbooks', 'brand', 'products', 'faqs')"
                            ),
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of results to return. Default: 10.",
                        },
                    },
                    "required": ["query"],
                },
                "handler": self._search_knowledge,
            },
            {
                "name": "get_template",
                "description": (
                    "Load a specific Mezzofy template by name and type. "
                    "Templates are used for email campaigns, PDF reports, and PPTX presentations."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "template_name": {
                            "type": "string",
                            "description": (
                                "Name of the template to load "
                                "(e.g., 'welcome_email', 'quarterly_report', 'sales_pitch')"
                            ),
                        },
                        "template_type": {
                            "type": "string",
                            "enum": ["email", "pdf", "pptx", "docx", "sms", "any"],
                            "description": "Type of template. Default: any.",
                        },
                    },
                    "required": ["template_name"],
                },
                "handler": self._get_template,
            },
            {
                "name": "get_brand_guidelines",
                "description": (
                    "Load the Mezzofy brand guidelines including voice and tone, "
                    "color palette, logo usage, and typography standards. "
                    "Use when creating branded content."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "section": {
                            "type": "string",
                            "description": (
                                "Specific section to retrieve "
                                "(e.g., 'colors', 'voice', 'logo', 'typography'). "
                                "If omitted, returns full brand guidelines."
                            ),
                        },
                    },
                    "required": [],
                },
                "handler": self._get_brand_guidelines,
            },
            {
                "name": "get_playbook",
                "description": (
                    "Load a specific sales, marketing, or operational playbook. "
                    "Playbooks contain step-by-step processes, scripts, and strategies."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "playbook_name": {
                            "type": "string",
                            "description": (
                                "Name of the playbook to load "
                                "(e.g., 'cold_outreach', 'onboarding', 'churn_prevention', "
                                "'upsell', 'qbr_preparation')"
                            ),
                        },
                        "section": {
                            "type": "string",
                            "description": (
                                "Specific section within the playbook "
                                "(e.g., 'scripts', 'objection_handling', 'checklist'). "
                                "If omitted, returns the full playbook."
                            ),
                        },
                    },
                    "required": ["playbook_name"],
                },
                "handler": self._get_playbook,
            },
        ]

    # ── Handlers ─────────────────────────────────────────────────────────────

    async def _search_knowledge(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 10,
    ) -> dict:
        """Search knowledge base files for the given query."""
        if not self._kb_path.exists():
            return self._ok({
                "query": query,
                "results": [],
                "message": "Knowledge base directory not found.",
            })

        results = []
        query_lower = query.lower()
        query_tokens = query_lower.split()

        # Determine which subdirectories to search
        search_dirs = [self._kb_path]
        if category:
            category_dir = self._kb_path / category
            if category_dir.exists():
                search_dirs = [category_dir]

        for search_dir in search_dirs:
            for file_path in search_dir.rglob("*"):
                if file_path.is_dir():
                    continue
                if file_path.suffix not in (".md", ".json", ".txt", ".yaml"):
                    continue

                try:
                    content = file_path.read_text(encoding="utf-8")
                    content_lower = content.lower()

                    # Score by token matches
                    score = sum(1 for token in query_tokens if token in content_lower)
                    if score == 0:
                        continue

                    # Extract a relevant snippet around the first match
                    snippet = self._extract_snippet(content, query_lower)
                    rel_path = file_path.relative_to(self._kb_path)

                    results.append({
                        "file": str(rel_path),
                        "score": score,
                        "snippet": snippet,
                        "type": file_path.suffix.lstrip("."),
                    })
                except Exception as e:
                    logger.debug(f"Skipping KB file '{file_path}': {e}")

        # Sort by score descending
        results.sort(key=lambda r: r["score"], reverse=True)

        return self._ok({
            "query": query,
            "category": category,
            "total_found": len(results),
            "results": results[:limit],
        })

    async def _get_template(
        self,
        template_name: str,
        template_type: str = "any",
    ) -> dict:
        """Load a specific template by name."""
        templates_dir = self._kb_path / "templates"

        # Build candidate file names
        slug = template_name.lower().replace(" ", "_")
        type_extensions = {
            "email": [".html", ".mjml", ".md", ".txt"],
            "pdf": [".html", ".md"],
            "pptx": [".json", ".md"],
            "docx": [".json", ".md"],
            "sms": [".txt", ".md"],
            "any": [".html", ".mjml", ".json", ".md", ".txt"],
        }
        extensions = type_extensions.get(template_type, type_extensions["any"])

        # Search in templates directory and subdirectories
        search_root = templates_dir if templates_dir.exists() else self._kb_path

        for ext in extensions:
            # Direct match
            candidate = search_root / f"{slug}{ext}"
            if candidate.exists():
                return self._ok({
                    "template_name": template_name,
                    "template_type": template_type,
                    "file": str(candidate.relative_to(self._kb_path)),
                    "content": candidate.read_text(encoding="utf-8"),
                })

            # Search subdirectory matching template_type
            if template_type != "any":
                type_dir = search_root / template_type
                candidate = type_dir / f"{slug}{ext}"
                if candidate.exists():
                    return self._ok({
                        "template_name": template_name,
                        "template_type": template_type,
                        "file": str(candidate.relative_to(self._kb_path)),
                        "content": candidate.read_text(encoding="utf-8"),
                    })

        # Fuzzy search across templates
        if search_root.exists():
            for file_path in search_root.rglob("*"):
                if file_path.is_dir():
                    continue
                if slug in file_path.stem.lower():
                    if template_type == "any" or template_type.lower() in str(file_path).lower():
                        try:
                            return self._ok({
                                "template_name": template_name,
                                "template_type": template_type,
                                "file": str(file_path.relative_to(self._kb_path)),
                                "content": file_path.read_text(encoding="utf-8"),
                            })
                        except Exception as e:
                            logger.warning(f"Failed to read template '{file_path}': {e}")

        return self._err(
            f"Template '{template_name}' (type: {template_type}) not found in knowledge base. "
            f"Searched in: {search_root}"
        )

    async def _get_brand_guidelines(self, section: Optional[str] = None) -> dict:
        """Load brand guidelines, optionally a specific section."""
        # Try known brand guideline file names
        data = (
            self._load_kb_file("brand/guidelines.json")
            or self._load_kb_file("brand/guidelines.md")
            or self._load_kb_file("brand.json")
            or self._load_kb_file("brand.md")
            or self._load_kb_file("brand_guidelines.json")
            or self._load_kb_file("brand_guidelines.md")
        )

        if data is None:
            # Return hardcoded Mezzofy brand defaults so the LLM is never stuck
            return self._ok({
                "source": "defaults",
                "message": "Brand guidelines file not found — returning Mezzofy brand defaults.",
                "colors": {
                    "primary": "#f97316",   # Orange
                    "black": "#000000",
                    "white": "#ffffff",
                },
                "typography": {
                    "primary_font": "Inter",
                    "heading_weight": 700,
                    "body_weight": 400,
                },
                "voice": {
                    "tone": "Professional, confident, friendly",
                    "avoid": ["jargon", "passive voice", "hyperbole"],
                },
                "logo": {
                    "usage": "Use on white or black backgrounds only. Minimum size: 24px height.",
                },
            })

        if section and isinstance(data, dict):
            section_data = data.get(section)
            if section_data is not None:
                return self._ok({"section": section, "brand": section_data})
            # Try case-insensitive search
            matched = next(
                (v for k, v in data.items() if k.lower() == section.lower()),
                None,
            )
            if matched is not None:
                return self._ok({"section": section, "brand": matched})

        return self._ok({"brand_guidelines": data})

    async def _get_playbook(
        self,
        playbook_name: str,
        section: Optional[str] = None,
    ) -> dict:
        """Load a playbook by name, optionally a specific section."""
        slug = playbook_name.lower().replace(" ", "_")
        playbooks_dir = self._kb_path / "playbooks"

        data = (
            self._load_kb_file(f"playbooks/{slug}.json")
            or self._load_kb_file(f"playbooks/{slug}.md")
            or self._load_kb_file(f"{slug}.json")
            or self._load_kb_file(f"{slug}.md")
        )

        if data is None:
            # Search playbooks directory for fuzzy match
            search_root = playbooks_dir if playbooks_dir.exists() else self._kb_path
            if search_root.exists():
                for file_path in search_root.rglob("*"):
                    if file_path.is_dir():
                        continue
                    if slug in file_path.stem.lower():
                        try:
                            content = file_path.read_text(encoding="utf-8")
                            if file_path.suffix == ".json":
                                data = json.loads(content)
                            else:
                                data = content
                            break
                        except Exception as e:
                            logger.warning(f"Failed to read playbook '{file_path}': {e}")

        if data is None:
            return self._err(
                f"Playbook '{playbook_name}' not found in knowledge base. "
                f"Searched in: {playbooks_dir}"
            )

        if section and isinstance(data, dict):
            section_data = data.get(section)
            if section_data is not None:
                return self._ok({"playbook": playbook_name, "section": section, "content": section_data})
            matched = next(
                (v for k, v in data.items() if k.lower() == section.lower()),
                None,
            )
            if matched is not None:
                return self._ok({"playbook": playbook_name, "section": section, "content": matched})

        return self._ok({"playbook": playbook_name, "content": data})

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _load_kb_file(self, relative_path: str):
        """
        Load a file from the knowledge base directory.
        Returns parsed JSON (dict/list) for .json files, or raw string for .md/.txt files.
        Returns None if file does not exist or fails to load.
        """
        file_path = self._kb_path / relative_path
        if not file_path.exists():
            return None
        try:
            content = file_path.read_text(encoding="utf-8")
            if relative_path.endswith(".json"):
                return json.loads(content)
            return content
        except Exception as e:
            logger.warning(f"Failed to load KB file '{relative_path}': {e}")
            return None

    def _extract_snippet(self, content: str, query: str, context_chars: int = 200) -> str:
        """Extract a snippet from content around the first query match."""
        idx = content.lower().find(query)
        if idx == -1:
            # Return the beginning of the content
            return content[:context_chars].strip() + ("..." if len(content) > context_chars else "")
        start = max(0, idx - context_chars // 2)
        end = min(len(content), idx + len(query) + context_chars // 2)
        snippet = content[start:end].strip()
        if start > 0:
            snippet = "..." + snippet
        if end < len(content):
            snippet = snippet + "..."
        # Remove excessive whitespace
        snippet = re.sub(r"\s+", " ", snippet)
        return snippet
