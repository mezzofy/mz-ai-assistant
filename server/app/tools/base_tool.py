"""
BaseTool — common interface for all Mezzofy AI Assistant tool implementations.

Every tool module (OutlookOps, TeamsOps, PDFOps, etc.) implements this pattern:

    class MyOps(BaseTool):
        def get_tools(self) -> list[dict]:
            return [
                {
                    "name": "my_tool",
                    "description": "...",
                    "parameters": {...},   # JSON Schema
                    "handler": self._my_handler,
                }
            ]

        async def _my_handler(self, **kwargs) -> dict:
            # Returns {success: True, output: ...} or {success: False, error: "..."}

The ToolExecutor (tool_executor.py) registers all tools and dispatches calls from the LLM.
"""

import logging
import traceback
from abc import ABC, abstractmethod
from typing import Any, Callable

logger = logging.getLogger("mezzofy.tools")


class BaseTool(ABC):
    """
    Abstract base for all tool collections.

    Each subclass registers one or more named tools via get_tools().
    The ToolExecutor calls execute(name, **kwargs) to dispatch to the right handler.
    """

    def __init__(self, config: dict):
        """
        Args:
            config: Full loaded config.yaml dict (or subset). Tools read their own
                    section (e.g., config["ms365"], config["teams"]).
        """
        self.config = config

    @abstractmethod
    def get_tools(self) -> list[dict]:
        """
        Return a list of tool definitions.

        Each dict has:
            name        (str)      — unique tool name for LLM function calling
            description (str)      — human-readable purpose for the LLM
            parameters  (dict)     — JSON Schema object with required + properties
            handler     (Callable) — async function(self, **kwargs) → dict
        """

    async def execute(self, tool_name: str, **kwargs) -> dict:
        """
        Find the named tool and call its handler.
        Always returns {success: bool, output/error: ...}.
        Never raises — all exceptions are caught and returned as errors.
        """
        tools_by_name = {t["name"]: t for t in self.get_tools()}
        tool = tools_by_name.get(tool_name)
        if not tool:
            return {"success": False, "error": f"Tool '{tool_name}' not found in {self.__class__.__name__}"}

        try:
            result = await tool["handler"](**kwargs)
            if not isinstance(result, dict):
                result = {"output": result}
            if "success" not in result:
                result["success"] = True
            return result
        except Exception as e:
            logger.error(f"Tool '{tool_name}' failed: {e}\n{traceback.format_exc()}")
            return {"success": False, "error": str(e)}

    def _ok(self, output: Any) -> dict:
        """Convenience helper: wrap a successful result."""
        return {"success": True, "output": output}

    def _err(self, message: str) -> dict:
        """Convenience helper: wrap an error result."""
        return {"success": False, "error": message}
