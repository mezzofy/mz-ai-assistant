"""
Image Handler — Upload image to Anthropic Files API for native vision analysis.

Processing pipeline (primary):
  1. Upload image bytes to Anthropic Files API → get file_id
  2. Store file_id as anthropic_file_id in task
  3. LLMManager builds an image block from the file_id → Claude sees the image directly

Fallback (if Files API upload fails):
  1. Base64-encode image bytes
  2. Vision analysis via ImageOps.analyze_image (Claude Vision inline)
  3. OCR text extraction via ImageOps.ocr_image (Tesseract — optional)
  4. Combine results into extracted_text for the LLM
"""

import asyncio
import base64
import logging
import os
from typing import Optional

logger = logging.getLogger("mezzofy.input.image")

_IMAGE_MIME_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".bmp": "image/bmp",
    ".tiff": "image/tiff",
    ".tif": "image/tiff",
    ".heic": "image/heic",
}


def _upload_image_to_files_api_sync(
    file_bytes: bytes, filename: str, mime_type: str, config: dict
) -> Optional[str]:
    """
    Upload image bytes to Anthropic Files API (synchronous).

    Returns the file_id string on success, or None on failure.
    Intended to be called via run_in_executor from async code.
    """
    try:
        import anthropic

        api_key = config.get("llm", {}).get("claude", {}).get("api_key", "")
        if not api_key:
            logger.warning("Files API image upload skipped: no Claude API key in config")
            return None

        client = anthropic.Anthropic(api_key=api_key)
        response = client.beta.files.upload(
            file=(filename, file_bytes, mime_type),
        )
        logger.info(
            f"Files API image upload succeeded: file_id={response.id} filename={filename!r}"
        )
        return response.id
    except Exception as e:
        logger.warning(f"Files API image upload failed for {filename!r}: {e}")
        return None


async def handle_image(
    task: dict,
    file_bytes: bytes,
    filename: str,
) -> dict:
    """
    Process an uploaded image via Anthropic Files API (primary) or inline base64 (fallback).

    Args:
        task:       Task dict with _config and optional message.
        file_bytes: Raw image bytes (JPEG, PNG, HEIC, WebP, etc.).
        filename:   Original filename for extension and MIME type detection.

    Returns:
        Task dict enriched with anthropic_file_id (Files API path) or
        extracted_text (fallback path), plus media_content metadata.
    """
    config = task.get("_config", {})
    ext = os.path.splitext(filename)[1].lower()
    mime_type = _IMAGE_MIME_TYPES.get(ext, "image/jpeg")
    user_msg = (task.get("message") or "").strip()

    # ── Primary path: Anthropic Files API ─────────────────────────────────────
    loop = asyncio.get_event_loop()
    file_id = await loop.run_in_executor(
        None, _upload_image_to_files_api_sync, file_bytes, filename, mime_type, config
    )
    if file_id:
        return {
            **task,
            "input_type": "image",
            "anthropic_file_id": file_id,
            "anthropic_file_name": filename,
            "extracted_text": user_msg or "Please analyze this image.",
            "media_content": {"filename": filename, "extension": ext, "mime_type": mime_type},
            "input_summary": f"Image: {filename} (uploaded via Files API)",
        }
    # ── End Files API path ────────────────────────────────────────────────────

    logger.warning(f"handle_image: Files API upload failed for {filename!r} — falling back to inline vision")

    # ── Fallback: inline base64 vision analysis ────────────────────────────────
    image_b64 = base64.b64encode(file_bytes).decode()

    from app.tools.media.image_ops import ImageOps
    image_ops = ImageOps(config)

    # OCR (optional — Tesseract may not be installed)
    ocr_text = ""
    try:
        ocr_result = await image_ops.execute("ocr_image", image_bytes=image_b64)
        if ocr_result.get("success"):
            ocr_text = (ocr_result.get("output") or "").strip()
    except Exception as e:
        logger.warning(f"OCR failed for {filename}: {e}")

    # Vision analysis via inline base64
    description = ""
    try:
        vision_prompt = user_msg or "Describe what you see in this image in detail."
        analyze_result = await image_ops.execute("analyze_image", image_bytes=image_b64, prompt=vision_prompt)
        if analyze_result.get("success"):
            description = (analyze_result.get("output") or "").strip()
    except Exception as e:
        logger.warning(f"Vision analysis failed for {filename}: {e}")

    # Build extracted_text for LLM
    parts = []
    if description:
        parts.append(f"[Image description: {description}]")
    if ocr_text:
        parts.append(f"[Extracted text from image: {ocr_text}]")
    if user_msg:
        parts.append(user_msg)

    extracted_text = (
        "\n".join(parts) if parts else "[Image uploaded — no content extracted]"
    )

    return {
        **task,
        "input_type": "image",
        "extracted_text": extracted_text,
        "media_content": {
            "filename": filename,
            "ocr_text": ocr_text,
            "description": description,
        },
        "input_summary": (
            f"Image: {filename} — {description[:100]}"
            if description
            else f"Image: {filename}"
        ),
    }
