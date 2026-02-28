"""
File Handler — text extraction from uploaded documents.

Supported formats and extraction libraries:
  PDF   → PDFOps.extract_text_from_pdf (pdfplumber)
  DOCX  → python-docx
  PPTX  → python-pptx (slide text + speaker notes)
  CSV   → pandas (first 100 rows as string)
  XLSX  → pandas
  TXT   → plain UTF-8 read
"""

import logging
import os
import tempfile
from typing import Optional

logger = logging.getLogger("mezzofy.input.file")

# Truncate extracted text at this many chars to avoid overwhelming LLM context
_MAX_EXTRACTED_CHARS = 6000


async def handle_file(
    task: dict,
    file_bytes: bytes,
    filename: str,
) -> dict:
    """
    Extract text from an uploaded document file.

    Args:
        task:       Task dict with _config and optional message.
        file_bytes: Raw document bytes.
        filename:   Original filename (used for extension detection).

    Returns:
        Task dict enriched with extracted_text from the document content.
    """
    config = task.get("_config", {})
    ext = os.path.splitext(filename)[1].lower()

    tmp_path: Optional[str] = None
    try:
        with tempfile.NamedTemporaryFile(suffix=ext or ".bin", delete=False) as tmp:
            tmp.write(file_bytes)
            tmp_path = tmp.name

        extracted = await _extract_by_extension(ext, tmp_path, config)
        extracted = extracted[:_MAX_EXTRACTED_CHARS]

        parts = []
        if extracted:
            parts.append(
                f"[Document content from '{filename}':\n{extracted}]"
            )
        user_msg = (task.get("message") or "").strip()
        if user_msg:
            parts.append(user_msg)

        return {
            **task,
            "input_type": "file",
            "extracted_text": (
                "\n\n".join(parts)
                if parts
                else f"[File '{filename}' uploaded — no text extracted]"
            ),
            "media_content": {
                "filename": filename,
                "extension": ext,
                "extracted_chars": len(extracted),
            },
            "input_summary": (
                f"File: {filename} ({len(extracted):,} chars extracted)"
            ),
        }

    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass


async def _extract_by_extension(ext: str, file_path: str, config: dict) -> str:
    """Route to the correct extraction method by file extension."""

    if ext == ".pdf":
        try:
            from app.tools.document.pdf_ops import PDFOps
            ops = PDFOps(config)
            result = await ops.execute("extract_text_from_pdf", file_path=file_path)
            return result.get("output", "") if result.get("success") else ""
        except Exception as e:
            logger.warning(f"PDF extraction failed: {e}")
            return ""

    if ext == ".docx":
        try:
            import docx as python_docx
            doc = python_docx.Document(file_path)
            return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
        except Exception as e:
            logger.warning(f"DOCX extraction failed: {e}")
            return ""

    if ext == ".pptx":
        try:
            from pptx import Presentation
            prs = Presentation(file_path)
            texts = []
            for slide in prs.slides:
                for shape in slide.shapes:
                    if hasattr(shape, "text") and shape.text.strip():
                        texts.append(shape.text.strip())
            return "\n".join(texts)
        except Exception as e:
            logger.warning(f"PPTX extraction failed: {e}")
            return ""

    if ext == ".csv":
        try:
            import pandas as pd
            df = pd.read_csv(file_path, nrows=100)
            return df.to_string(index=False)
        except Exception as e:
            logger.warning(f"CSV extraction failed: {e}")
            return ""

    if ext in (".xlsx", ".xls"):
        try:
            import pandas as pd
            df = pd.read_excel(file_path, nrows=100)
            return df.to_string(index=False)
        except Exception as e:
            logger.warning(f"Excel extraction failed: {e}")
            return ""

    if ext in (".txt", ".md", ".rst"):
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                return f.read()
        except Exception as e:
            logger.warning(f"Text read failed: {e}")
            return ""

    logger.warning(f"No extractor for extension: {ext!r}")
    return ""
