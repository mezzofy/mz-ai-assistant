"""
Audio Handler — transcribes uploaded audio files (pre-recorded, not live).

Live speech from the mobile app is handled by speech_handler.py via WebSocket.
This handler processes audio file uploads from /chat/send-media.

Delegates transcription to AudioOps.transcribe_audio (Whisper, Phase 3).
"""

import logging
import os
import tempfile
from typing import Optional

logger = logging.getLogger("mezzofy.input.audio")


async def handle_audio(
    task: dict,
    file_bytes: bytes,
    filename: str,
) -> dict:
    """
    Transcribe an uploaded audio file (MP3, WAV, M4A, OGG).

    Args:
        task:       Task dict with _config and optional message.
        file_bytes: Raw audio bytes.
        filename:   Original filename for extension detection.

    Returns:
        Task dict enriched with extracted_text containing the transcript.
    """
    config = task.get("_config", {})
    ext = os.path.splitext(filename)[1].lower() or ".mp3"

    tmp_path: Optional[str] = None
    try:
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp.write(file_bytes)
            tmp_path = tmp.name

        from app.tools.media.audio_ops import AudioOps
        audio_ops = AudioOps(config)

        transcript = ""
        detected_language = ""
        try:
            result = await audio_ops.execute("transcribe_audio", audio_path=tmp_path)
            if result.get("success"):
                transcript = (result.get("output") or "").strip()
                detected_language = (result.get("language") or "").strip()
        except Exception as e:
            logger.warning(f"Audio transcription failed for {filename}: {e}")

        parts = []
        if transcript:
            parts.append(f"[Audio transcript: {transcript}]")
        user_msg = (task.get("message") or "").strip()
        if user_msg:
            parts.append(user_msg)

        extracted_text = (
            "\n".join(parts) if parts else "[Audio uploaded — transcription failed]"
        )

        return {
            **task,
            "input_type": "audio",
            "extracted_text": extracted_text,
            "media_content": {
                "filename": filename,
                "transcript": transcript,
                "language": detected_language,
            },
            "input_summary": (
                f"Audio transcription: {transcript[:100]}…"
                if transcript
                else f"Audio: {filename} (transcription failed)"
            ),
        }

    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
