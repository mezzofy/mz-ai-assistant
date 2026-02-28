"""
Speech Tool — real-time STT streaming and language detection for live audio.

Tools provided:
    stream_stt            — Accumulate audio chunks; transcribe on flush (Whisper)
    detect_speech_language — Detect spoken language from an audio clip (Whisper)

Note: These tools are primarily used via WebSocket streaming, not standard REST calls.
      The in-memory buffer (_SESSION_BUFFERS) is process-local; for multi-worker deployments
      route sessions to a fixed worker or move buffers to Redis.

Config section: config["media_processing"] → whisper_model
Library: openai-whisper (lazy-imported)
"""

import logging
import os
import tempfile

from app.tools.base_tool import BaseTool

logger = logging.getLogger("mezzofy.tools.speech")

# In-process buffer: session_id → accumulated raw audio bytes
# Cleared on flush or session timeout
_SESSION_BUFFERS: dict[str, list[bytes]] = {}


class SpeechOps(BaseTool):

    def get_tools(self) -> list[dict]:
        return [
            {
                "name": "stream_stt",
                "description": (
                    "Accumulate audio chunks for a real-time speech-to-text session. "
                    "Each call buffers the audio chunk. When flush=true, all buffered audio "
                    "is transcribed via Whisper and the buffer is cleared. "
                    "Returns partial_text and is_final flag."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "audio_chunk_bytes": {
                            "type": "string",
                            "description": "Base64-encoded PCM/WAV audio chunk to buffer",
                        },
                        "session_id": {
                            "type": "string",
                            "description": "Unique session identifier grouping audio chunks into one utterance",
                        },
                        "flush": {
                            "type": "boolean",
                            "description": (
                                "If true, transcribe all buffered audio for this session "
                                "and clear the buffer (signals end of utterance)"
                            ),
                            "default": False,
                        },
                    },
                    "required": ["audio_chunk_bytes", "session_id"],
                },
                "handler": self._stream_stt,
            },
            {
                "name": "detect_speech_language",
                "description": (
                    "Detect the spoken language from an audio clip using Whisper. "
                    "First 30 seconds of the audio are used for detection. "
                    "Returns ISO language code and confidence probability."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "audio_bytes": {
                            "type": "string",
                            "description": "Base64-encoded audio bytes (WAV preferred)",
                        },
                    },
                    "required": ["audio_bytes"],
                },
                "handler": self._detect_speech_language,
            },
        ]

    # ── Private helpers ────────────────────────────────────────────────────────

    def _load_whisper_model(self):
        """Lazy-load the Whisper model. Heavy import done once per process."""
        import whisper

        model_name = self.config.get("media_processing", {}).get("whisper_model", "base")
        return whisper.load_model(model_name)

    # ── Handlers ──────────────────────────────────────────────────────────────

    async def _stream_stt(
        self,
        audio_chunk_bytes: str,
        session_id: str,
        flush: bool = False,
    ) -> dict:
        try:
            import base64

            raw = (
                base64.b64decode(audio_chunk_bytes)
                if isinstance(audio_chunk_bytes, str)
                else audio_chunk_bytes
            )

            # Accumulate chunk
            if session_id not in _SESSION_BUFFERS:
                _SESSION_BUFFERS[session_id] = []
            _SESSION_BUFFERS[session_id].append(raw)

            if not flush:
                total_bytes = sum(len(c) for c in _SESSION_BUFFERS[session_id])
                return self._ok({
                    "partial_text": "",
                    "is_final": False,
                    "buffered_bytes": total_bytes,
                })

            # Flush: concatenate buffer and transcribe
            combined = b"".join(_SESSION_BUFFERS.pop(session_id, []))
            if not combined:
                return self._ok({"partial_text": "", "is_final": True, "buffered_bytes": 0})

            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp.write(combined)
                tmp_path = tmp.name

            try:
                model = self._load_whisper_model()
                result = model.transcribe(tmp_path)
                text = result["text"].strip()
                logger.info(f"stream_stt flush [{session_id}]: {len(text)} chars")
                return self._ok({"partial_text": text, "is_final": True})
            finally:
                os.unlink(tmp_path)

        except Exception as e:
            # Clear buffer on error to avoid corrupted state
            _SESSION_BUFFERS.pop(session_id, None)
            logger.error(f"stream_stt failed [{session_id}]: {e}")
            return self._err(f"STT streaming failed: {e}")

    async def _detect_speech_language(self, audio_bytes: str) -> dict:
        try:
            import base64

            import whisper

            raw = base64.b64decode(audio_bytes) if isinstance(audio_bytes, str) else audio_bytes

            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp.write(raw)
                tmp_path = tmp.name

            try:
                model = self._load_whisper_model()

                audio = whisper.load_audio(tmp_path)
                audio = whisper.pad_or_trim(audio)
                mel = whisper.log_mel_spectrogram(audio).to(model.device)
                _, probs = model.detect_language(mel)

                detected = max(probs, key=probs.get)
                probability = round(float(probs[detected]), 4)

                logger.info(f"detect_speech_language: {detected} (prob={probability})")
                return self._ok({"language": detected, "probability": probability})
            finally:
                os.unlink(tmp_path)
        except Exception as e:
            logger.error(f"detect_speech_language failed: {e}")
            return self._err(f"Language detection failed: {e}")
