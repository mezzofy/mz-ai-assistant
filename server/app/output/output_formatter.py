"""
Output Formatter — formats agent results for the mobile API response.

Provides consistent response envelope construction for:
  - REST API responses (format_api_response)
  - WebSocket message envelopes (format_ws_message)

All chat endpoints and the WebSocket handler use these helpers to ensure
a uniform response shape for the React Native mobile app.
"""

import logging

logger = logging.getLogger("mezzofy.output.formatter")


def format_api_response(
    session_id: str,
    content: str,
    artifacts: list,
    agent_used: str,
    tools_used: list,
    input_summary: str = "",
    success: bool = True,
) -> dict:
    """
    Build the standard REST API response envelope.

    Shape:
        {
            "session_id":      str,
            "response":        str,
            "input_processed": {summary: str} | None,
            "artifacts":       [{id, type, name, download_url}, ...],
            "agent_used":      str,
            "tools_used":      [str, ...],
            "success":         bool,
        }
    """
    return {
        "session_id": session_id,
        "response": (content or "").strip() or "Task completed.",
        "input_processed": {"summary": input_summary} if input_summary else None,
        "artifacts": [
            {
                "id": a.get("id"),
                "type": a.get("file_type") or a.get("type", "file"),
                "name": a.get("filename") or a.get("name", "artifact"),
                "download_url": a.get("download_url"),
            }
            for a in (artifacts or [])
        ],
        "agent_used": agent_used or "unknown",
        "tools_used": tools_used or [],
        "success": success,
    }


def format_ws_message(msg_type: str, **kwargs) -> dict:
    """
    Build a typed WebSocket message envelope.

    Supported types and their expected kwargs:
      "status"          → message: str
      "transcript"      → text: str, is_final: bool
      "camera_analysis" → description: str
      "task_queued"     → task_id: str, estimated_seconds: int
      "task_progress"   → task_id: str, progress: int (0-100), message: str
      "complete"        → response: dict (full API response)
      "error"           → detail: str

    Example:
        format_ws_message("status", message="Searching LinkedIn...")
        format_ws_message("complete", response={...})
    """
    return {"type": msg_type, **kwargs}
