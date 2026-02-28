"""
Image Tool — OCR, vision analysis, resize, and EXIF extraction.

Tools provided:
    ocr_image      — Extract text from image via Tesseract OCR
    analyze_image  — Describe image content via Claude Vision API
    resize_image   — Resize/compress image with Pillow
    extract_exif   — Extract EXIF metadata (GPS, date, device)

Config section: config["media_processing"]
Libraries: pytesseract, anthropic, Pillow (all lazy-imported)
"""

import logging
import os
from typing import Optional

from app.tools.base_tool import BaseTool

logger = logging.getLogger("mezzofy.tools.image")


class ImageOps(BaseTool):

    def get_tools(self) -> list[dict]:
        return [
            {
                "name": "ocr_image",
                "description": (
                    "Extract text from an image using OCR (Tesseract). Supports printed text, "
                    "scanned documents, and screenshots. Returns extracted text and confidence score."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "image_bytes": {
                            "type": "string",
                            "description": "Base64-encoded image bytes (JPEG, PNG, TIFF, BMP)",
                        },
                        "language": {
                            "type": "string",
                            "description": (
                                "OCR language code (default: 'eng'). "
                                "Use 'chi_sim' for Simplified Chinese, 'chi_tra' for Traditional Chinese."
                            ),
                            "default": "eng",
                        },
                    },
                    "required": ["image_bytes"],
                },
                "handler": self._ocr_image,
            },
            {
                "name": "analyze_image",
                "description": (
                    "Describe and analyze the content of an image using Claude Vision API. "
                    "Use for understanding what's in a photo, reading charts, or extracting "
                    "structured information from images."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "image_bytes": {
                            "type": "string",
                            "description": "Base64-encoded image bytes (JPEG or PNG)",
                        },
                        "prompt": {
                            "type": "string",
                            "description": (
                                "What to analyze or extract from the image. "
                                "E.g. 'Describe what you see' or 'Extract all text from this chart'."
                            ),
                        },
                    },
                    "required": ["image_bytes", "prompt"],
                },
                "handler": self._analyze_image,
            },
            {
                "name": "resize_image",
                "description": (
                    "Resize or compress an image to specified dimensions using Pillow. "
                    "Maintains aspect ratio. Returns the resized image as base64-encoded bytes."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "image_bytes": {
                            "type": "string",
                            "description": "Base64-encoded input image bytes",
                        },
                        "width": {
                            "type": "integer",
                            "description": "Target width in pixels (aspect ratio is preserved)",
                        },
                        "height": {
                            "type": "integer",
                            "description": "Target height in pixels (aspect ratio is preserved)",
                        },
                        "format": {
                            "type": "string",
                            "description": "Output format: JPEG, PNG, or WEBP (default: JPEG)",
                            "default": "JPEG",
                        },
                    },
                    "required": ["image_bytes", "width", "height"],
                },
                "handler": self._resize_image,
            },
            {
                "name": "extract_exif",
                "description": (
                    "Extract EXIF metadata from an image, including GPS coordinates, "
                    "capture date/time, camera device, and image dimensions."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "image_bytes": {
                            "type": "string",
                            "description": "Base64-encoded image bytes",
                        },
                    },
                    "required": ["image_bytes"],
                },
                "handler": self._extract_exif,
            },
        ]

    # ── Handlers ──────────────────────────────────────────────────────────────

    async def _ocr_image(self, image_bytes: str, language: str = "eng") -> dict:
        try:
            import base64
            import io

            import pytesseract
            from PIL import Image

            raw = base64.b64decode(image_bytes) if isinstance(image_bytes, str) else image_bytes
            image = Image.open(io.BytesIO(raw))

            import asyncio

            loop = asyncio.get_event_loop()

            # Get per-word confidence alongside full text (sync calls — off-thread)
            data = await loop.run_in_executor(
                None,
                lambda: pytesseract.image_to_data(
                    image, lang=language, output_type=pytesseract.Output.DICT
                ),
            )
            text = (
                await loop.run_in_executor(None, pytesseract.image_to_string, image, language)
            ).strip()

            # Average confidence, excluding non-text regions (confidence = -1)
            confidences = [c for c in data["conf"] if c != -1]
            avg_confidence = round(sum(confidences) / len(confidences), 1) if confidences else 0.0

            logger.info(f"ocr_image: extracted {len(text)} chars, confidence={avg_confidence}")
            return self._ok({"text": text, "confidence": avg_confidence, "language": language})
        except Exception as e:
            logger.error(f"ocr_image failed: {e}")
            return self._err(f"OCR failed: {e}")

    async def _analyze_image(self, image_bytes: str, prompt: str) -> dict:
        try:
            import base64

            import anthropic

            raw = base64.b64decode(image_bytes) if isinstance(image_bytes, str) else image_bytes
            b64_str = base64.b64encode(raw).decode()

            api_key = (
                self.config.get("llm", {}).get("claude", {}).get("api_key")
                or os.getenv("ANTHROPIC_API_KEY", "")
            )
            model = (
                self.config.get("llm", {}).get("claude", {}).get("model")
                or os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")
            )

            client = anthropic.AsyncAnthropic(api_key=api_key)
            response = await client.messages.create(
                model=model,
                max_tokens=1024,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/jpeg",
                                    "data": b64_str,
                                },
                            },
                            {"type": "text", "text": prompt},
                        ],
                    }
                ],
            )

            description = response.content[0].text if response.content else ""
            logger.info(f"analyze_image: {len(description)} char response")
            return self._ok({"description": description})
        except Exception as e:
            logger.error(f"analyze_image failed: {e}")
            return self._err(f"Vision analysis failed: {e}")

    async def _resize_image(
        self,
        image_bytes: str,
        width: int,
        height: int,
        format: str = "JPEG",
    ) -> dict:
        try:
            import base64
            import io

            from PIL import Image

            raw = base64.b64decode(image_bytes) if isinstance(image_bytes, str) else image_bytes
            image = Image.open(io.BytesIO(raw))

            # thumbnail() preserves aspect ratio, shrinking to fit within (width, height)
            image.thumbnail((width, height), Image.LANCZOS)

            fmt = format.upper()
            # JPEG does not support alpha channel
            if fmt == "JPEG" and image.mode in ("RGBA", "P", "LA"):
                image = image.convert("RGB")

            buf = io.BytesIO()
            image.save(buf, format=fmt)
            resized_bytes = buf.getvalue()

            logger.info(
                f"resize_image: output {image.width}×{image.height} {fmt}, "
                f"{len(resized_bytes)} bytes"
            )
            return self._ok({
                "image_bytes": base64.b64encode(resized_bytes).decode(),
                "size": {"width": image.width, "height": image.height},
                "format": fmt,
            })
        except Exception as e:
            logger.error(f"resize_image failed: {e}")
            return self._err(f"Image resize failed: {e}")

    async def _extract_exif(self, image_bytes: str) -> dict:
        try:
            import base64
            import io

            from PIL import Image
            from PIL.ExifTags import GPSTAGS, TAGS

            raw = base64.b64decode(image_bytes) if isinstance(image_bytes, str) else image_bytes
            image = Image.open(io.BytesIO(raw))

            exif_data: dict = {}
            raw_exif = image._getexif() if hasattr(image, "_getexif") else None  # type: ignore[attr-defined]
            if raw_exif:
                for tag_id, value in raw_exif.items():
                    tag = TAGS.get(tag_id, str(tag_id))
                    exif_data[tag] = (
                        value if isinstance(value, (int, float, str, bool)) else str(value)
                    )

            # Decode GPS sub-IFD (tag 34853 = GPSInfo)
            gps: dict = {}
            gps_info = raw_exif.get(34853) if raw_exif else None
            if gps_info:
                for key, val in gps_info.items():
                    gps[GPSTAGS.get(key, str(key))] = (
                        val if isinstance(val, (int, float, str)) else str(val)
                    )

            result = {
                "dimensions": {"width": image.width, "height": image.height},
                "format": image.format,
                "mode": image.mode,
                "date_taken": exif_data.get("DateTimeOriginal") or exif_data.get("DateTime"),
                "device": exif_data.get("Model"),
                "make": exif_data.get("Make"),
                "gps": gps if gps else None,
                "raw_exif_fields": len(exif_data),
            }

            logger.info(f"extract_exif: {len(exif_data)} EXIF fields found")
            return self._ok(result)
        except Exception as e:
            logger.error(f"extract_exif failed: {e}")
            return self._err(f"EXIF extraction failed: {e}")
