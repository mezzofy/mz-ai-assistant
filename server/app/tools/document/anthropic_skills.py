"""
anthropic_skills.py — Thin wrapper for Anthropic Agent Skills document generation.

Exposes convenience functions for generating PPTX, XLSX, PDF, and DOCX files
using Anthropic's native Agent Skills API (beta: skills-2025-10-02).

Primary document generation path:
  → anthropic_skills.generate_pptx / generate_xlsx / generate_pdf / generate_docx
  → llm_manager.generate_document_with_skill()
  → Anthropic Skills API (pause_turn loop)
  → artifact_manager.download_from_anthropic()

Fallback: if skill_result["success"] is False, callers should fall back to
legacy pdf_ops / pptx_ops / docx_ops modules.

NOTE: These functions return the raw skill result dict (file_ids, container_id, etc.).
To download the files and register them in the artifacts table, call:
  artifact_manager.download_from_anthropic(db, file_id, user_id, session_id, skill_id, ...)
"""

import logging

from app.llm import llm_manager

logger = logging.getLogger("mezzofy.tools.document.anthropic_skills")


async def generate_pptx(
    prompt: str,
    context_data: str = None,
    task_context: dict = None,
    existing_container_id: str = None,
) -> dict:
    """
    Generate a PowerPoint presentation using Anthropic's pptx Skill.

    Args:
        prompt:                Slide generation instruction (topic, audience, structure, etc.)
        context_data:          Source data / content to base slides on (JSON, text, report data)
        task_context:          Agent task dict for system prompt and usage tracking
        existing_container_id: Resume an existing container (multi-turn use case)

    Returns:
        {
          success:      bool,
          file_ids:     list[str],   # Anthropic Files API IDs — download via artifact_manager
          container_id: str | None,
          text:         str,         # Any Claude explanation alongside the file
          usage:        dict,
          error:        str | None,
        }
    """
    mgr = llm_manager.get()
    result = await mgr.generate_document_with_skill(
        skill_id="pptx",
        prompt=prompt,
        context_data=context_data,
        task_context=task_context,
        existing_container_id=existing_container_id,
    )
    logger.info(
        f"generate_pptx: success={result['success']} "
        f"file_ids={result['file_ids']} "
        f"input_tokens={result['usage']['input_tokens']}"
    )
    return result


async def generate_xlsx(
    prompt: str,
    context_data: str = None,
    task_context: dict = None,
    existing_container_id: str = None,
) -> dict:
    """
    Generate an Excel spreadsheet using Anthropic's xlsx Skill.

    Args:
        prompt:                Spreadsheet generation instruction (structure, formulas, data layout)
        context_data:          Source data to populate the spreadsheet (CSV, JSON, report data)
        task_context:          Agent task dict for system prompt and usage tracking
        existing_container_id: Resume an existing container (multi-turn use case)

    Returns:
        {
          success:      bool,
          file_ids:     list[str],
          container_id: str | None,
          text:         str,
          usage:        dict,
          error:        str | None,
        }
    """
    mgr = llm_manager.get()
    result = await mgr.generate_document_with_skill(
        skill_id="xlsx",
        prompt=prompt,
        context_data=context_data,
        task_context=task_context,
        existing_container_id=existing_container_id,
    )
    logger.info(
        f"generate_xlsx: success={result['success']} "
        f"file_ids={result['file_ids']} "
        f"input_tokens={result['usage']['input_tokens']}"
    )
    return result


async def generate_pdf(
    prompt: str,
    context_data: str = None,
    task_context: dict = None,
    existing_container_id: str = None,
) -> dict:
    """
    Generate a PDF document using Anthropic's pdf Skill.

    Args:
        prompt:                PDF generation instruction (report type, structure, branding, etc.)
        context_data:          Source data / content for the document
        task_context:          Agent task dict for system prompt and usage tracking
        existing_container_id: Resume an existing container (multi-turn use case)

    Returns:
        {
          success:      bool,
          file_ids:     list[str],
          container_id: str | None,
          text:         str,
          usage:        dict,
          error:        str | None,
        }
    """
    mgr = llm_manager.get()
    result = await mgr.generate_document_with_skill(
        skill_id="pdf",
        prompt=prompt,
        context_data=context_data,
        task_context=task_context,
        existing_container_id=existing_container_id,
    )
    logger.info(
        f"generate_pdf: success={result['success']} "
        f"file_ids={result['file_ids']} "
        f"input_tokens={result['usage']['input_tokens']}"
    )
    return result


async def generate_docx(
    prompt: str,
    context_data: str = None,
    task_context: dict = None,
    existing_container_id: str = None,
) -> dict:
    """
    Generate a Word document using Anthropic's docx Skill.

    Args:
        prompt:                DOCX generation instruction (document type, structure, tone)
        context_data:          Source content (contract clauses, policy text, report data, etc.)
        task_context:          Agent task dict for system prompt and usage tracking
        existing_container_id: Resume an existing container (multi-turn use case)

    Returns:
        {
          success:      bool,
          file_ids:     list[str],
          container_id: str | None,
          text:         str,
          usage:        dict,
          error:        str | None,
        }
    """
    mgr = llm_manager.get()
    result = await mgr.generate_document_with_skill(
        skill_id="docx",
        prompt=prompt,
        context_data=context_data,
        task_context=task_context,
        existing_container_id=existing_container_id,
    )
    logger.info(
        f"generate_docx: success={result['success']} "
        f"file_ids={result['file_ids']} "
        f"input_tokens={result['usage']['input_tokens']}"
    )
    return result
