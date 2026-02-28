"""
Speech Handler — live speech-to-text session manager for WebSocket streaming.

The mobile app sends audio in chunks:
  {"type": "speech_start"}
  {"type": "speech_audio", "data": "<base64 chunk>"}  (repeated)
  {"type": "speech_end"}

SpeechSession accumulates chunks and transcribes on end via AudioOps.
One SpeechSession instance per WebSocket connection (per user session).

The final transcript is returned and treated as a normal text message.
"""

import base64
import logging
import os
import tempfile
from typing import Optional

logger = logging.getLogger("mezzofy.input.speech")


class SpeechSession:
    """
    Manages a single live speech capture session for one WebSocket connection.

    Lifecycle:
      1. start()          — begins accumulation, clears previous chunks
      2. add_chunk(b64)   — appends decoded audio bytes
      3. end_and_transcribe() → str — concatenates + transcribes, returns text
    """

    __slots__ = ("_config", "_chunks", "_active")

    def __init__(self, config: dict):
        self._config = config
        self._chunks: list[bytes] = []
        self._active = False

    def start(self) -> None:
        """Begin a new speech capture session."""
        self._chunks = []
        self._active = True
        logger.debug("Speech session started")

    def add_chunk(self, audio_b64: str) -> None:
        """Decode and buffer one audio chunk from WebSocket."""
        if not self._active:
            logger.warning("Received audio chunk outside active speech session")
            return
        try:
            chunk = base64.b64decode(audio_b64)
            self._chunks.append(chunk)
        except Exception as e:
            logger.warning(f"Failed to decode audio chunk: {e}")

    async def end_and_transcribe(self) -> str:
        """
        Finalize and transcribe all accumulated audio chunks.

        Concatenates raw bytes → writes to temp WAV → calls AudioOps.transcribe_audio.
        Returns the transcript string (empty string on failure).
        """
        self._active = False
        if not self._chunks:
            logger.debug("Speech session ended with no audio chunks")
            return ""

        combined = b"".join(self._chunks)
        self._chunks = []

        tmp_path: Optional[str] = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp.write(combined)
                tmp_path = tmp.name

            from app.tools.media.audio_ops import AudioOps
            audio_ops = AudioOps(self._config)

            result = await audio_ops.execute("transcribe_audio", audio_path=tmp_path)
            transcript = result.get("output", "") if result.get("success") else ""
            logger.debug(
                f"Speech transcription complete: {len(transcript)} chars"
            )
            return transcript

        except Exception as e:
            logger.error(f"Speech transcription failed: {e}")
            return ""

        finally:
            if tmp_path:
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass

    @property
    def is_active(self) -> bool:
        return self._active
