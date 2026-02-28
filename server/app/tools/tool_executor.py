"""
ToolExecutor — registers all tool collections and dispatches LLM tool calls.

Called by the LLM Manager (Phase 4) during the agentic tool-use loop.

Usage (Phase 4 wires this up):
    executor = ToolExecutor(config)
    result = await executor.execute("outlook_send_email", to=["..."], subject="...", body_html="...")

    # Get all tool definitions for LLM function calling
    definitions = executor.get_all_definitions()

Tool registration order matches TOOLS.md spec.
Phase 2 tools registered here. Phase 3, 4 tools will extend this in later sessions.
"""

import logging
import os
import yaml
from pathlib import Path
from typing import Optional

logger = logging.getLogger("mezzofy.tool_executor")


def _load_config() -> dict:
    """Load config.yaml from server/config/ directory."""
    config_path = Path(__file__).parent.parent.parent / "config" / "config.yaml"
    if config_path.exists():
        return yaml.safe_load(config_path.read_text()) or {}
    # Fallback to example config for dev
    example_path = Path(__file__).parent.parent.parent / "config" / "config.example.yaml"
    if example_path.exists():
        return yaml.safe_load(example_path.read_text()) or {}
    return {}


class ToolExecutor:
    """
    Central tool registry and dispatcher.

    Lazy-initializes tool collections on first use to avoid heavy imports
    at startup (e.g., playwright, whisper, weasyprint).
    """

    def __init__(self, config: Optional[dict] = None):
        self.config = config or _load_config()
        self._registry: dict[str, object] = {}  # tool_name → ops_instance
        self._definitions: list[dict] = []
        self._loaded = False

    def _load_all_tools(self) -> None:
        """Register all tool collections. Called once on first use."""
        if self._loaded:
            return

        # ── Phase 2: Communication + Document Tools ───────────────────────────
        self._register_ops("communication.outlook_ops", "OutlookOps")
        self._register_ops("communication.teams_ops", "TeamsOps")
        self._register_ops("communication.push_ops", "PushOps")
        self._register_ops("document.pdf_ops", "PDFOps")
        self._register_ops("document.pptx_ops", "PPTXOps")
        self._register_ops("document.docx_ops", "DocxOps")
        self._register_ops("document.csv_ops", "CSVOps")

        # ── Phase 3: Media + Web + Database Tools ────────────────────────────
        self._register_ops("media.image_ops", "ImageOps")
        self._register_ops("media.video_ops", "VideoOps")
        self._register_ops("media.audio_ops", "AudioOps")
        self._register_ops("web.browser_ops", "BrowserOps")
        self._register_ops("web.scraping_ops", "ScrapingOps")
        self._register_ops("web.linkedin_ops", "LinkedInOps")
        self._register_ops("database.db_ops", "DatabaseOps")
        self._register_ops("database.crm_ops", "CRMOps")
        self._register_ops("mezzofy.data_ops", "MezzofyDataOps")
        self._register_ops("mezzofy.knowledge_ops", "KnowledgeOps")
        # Note: speech_ops (SpeechOps) is NOT registered here — WebSocket-only

        self._loaded = True
        logger.info(f"ToolExecutor loaded {len(self._definitions)} tools")

    def _register_ops(self, module_suffix: str, class_name: str) -> None:
        """
        Dynamically import and register a tool ops class.
        Failures are logged but do not crash the server.
        """
        try:
            import importlib
            module = importlib.import_module(f"app.tools.{module_suffix}")
            cls = getattr(module, class_name)
            instance = cls(self.config)
            for tool_def in instance.get_tools():
                name = tool_def["name"]
                self._registry[name] = instance
                # Store definition without the handler callable
                self._definitions.append({
                    "name": name,
                    "description": tool_def["description"],
                    "parameters": tool_def["parameters"],
                })
        except Exception as e:
            logger.warning(f"Failed to load {class_name} from {module_suffix}: {e}")

    async def execute(self, tool_name: str, **kwargs) -> dict:
        """
        Execute a named tool with the given arguments.
        Returns {success: bool, output/error: ...}.
        """
        self._load_all_tools()
        ops = self._registry.get(tool_name)
        if not ops:
            return {"success": False, "error": f"Unknown tool: '{tool_name}'"}
        return await ops.execute(tool_name, **kwargs)

    def get_all_definitions(self) -> list[dict]:
        """
        Return all registered tool definitions in OpenAI function-calling format.
        Used by LLM Manager to populate the tools list in API calls.
        """
        self._load_all_tools()
        return self._definitions

    def get_tool_names(self) -> list[str]:
        """Return all registered tool names."""
        self._load_all_tools()
        return list(self._registry.keys())
