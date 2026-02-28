"""
Input Router — detects input type and dispatches to the correct handler.

All handlers return a copy of the task dict enriched with:
  extracted_text  — text representation for the LLM (text + media context)
  media_content   — structured metadata from the media processing
  input_summary   — human-readable description of what was processed

Handlers are called BEFORE routing to agents. By the time a task reaches
an agent, all media has been converted to extracted_text.

speech and camera inputs are NOT routed here — they are handled directly
inside the WebSocket handler in chat.py (streaming, real-time).
"""

import logging
from typing import Optional

logger = logging.getLogger("mezzofy.input.router")


async def process_input(
    task: dict,
    file_bytes: Optional[bytes] = None,
    filename: Optional[str] = None,
) -> dict:
    """
    Process input based on task["input_type"] and return enriched task dict.

    Args:
        task:       Normalized task dict with input_type, message, _config, etc.
        file_bytes: Raw bytes of uploaded file (image/video/audio/document).
        filename:   Original filename for type detection.

    Returns:
        Task dict with extracted_text, media_content, input_summary populated.
    """
    input_type = task.get("input_type", "text")

    if input_type == "text":
        from app.input.text_handler import handle_text
        return await handle_text(task)

    if input_type == "image":
        from app.input.image_handler import handle_image
        return await handle_image(task, file_bytes or b"", filename or "image.jpg")

    if input_type == "video":
        from app.input.video_handler import handle_video
        return await handle_video(task, file_bytes or b"", filename or "video.mp4")

    if input_type == "audio":
        from app.input.audio_handler import handle_audio
        return await handle_audio(task, file_bytes or b"", filename or "audio.mp3")

    if input_type == "file":
        from app.input.file_handler import handle_file
        return await handle_file(task, file_bytes or b"", filename or "document")

    if input_type == "url":
        from app.input.url_handler import handle_url
        return await handle_url(task)

    # speech and camera handled by WebSocket — passthrough here
    if input_type in ("speech", "camera"):
        return {
            **task,
            "extracted_text": task.get("message", ""),
            "media_content": None,
            "input_summary": f"{input_type} input (processed by WebSocket handler)",
        }

    logger.warning(f"Unknown input_type={input_type!r} — treating as text")
    return {
        **task,
        "extracted_text": task.get("message", ""),
        "media_content": None,
        "input_summary": f"Unknown input type: {input_type}",
    }
