"""
Files API — artifact upload, download, and listing.

Endpoints:
    POST /files/upload        — Upload a file for AI processing
    GET  /files/              — List user's generated artifacts
    GET  /files/{file_id}     — Download/stream a generated file
    DELETE /files/{file_id}   — Delete an artifact record (not the file)

All endpoints require JWT authentication via Depends(get_current_user).
File access is ownership-scoped: users can only access their own artifacts.
"""

import logging
import os
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.context.artifact_manager import (
    get_artifact,
    list_user_artifacts,
    register_artifact,
    get_artifacts_dir,
)

logger = logging.getLogger("mezzofy.api.files")
router = APIRouter(tags=["files"])

# Allowed MIME types for upload
_ALLOWED_MIME_PREFIXES = {
    "image/", "video/", "audio/",
    "application/pdf",
    "application/vnd.openxmlformats-officedocument",  # DOCX, PPTX, XLSX
    "application/vnd.ms-",                             # older Office formats
    "text/plain", "text/csv",
}


@router.post("/upload")
async def upload_file(
    media_file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload a file for future AI processing.

    The uploaded file is saved to the artifacts directory and registered in DB.
    Returns the artifact ID which can be used as input to /chat/send-media.
    """
    # Basic MIME type validation
    content_type = media_file.content_type or ""
    allowed = any(
        content_type.startswith(prefix) for prefix in _ALLOWED_MIME_PREFIXES
    )
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file type: {content_type}",
        )

    # Save to artifacts directory
    artifacts_dir = get_artifacts_dir()
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    safe_filename = Path(media_file.filename or "upload").name
    save_path = artifacts_dir / f"{current_user['user_id']}_{safe_filename}"

    file_bytes = await media_file.read()
    try:
        save_path.write_bytes(file_bytes)
    except Exception as e:
        logger.error(f"Failed to save upload: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save uploaded file",
        )

    # Infer file_type from MIME
    file_type = content_type.split("/")[-1].split(";")[0] or "file"

    # Register in DB
    artifact = await register_artifact(
        db=db,
        user_id=current_user["user_id"],
        session_id="",  # standalone upload — not tied to a session yet
        filename=safe_filename,
        file_path=str(save_path),
        file_type=file_type,
    )

    return {
        "artifact_id": artifact["id"],
        "filename": safe_filename,
        "file_type": file_type,
        "size_bytes": len(file_bytes),
        "download_url": artifact["download_url"],
    }


@router.get("/")
async def list_files(
    limit: int = 50,
    offset: int = 0,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all artifacts (uploads + generated files) for the current user."""
    artifacts = await list_user_artifacts(
        db, current_user["user_id"], limit=limit, offset=offset
    )
    return {"artifacts": artifacts, "count": len(artifacts)}


@router.get("/{file_id}")
async def get_file(
    file_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Download a generated or uploaded file by artifact ID."""
    artifact = await get_artifact(db, file_id, current_user["user_id"])

    if artifact is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found or access denied",
        )

    file_path = artifact["file_path"]
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File has been removed from storage",
        )

    return FileResponse(
        path=file_path,
        filename=artifact["filename"],
        media_type=_mime_for_type(artifact.get("file_type", "file")),
    )


@router.delete("/{file_id}")
async def delete_file(
    file_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Delete an artifact record from DB.

    The underlying file is NOT deleted from disk (preserves audit trail).
    Returns 404 if the artifact does not belong to the current user.
    """
    from sqlalchemy import text

    result = await db.execute(
        text(
            "DELETE FROM artifacts WHERE id = :id AND user_id = :uid RETURNING id"
        ),
        {"id": file_id, "uid": current_user["user_id"]},
    )
    deleted = result.fetchone()
    if deleted is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found or access denied",
        )

    return {"deleted": True, "artifact_id": file_id}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _mime_for_type(file_type: str) -> str:
    """Map a file_type string to a MIME type for FileResponse."""
    _map = {
        "pdf": "application/pdf",
        "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "csv": "text/csv",
        "txt": "text/plain",
        "mp3": "audio/mpeg",
        "mp4": "video/mp4",
    }
    return _map.get(file_type.lower(), "application/octet-stream")
