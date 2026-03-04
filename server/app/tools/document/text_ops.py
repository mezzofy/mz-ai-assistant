"""
Text Tool — Create and read plain text files.

Tools provided:
    create_txt  — Write plain text content to a .txt file
    read_txt    — Read the contents of a .txt file

Output files saved to the configured artifact storage directory.
"""

import logging
import uuid
from pathlib import Path
from typing import Optional

from app.context.artifact_manager import get_user_artifacts_dir, get_dept_artifacts_dir
from app.core.user_context import get_user_dept, get_user_email
from app.tools.base_tool import BaseTool

logger = logging.getLogger("mezzofy.tools.text")


def _get_artifact_dir(config: dict) -> Path:
    base = config.get("storage", {}).get("local_path", "/data/artifacts")
    path = Path(base) / "txt"
    path.mkdir(parents=True, exist_ok=True)
    return path


class TextOps(BaseTool):
    """Plain text file creation and reading."""

    def __init__(self, config: dict):
        super().__init__(config)
        self._artifact_dir = _get_artifact_dir(config)

    def _resolve_output_dir(self, storage_scope: str = "user") -> Path:
        """Return output dir based on storage scope and user context."""
        dept = get_user_dept()
        email = get_user_email()
        if storage_scope == "department" and dept:
            return get_dept_artifacts_dir(dept)
        if email:
            return get_user_artifacts_dir(dept, email)
        return self._artifact_dir

    def get_tools(self) -> list[dict]:
        return [
            {
                "name": "create_txt",
                "description": (
                    "Create a plain text (.txt) file with the given content. "
                    "Use for notes, logs, plain reports, or any unformatted text. "
                    "Returns the file path of the saved file."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "content": {
                            "type": "string",
                            "description": "The text content to write to the file.",
                        },
                        "filename": {
                            "type": "string",
                            "description": (
                                "Output filename (without extension). "
                                "Auto-generated if not provided."
                            ),
                        },
                        "storage_scope": {
                            "type": "string",
                            "description": (
                                "Where to save the file. 'user' = personal folder (default), "
                                "'department' = shared department folder visible to the whole team."
                            ),
                            "enum": ["user", "department"],
                            "default": "user",
                        },
                    },
                    "required": ["content"],
                },
                "handler": self._create_txt,
            },
            {
                "name": "read_txt",
                "description": "Read the contents of a plain text (.txt) file.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "Absolute path to the .txt file to read.",
                        },
                    },
                    "required": ["file_path"],
                },
                "handler": self._read_txt,
            },
        ]

    async def _create_txt(
        self,
        content: str,
        filename: Optional[str] = None,
        storage_scope: str = "user",
    ) -> dict:
        """Write plain text content to a .txt file."""
        if not filename:
            filename = f"notes_{uuid.uuid4().hex[:8]}"

        output_path = self._resolve_output_dir(storage_scope) / f"{filename}.txt"

        try:
            output_path.write_text(content, encoding="utf-8")
            file_size = output_path.stat().st_size
            logger.info(f"Created TXT: {output_path}")
            return self._ok({
                "file_path": str(output_path),
                "filename": f"{filename}.txt",
                "size_bytes": file_size,
                "lines": content.count("\n") + 1 if content else 0,
            })
        except Exception as e:
            logger.error(f"Failed to create TXT: {e}")
            return self._err(str(e))

    async def _read_txt(self, file_path: str) -> dict:
        """Read a plain text file."""
        import os
        if not os.path.exists(file_path):
            return self._err(f"File not found: {file_path}")
        try:
            text = Path(file_path).read_text(encoding="utf-8")
            return self._ok({
                "file_path": file_path,
                "content": text,
                "size_bytes": len(text.encode("utf-8")),
                "lines": text.count("\n") + 1 if text else 0,
            })
        except Exception as e:
            logger.error(f"Failed to read TXT {file_path}: {e}")
            return self._err(str(e))
