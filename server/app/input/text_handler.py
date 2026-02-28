"""
Text Handler — plain text passthrough.

Text messages need no media processing. The handler normalises the task
and populates extracted_text = message so downstream components have a
consistent interface regardless of input type.
"""

import logging

logger = logging.getLogger("mezzofy.input.text")


async def handle_text(task: dict) -> dict:
    """
    Passthrough handler for plain text messages.

    Returns task enriched with:
        extracted_text  — the raw message string
        media_content   — None
        input_summary   — brief character count summary
    """
    message = task.get("message", "")
    return {
        **task,
        "input_type": "text",
        "extracted_text": message,
        "media_content": None,
        "input_summary": f"Text message ({len(message)} chars)",
    }
