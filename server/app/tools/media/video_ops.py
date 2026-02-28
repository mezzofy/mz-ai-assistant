"""
Video Tool — key frame extraction, audio track separation, metadata, and analysis.

Tools provided:
    extract_key_frames  — Extract frames at regular intervals (OpenCV)
    extract_audio_track — Separate audio track from video (MoviePy)
    get_video_info      — Get duration, FPS, resolution, codec (OpenCV)
    analyze_video       — Combined frame + audio analysis (Claude Vision + Whisper)

Config section: config["media_processing"]
Libraries: opencv-python-headless, moviepy, openai-whisper, anthropic (all lazy-imported)
"""

import logging
import os
import tempfile
from typing import Optional

from app.tools.base_tool import BaseTool

logger = logging.getLogger("mezzofy.tools.video")


class VideoOps(BaseTool):

    def get_tools(self) -> list[dict]:
        return [
            {
                "name": "extract_key_frames",
                "description": (
                    "Extract key frames from a video at regular time intervals using OpenCV. "
                    "Returns frames as a list of base64-encoded JPEG images. "
                    "Used as input for visual analysis of video content."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "video_bytes": {
                            "type": "string",
                            "description": "Base64-encoded video file bytes (MP4, MOV, AVI)",
                        },
                        "interval_seconds": {
                            "type": "number",
                            "description": "Extract one frame every N seconds (default: 5)",
                            "default": 5,
                        },
                    },
                    "required": ["video_bytes"],
                },
                "handler": self._extract_key_frames,
            },
            {
                "name": "extract_audio_track",
                "description": (
                    "Extract the audio track from a video file using MoviePy. "
                    "Returns the audio as base64-encoded WAV bytes and duration."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "video_bytes": {
                            "type": "string",
                            "description": "Base64-encoded video file bytes (MP4, MOV, AVI)",
                        },
                    },
                    "required": ["video_bytes"],
                },
                "handler": self._extract_audio_track,
            },
            {
                "name": "get_video_info",
                "description": (
                    "Get metadata about a video file: duration in seconds, frames per second, "
                    "resolution (width × height), codec, and file size."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "video_bytes": {
                            "type": "string",
                            "description": "Base64-encoded video file bytes",
                        },
                    },
                    "required": ["video_bytes"],
                },
                "handler": self._get_video_info,
            },
            {
                "name": "analyze_video",
                "description": (
                    "Fully analyze a video: extract key frames for visual description via "
                    "Claude Vision, then transcribe the audio via Whisper. "
                    "Returns a visual_summary and a full transcript. "
                    "Maximum supported video duration: 5 minutes."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "video_bytes": {
                            "type": "string",
                            "description": "Base64-encoded video file bytes (max 5 minutes)",
                        },
                    },
                    "required": ["video_bytes"],
                },
                "handler": self._analyze_video,
            },
        ]

    # ── Handlers ──────────────────────────────────────────────────────────────

    async def _extract_key_frames(
        self,
        video_bytes: str,
        interval_seconds: float = 5,
    ) -> dict:
        try:
            import base64

            import cv2

            raw = base64.b64decode(video_bytes) if isinstance(video_bytes, str) else video_bytes

            with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
                tmp.write(raw)
                tmp_path = tmp.name

            try:
                cap = cv2.VideoCapture(tmp_path)
                fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
                frame_interval = max(1, int(fps * interval_seconds))

                frames: list[str] = []
                frame_idx = 0

                while True:
                    ret, frame = cap.read()
                    if not ret:
                        break
                    if frame_idx % frame_interval == 0:
                        _, buf = cv2.imencode(".jpg", frame)
                        frames.append(base64.b64encode(buf.tobytes()).decode())
                    frame_idx += 1

                cap.release()
                logger.info(
                    f"extract_key_frames: {len(frames)} frames at {interval_seconds}s intervals"
                )
                return self._ok({"frames": frames, "count": len(frames)})
            finally:
                os.unlink(tmp_path)
        except Exception as e:
            logger.error(f"extract_key_frames failed: {e}")
            return self._err(f"Frame extraction failed: {e}")

    async def _extract_audio_track(self, video_bytes: str) -> dict:
        tmp_path = None
        audio_path = None
        try:
            import base64

            from moviepy.editor import VideoFileClip

            raw = base64.b64decode(video_bytes) if isinstance(video_bytes, str) else video_bytes

            with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
                tmp.write(raw)
                tmp_path = tmp.name

            audio_path = tmp_path.replace(".mp4", "_audio.wav")

            clip = VideoFileClip(tmp_path)
            if clip.audio is None:
                clip.close()
                return self._err("Video has no audio track")

            clip.audio.write_audiofile(audio_path, logger=None)
            duration = clip.duration
            clip.close()

            with open(audio_path, "rb") as f:
                audio_data = f.read()

            logger.info(
                f"extract_audio_track: {len(audio_data)} bytes, duration={duration:.1f}s"
            )
            return self._ok({
                "audio_bytes": base64.b64encode(audio_data).decode(),
                "duration": round(duration, 2),
                "format": "wav",
            })
        except Exception as e:
            logger.error(f"extract_audio_track failed: {e}")
            return self._err(f"Audio extraction failed: {e}")
        finally:
            for p in [tmp_path, audio_path]:
                if p and os.path.exists(p):
                    os.unlink(p)

    async def _get_video_info(self, video_bytes: str) -> dict:
        try:
            import base64

            import cv2

            raw = base64.b64decode(video_bytes) if isinstance(video_bytes, str) else video_bytes

            with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
                tmp.write(raw)
                tmp_path = tmp.name

            try:
                cap = cv2.VideoCapture(tmp_path)
                fps = cap.get(cv2.CAP_PROP_FPS)
                frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

                # Decode the four-character codec code
                fourcc_int = int(cap.get(cv2.CAP_PROP_FOURCC))
                codec = "".join(
                    [chr((fourcc_int >> (8 * i)) & 0xFF) for i in range(4)]
                ).strip()
                cap.release()

                duration = round(frame_count / fps, 2) if fps > 0 else 0

                return self._ok({
                    "duration": duration,
                    "fps": round(fps, 2),
                    "width": width,
                    "height": height,
                    "codec": codec,
                    "frame_count": frame_count,
                    "file_size_bytes": len(raw),
                })
            finally:
                os.unlink(tmp_path)
        except Exception as e:
            logger.error(f"get_video_info failed: {e}")
            return self._err(f"Video info failed: {e}")

    async def _analyze_video(self, video_bytes: str) -> dict:
        try:
            import base64
            import tempfile

            import anthropic
            import whisper

            raw = base64.b64decode(video_bytes) if isinstance(video_bytes, str) else video_bytes

            # ── Step 1: Extract key frames every 5 seconds ────────────────────
            frames_result = await self._extract_key_frames(
                video_bytes=video_bytes, interval_seconds=5
            )
            if not frames_result["success"]:
                return frames_result
            frames: list[str] = frames_result["output"]["frames"]

            # ── Step 2: Extract and transcribe audio (inline Whisper) ─────────
            transcript = ""
            audio_result = await self._extract_audio_track(video_bytes=video_bytes)
            if audio_result["success"]:
                audio_raw = base64.b64decode(audio_result["output"]["audio_bytes"])
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as atmp:
                    atmp.write(audio_raw)
                    atmp_path = atmp.name
                try:
                    model_name = (
                        self.config.get("media_processing", {}).get("whisper_model", "base")
                    )
                    wmodel = whisper.load_model(model_name)
                    result = wmodel.transcribe(atmp_path)
                    transcript = result["text"].strip()
                except Exception as te:
                    logger.warning(f"analyze_video transcription failed: {te}")
                finally:
                    os.unlink(atmp_path)

            # ── Step 3: Analyze frames via Claude Vision ───────────────────────
            api_key = (
                self.config.get("llm", {}).get("claude", {}).get("api_key")
                or os.getenv("ANTHROPIC_API_KEY", "")
            )
            model = (
                self.config.get("llm", {}).get("claude", {}).get("model")
                or os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")
            )

            client = anthropic.Anthropic(api_key=api_key)
            # Use up to 5 evenly-spaced frames for visual analysis
            sample_frames = frames[:: max(1, len(frames) // 5)][:5]

            content: list[dict] = [
                {
                    "type": "text",
                    "text": (
                        "Describe the visual content of this video based on these key frames. "
                        "Be concise and focus on what is shown."
                    ),
                }
            ]
            for frame_b64 in sample_frames:
                content.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/jpeg",
                        "data": frame_b64,
                    },
                })

            response = client.messages.create(
                model=model,
                max_tokens=1024,
                messages=[{"role": "user", "content": content}],
            )
            visual_summary = response.content[0].text if response.content else ""

            logger.info(
                f"analyze_video: {len(frames)} frames, transcript={len(transcript)} chars"
            )
            return self._ok({
                "visual_summary": visual_summary,
                "transcript": transcript,
                "frames_analyzed": len(sample_frames),
            })
        except Exception as e:
            logger.error(f"analyze_video failed: {e}")
            return self._err(f"Video analysis failed: {e}")
