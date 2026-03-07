"""
Files API — artifact upload, download, listing, and deletion.

Endpoints:
    POST   /files/upload        — Upload a file (scope-aware)
    GET    /files/              — List artifacts by scope (personal/department/company)
    GET    /files/{file_id}     — Download/stream a file (scope-aware access check)
    DELETE /files/{file_id}     — Delete an artifact record (scope-aware RBAC)

Access rules:
    personal  — owner only
    department — any user in the same department
    company   — any authenticated user can read; Management dept can upload/delete
"""

import logging
import os
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Query, UploadFile, File, status
from pydantic import BaseModel
from fastapi.responses import FileResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.context.artifact_manager import (
    get_artifact,
    list_artifacts,
    register_artifact,
    sync_user_artifacts,
    get_user_artifacts_dir,
    get_dept_artifacts_dir,
    get_company_artifacts_dir,
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
    "text/markdown",    # .md files
    "text/x-markdown",  # Safari / older browsers
}


# ── RBAC helpers ──────────────────────────────────────────────────────────────

def _is_management(user: dict) -> bool:
    return (user.get("department") or "").lower() == "management"


def _can_write(scope: str, user: dict) -> bool:
    if scope in ("personal", "department"):
        return True
    if scope == "company":
        return _is_management(user)
    return False


def _check_read_access(artifact: dict, current_user: dict):
    """Raise 403/404 if current_user cannot read the artifact."""
    scope = artifact.get("scope", "personal")
    if scope == "personal":
        if artifact["user_id"] != current_user["user_id"]:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                                detail="File not found or access denied")
    elif scope == "department":
        if (artifact.get("department") or "").lower() != (current_user.get("department") or "").lower():
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="Access denied")
    # company — any authenticated user can read (no extra check)


def _check_delete_access(artifact: dict, current_user: dict):
    """Raise 403/404 if current_user cannot delete the artifact."""
    scope = artifact.get("scope", "personal")
    if scope == "personal":
        if artifact["user_id"] != current_user["user_id"]:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                                detail="File not found or access denied")
    elif scope == "department":
        if (artifact.get("department") or "").lower() != (current_user.get("department") or "").lower():
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="Access denied")
    elif scope == "company":
        if not _is_management(current_user):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="Only the Management department can delete company files")


