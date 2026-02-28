"""
Video Handler — frame extraction + audio transcription for uploaded videos.

Short videos (<60 s) are processed inline.
Long videos should be dispatched to Celery (wired in Phase 6).
Processing delegates to VideoOps (Phase 3).
"""

import logging
import os
import tempfile
from typing import Optional

logger = logging.getLogger("mezzofy.input.video")


async def handle_video(
    task: dict,
    file_bytes: bytes,
    filename: str,
) -> dict:
    """
    Process an uploaded video: key frame analysis + audio transcription.

    Args:
        task:       Task dict with _config and optional message.
        file_bytes: Raw video bytes (MP4, MOV, AVI).
        filename:   Original filename for extension detection.

    Returns:
        Task dict enriched with extracted_text containing scene descriptions
        and audio transcript, plus media_content metadata.
    """
    config = task.get("_config", {})
    ext = os.path.splitext(filename)[1].lower() or ".mp4"

    tmp_path: Optional[str] = None
    try:
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp.write(file_bytes)
            tmp_path = tmp.name

        from app.tools.media.video_ops import VideoOps
        video_ops = VideoOps(config)

        description = ""
        transcript = ""
        try:
            result = await video_ops.execute("analyze_video", video_path=tmp_path)
            if result.get("success"):
                description = (result.get("output") or "").strip()
                transcript = (result.get("transcript") or "").strip()
        except Exception as e:
            logger.warning(f"Video analysis failed for {filename}: {e}")

        parts = []
        if description:
            parts.append(f"[Video description: {description}]")
        if transcript:
            parts.append(f"[Audio transcript: {transcript}]")
        user_msg = (task.get("message") or "").strip()
        if user_msg:
            parts.append(user_msg)

        extracted_text = (
            "\n".join(parts) if parts else "[Video uploaded — no content extracted]"
        )

        return {
            **task,
            "input_type": "video",
            "extracted_text": extracted_text,
            "media_content": {
                "filename": filename,
                "description": description,
                "transcript": transcript,
            },
            "input_summary": f"Video: {filename}",
        }

    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
