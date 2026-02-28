"""
Audio Tool — transcription, language detection, format conversion, and metadata.

Tools provided:
    transcribe_audio  — Full audio file → text transcription (Whisper)
    detect_language   — Detect spoken language (Whisper)
    convert_audio     — Convert between audio formats (pydub / FFmpeg)
    get_audio_info    — Get duration, format, sample rate, channels (pydub)

Config section: config["media_processing"] → whisper_model
Libraries: openai-whisper, pydub (all lazy-imported)
"""

import logging
import os
import tempfile
from typing import Optional

from app.tools.base_tool import BaseTool

logger = logging.getLogger("mezzofy.tools.audio")


class AudioOps(BaseTool):

    def get_tools(self) -> list[dict]:
        return [
            {
                "name": "transcribe_audio",
                "description": (
                    "Transcribe a full audio file to text using OpenAI Whisper. "
                    "Supports MP3, WAV, M4A, OGG, FLAC. "
                    "Returns transcript text, detected language, and duration in seconds."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "audio_bytes": {
                            "type": "string",
                            "description": "Base64-encoded audio file bytes",
                        },
                        "language": {
                            "type": "string",
                            "description": (
                                "ISO language code hint (e.g. 'en', 'zh'). "
                                "Omit for automatic language detection."
                            ),
                        },
                        "file_extension": {
                            "type": "string",
                            "description": "File extension for format hint: mp3, wav, m4a, ogg, flac (default: wav)",
                            "default": "wav",
                        },
                    },
                    "required": ["audio_bytes"],
                },
                "handler": self._transcribe_audio,
            },
            {
                "name": "detect_language",
                "description": (
                    "Detect the spoken language in an audio clip using Whisper's "
                    "language detector. Returns language code and confidence probability."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "audio_bytes": {
                            "type": "string",
                            "description": "Base64-encoded audio bytes (WAV/MP3). First 30 seconds are used.",
                        },
                    },
                    "required": ["audio_bytes"],
                },
                "handler": self._detect_language,
            },
            {
                "name": "convert_audio",
                "description": (
                    "Convert an audio file between formats (e.g. M4A → WAV, MP3 → OGG). "
                    "Returns converted audio as base64-encoded bytes."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "audio_bytes": {
                            "type": "string",
                            "description": "Base64-encoded source audio bytes",
                        },
                        "from_format": {
                            "type": "string",
                            "description": "Source format: mp3, wav, m4a, ogg, flac, aac",
                        },
                        "to_format": {
                            "type": "string",
                            "description": "Target format: mp3, wav, m4a, ogg, flac, aac",
                        },
                    },
                    "required": ["audio_bytes", "from_format", "to_format"],
                },
                "handler": self._convert_audio,
            },
            {
                "name": "get_audio_info",
                "description": (
                    "Get metadata about an audio file: duration in seconds, format, "
                    "sample rate, number of channels, and file size."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "audio_bytes": {
                            "type": "string",
                            "description": "Base64-encoded audio file bytes",
                        },
                        "file_extension": {
                            "type": "string",
                            "description": "File extension for format parsing: mp3, wav, m4a, ogg (default: wav)",
                            "default": "wav",
                        },
                    },
                    "required": ["audio_bytes"],
                },
                "handler": self._get_audio_info,
            },
        ]

    # ── Private helpers ────────────────────────────────────────────────────────

    def _load_whisper_model(self):
        """Lazy-load the Whisper model (heavy import — done once per instance)."""
        import whisper  # openai-whisper

        model_name = self.config.get("media_processing", {}).get("whisper_model", "base")
        return whisper.load_model(model_name)

    # ── Handlers ──────────────────────────────────────────────────────────────

    async def _transcribe_audio(
        self,
        audio_bytes: str,
        language: Optional[str] = None,
        file_extension: str = "wav",
    ) -> dict:
        try:
            import base64

            raw = base64.b64decode(audio_bytes) if isinstance(audio_bytes, str) else audio_bytes

            with tempfile.NamedTemporaryFile(suffix=f".{file_extension}", delete=False) as tmp:
                tmp.write(raw)
                tmp_path = tmp.name

            try:
                import asyncio

                model = self._load_whisper_model()
                options: dict = {}
                if language:
                    options["language"] = language

                # Whisper transcription is sync PyTorch — run off event loop thread
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    None, lambda: model.transcribe(tmp_path, **options)
                )

                text = result["text"].strip()
                detected_lang = result.get("language")
                # Duration from last segment end time
                segments = result.get("segments", [])
                duration = segments[-1]["end"] if segments else None

                logger.info(f"transcribe_audio: {len(text)} chars, lang={detected_lang}")
                return self._ok({"text": text, "language": detected_lang, "duration": duration})
            finally:
                os.unlink(tmp_path)
        except Exception as e:
            logger.error(f"transcribe_audio failed: {e}")
            return self._err(f"Transcription failed: {e}")

    async def _detect_language(self, audio_bytes: str) -> dict:
        try:
            import base64

            import whisper

            raw = base64.b64decode(audio_bytes) if isinstance(audio_bytes, str) else audio_bytes

            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp.write(raw)
                tmp_path = tmp.name

            try:
                import asyncio

                model = self._load_whisper_model()

                # All Whisper calls are sync PyTorch — bundle into one off-thread task
                def _detect():
                    audio = whisper.load_audio(tmp_path)
                    audio = whisper.pad_or_trim(audio)
                    mel = whisper.log_mel_spectrogram(audio).to(model.device)
                    _, probs = model.detect_language(mel)
                    return probs

                loop = asyncio.get_event_loop()
                probs = await loop.run_in_executor(None, _detect)
                detected = max(probs, key=probs.get)
                probability = round(float(probs[detected]), 4)

                logger.info(f"detect_language: {detected} (prob={probability})")
                return self._ok({"language": detected, "probability": probability})
            finally:
                os.unlink(tmp_path)
        except Exception as e:
            logger.error(f"detect_language failed: {e}")
            return self._err(f"Language detection failed: {e}")

    async def _convert_audio(
        self,
        audio_bytes: str,
        from_format: str,
        to_format: str,
    ) -> dict:
        src_path = None
        dst_path = None
        try:
            import base64

            from pydub import AudioSegment

            raw = base64.b64decode(audio_bytes) if isinstance(audio_bytes, str) else audio_bytes

            with tempfile.NamedTemporaryFile(
                suffix=f".{from_format}", delete=False
            ) as src:
                src.write(raw)
                src_path = src.name

            dst_path = src_path.replace(f".{from_format}", f".{to_format}")

            seg = AudioSegment.from_file(src_path, format=from_format)
            seg.export(dst_path, format=to_format)

            with open(dst_path, "rb") as f:
                converted = f.read()

            logger.info(
                f"convert_audio: {from_format} → {to_format}, {len(converted)} bytes"
            )
            return self._ok({
                "audio_bytes": base64.b64encode(converted).decode(),
                "format": to_format,
                "size_bytes": len(converted),
            })
        except Exception as e:
            logger.error(f"convert_audio failed: {e}")
            return self._err(f"Audio conversion failed: {e}")
        finally:
            for p in [src_path, dst_path]:
                if p and os.path.exists(p):
                    os.unlink(p)

    async def _get_audio_info(self, audio_bytes: str, file_extension: str = "wav") -> dict:
        try:
            import base64

            from pydub import AudioSegment

            raw = base64.b64decode(audio_bytes) if isinstance(audio_bytes, str) else audio_bytes

            with tempfile.NamedTemporaryFile(suffix=f".{file_extension}", delete=False) as tmp:
                tmp.write(raw)
                tmp_path = tmp.name

            try:
                seg = AudioSegment.from_file(tmp_path, format=file_extension)
                return self._ok({
                    "duration_seconds": round(len(seg) / 1000.0, 2),
                    "format": file_extension,
                    "sample_rate": seg.frame_rate,
                    "channels": seg.channels,
                    "sample_width_bytes": seg.sample_width,
                    "file_size_bytes": len(raw),
                })
            finally:
                os.unlink(tmp_path)
        except Exception as e:
            logger.error(f"get_audio_info failed: {e}")
            return self._err(f"Audio info failed: {e}")