def _check_rename_access(artifact: dict, current_user: dict):
    """Raise 403 if current_user is not the file creator (any scope)."""
    if artifact["user_id"] != current_user["user_id"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Only the file creator can rename this file")


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/upload")
async def upload_file(
    media_file: UploadFile = File(...),
    scope: str = Form("personal"),            # personal | department | company
    folder_id: Optional[str] = Form(None),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload a file for future AI processing.

    The file is saved to the correct scope directory and registered in DB.
    Returns the artifact ID which can be used as input to /chat/send-media.
    """
    # Validate scope
    if scope not in ("personal", "department", "company"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="scope must be personal, department, or company")

    # RBAC check
    if not _can_write(scope, current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="You do not have permission to upload to this scope")

    # MIME type validation
    content_type = media_file.content_type or ""
    allowed = any(content_type.startswith(prefix) for prefix in _ALLOWED_MIME_PREFIXES)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file type: {content_type}",
        )

    dept = current_user.get("department", "general")
    email = current_user.get("email", current_user["user_id"])

    if scope == "department":
        upload_dir = get_dept_artifacts_dir(dept)
    elif scope == "company":
        upload_dir = get_company_artifacts_dir()
    else:
        upload_dir = get_user_artifacts_dir(dept, email)

    safe_filename = Path(media_file.filename or "upload").name
    save_path = upload_dir / safe_filename

    file_bytes = await media_file.read()
    try:
        save_path.write_bytes(file_bytes)
    except Exception as e:
        logger.error(f"Failed to save upload: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save uploaded file",
        )

    file_type = content_type.split("/")[-1].split(";")[0] or "file"

    artifact = await register_artifact(
        db=db,
        user_id=current_user["user_id"],
        session_id=None,
        filename=safe_filename,
        file_path=str(save_path),
        file_type=file_type,
        scope=scope,
        folder_id=folder_id if folder_id else None,
        department=dept,
    )
    await db.commit()

    return {
        "artifact_id": artifact["id"],
        "filename": safe_filename,
        "file_type": file_type,
        "scope": scope,
        "size_bytes": len(file_bytes),
        "download_url": artifact["download_url"],
    }


@router.get("/")
async def list_files(
    scope: str = Query("personal", pattern="^(personal|department|company)$"),
    folder_id: Optional[str] = Query(None),
    limit: int = 50,
    offset: int = 0,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List artifacts for the current user by scope and optional folder."""
    uid = current_user["user_id"]
    dept = current_user.get("department", "")
    email = current_user.get("email", "")

    # Auto-sync orphaned disk files into DB (personal scope only)
    if scope == "personal" and not folder_id:
        await sync_user_artifacts(db, uid, dept, email)

    artifacts = await list_artifacts(
        db=db,
        scope=scope,
        user_id=uid,
        department=dept,
        folder_id=folder_id,
        limit=limit,
        offset=offset,
    )
    return {"artifacts": artifacts, "count": len(artifacts)}


@router.get("/search")
async def search_files(
    q: str = Query(..., min_length=1),
    limit: int = Query(30, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Search files by name across all scopes accessible to the user."""
    uid = current_user["user_id"]
    dept = current_user.get("department", "")
    pattern = f"%{q}%"
    result = await db.execute(
        text("""
            SELECT a.id, a.filename, a.file_type, a.scope, a.folder_id, a.created_at,
                   a.user_id AS created_by_id, u.name AS creator_name
            FROM artifacts a
            LEFT JOIN users u ON u.id = a.user_id
            WHERE a.filename ILIKE :pat
              AND (
                (a.scope = 'personal' AND a.user_id = :uid)
                OR (a.scope = 'department' AND a.department = :dept)
                OR a.scope = 'company'
              )
            ORDER BY a.created_at DESC
            LIMIT :lim
        """),
        {"pat": pattern, "uid": uid, "dept": dept, "lim": limit},
    )
    rows = result.fetchall()
    results = [
        {
            "id": str(r.id),
            "filename": r.filename,
            "file_type": r.file_type,
            "scope": r.scope,
            "folder_id": str(r.folder_id) if r.folder_id else None,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "creator_name": r.creator_name or "Unknown",
            "created_by_id": str(r.created_by_id),
            "download_url": f"/files/{r.id}",
        }
        for r in rows
    ]
    return {"results": results, "count": len(results)}


@router.get("/{file_id}")
async def get_file(
    file_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Download a generated or uploaded file by artifact ID (scope-aware access check)."""
    artifact = await get_artifact(db, file_id)

    if artifact is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="File not found or access denied")

    _check_read_access(artifact, current_user)

    file_path = artifact["file_path"]
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="File has been removed from storage")

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
    """Delete an artifact record from DB and its physical file from disk (scope-aware RBAC)."""
    from sqlalchemy import text

    artifact = await get_artifact(db, file_id)
    if artifact is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="File not found or access denied")

    _check_delete_access(artifact, current_user)

    file_path = artifact.get("file_path")

    await db.execute(
        text("DELETE FROM artifacts WHERE id = :id"),
        {"id": file_id},
    )
    await db.commit()

    if file_path and os.path.exists(file_path):
        try:
            os.remove(file_path)
            logger.info(f"Deleted file from disk: {file_path}")
        except OSError as e:
            logger.warning(f"Could not delete file from disk: {e}")

    return {"deleted": True, "artifact_id": file_id}


class FileMoveRequest(BaseModel):
    folder_id: Optional[str] = None   # None = move to root (no folder)


@router.patch("/{file_id}/move")
async def move_file(
    file_id: str,
    body: FileMoveRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Move a file to a different folder (or to root if folder_id=None).
    When moving to a folder, the file's scope and department are updated to match
    the target folder (allows cross-scope moves, e.g. personal → department).
    When moving to root (folder_id=None), only folder_id is cleared.
    RBAC: same access rules as delete.
    """
    from sqlalchemy import text as _text
    import uuid as _uuid_lib

    artifact = await get_artifact(db, file_id)
    if artifact is None:
        raise HTTPException(status_code=404, detail="File not found or access denied")

    _check_delete_access(artifact, current_user)

    # Validate target folder (if provided) and fetch its scope/department
    if body.folder_id:
        try:
            target_fid = _uuid_lib.UUID(str(body.folder_id))
        except (ValueError, AttributeError):
            raise HTTPException(status_code=400, detail="Invalid folder_id")

        result = await db.execute(
            _text("SELECT scope, department FROM folders WHERE id = :id"),
            {"id": target_fid},
        )
        folder_row = result.fetchone()
        if folder_row is None:
            raise HTTPException(status_code=404, detail="Target folder not found")

        new_scope = folder_row.scope
        new_dept = folder_row.department

        await db.execute(
            _text("UPDATE artifacts SET folder_id = :fid, scope = :scope, department = :dept WHERE id = :id"),
            {"fid": target_fid, "scope": new_scope, "dept": new_dept, "id": file_id},
        )
    else:
        # Moving to root — clear folder_id only, keep existing scope
        await db.execute(
            _text("UPDATE artifacts SET folder_id = NULL WHERE id = :id"),
            {"id": file_id},
        )

    await db.commit()
    logger.info(f"Moved artifact {file_id} → folder={body.folder_id}")
    return {"moved": True, "artifact_id": file_id, "folder_id": body.folder_id}


class FileRenameRequest(BaseModel):
    filename: str


@router.patch("/{file_id}/rename")
async def rename_file(
    file_id: str,
    body: FileRenameRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Rename a file — creator-only regardless of scope."""
    new_name = body.filename.strip()
    if not new_name or len(new_name) > 255 or '/' in new_name or '\\' in new_name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Invalid filename")
    artifact = await get_artifact(db, file_id)
    if artifact is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="File not found or access denied")
    _check_read_access(artifact, current_user)
    _check_rename_access(artifact, current_user)
    await db.execute(
        text("UPDATE artifacts SET filename = :n WHERE id = :id"),
        {"n": new_name, "id": file_id},
    )
    await db.commit()

    old_path = artifact.get("file_path")
    if old_path:
        old_path = Path(old_path)
        new_path = old_path.parent / new_name
        if old_path.exists():
            try:
                old_path.rename(new_path)
                await db.execute(
                    text("UPDATE artifacts SET file_path = :p WHERE id = :id"),
                    {"p": str(new_path), "id": file_id},
                )
                await db.commit()
                logger.info(f"Renamed file on disk: {old_path} → {new_path}")
            except OSError as e:
                logger.warning(f"Could not rename file on disk: {e}")

    return {"renamed": True, "artifact_id": file_id, "filename": new_name}


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
