"""
Image Handler — OCR and vision analysis for uploaded images.

Processing pipeline:
  1. Base64-encode image bytes
  2. OCR text extraction via ImageOps.ocr_image (Tesseract)
  3. Vision analysis via ImageOps.analyze_image (Claude Vision)
  4. Combine results into extracted_text for the LLM
"""

import base64
import logging
import os

logger = logging.getLogger("mezzofy.input.image")


async def handle_image(
    task: dict,
    file_bytes: bytes,
    filename: str,
) -> dict:
    """
    Process an uploaded image: OCR + vision analysis.

    Args:
        task:       Task dict with _config and optional message.
        file_bytes: Raw image bytes (JPEG, PNG, HEIC, WebP).
        filename:   Original filename for extension detection.

    Returns:
        Task dict enriched with extracted_text containing OCR text
        and vision description, plus media_content metadata.
    """
    config = task.get("_config", {})

    image_b64 = base64.b64encode(file_bytes).decode()

    from app.tools.media.image_ops import ImageOps
    image_ops = ImageOps(config)

    # OCR
    ocr_text = ""
    try:
        ocr_result = await image_ops.execute("ocr_image", image_bytes=image_b64)
        if ocr_result.get("success"):
            ocr_text = (ocr_result.get("output") or "").strip()
    except Exception as e:
        logger.warning(f"OCR failed for {filename}: {e}")

    # Vision analysis
    description = ""
    try:
        analyze_result = await image_ops.execute("analyze_image", image_bytes=image_b64)
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
    user_msg = (task.get("message") or "").strip()
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
