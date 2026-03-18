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
import magic as _magic
import os
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Query, UploadFile, File, status
from pydantic import BaseModel
from fastapi.responses import FileResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.core.rbac import VALID_DEPARTMENTS
from app.context.artifact_manager import (
    get_artifact,
    get_artifacts_dir,
    list_artifacts,
    register_artifact,
    sync_user_artifacts,
    sync_dept_artifacts,
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
    "application/vnd.ms-",                             # older Office formats (.xls, .ppt variants)
    "application/msword",                              # .doc (Word 97-2003)
    "application/x-mspowerpoint",                      # .ppt (some browsers)
    "text/plain", "text/csv",
    "text/markdown",    # .md files
    "text/x-markdown",  # Safari / older browsers
}

_MAX_UPLOAD_BYTES = 100 * 1024 * 1024   # 100 MB


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
        # Management can read files from any department
        if not _is_management(current_user):
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

    # MIME type validation (client-declared)
    content_type = media_file.content_type or ""
    allowed = any(content_type.startswith(prefix) for prefix in _ALLOWED_MIME_PREFIXES)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file type: {content_type}",
        )

    # Size pre-check from Content-Length (advisory — full check comes after read)
    if media_file.size and media_file.size > _MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File too large (max 100 MB)",
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

    # Post-read size check (guards against missing Content-Length)
    if len(file_bytes) > _MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File too large (max 100 MB)",
        )

    # Server-side MIME validation using libmagic (defeats Content-Type spoofing)
    actual_mime = _magic.from_buffer(file_bytes[:2048], mime=True)
    if not any(actual_mime.startswith(prefix) for prefix in _ALLOWED_MIME_PREFIXES):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"File content does not match declared type ({actual_mime})",
        )
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

    # Image analysis — run inline for image uploads; result included in response (not stored in DB)
    image_analysis: dict = {}
    if actual_mime.startswith("image/"):
        try:
            from app.input.image_handler import handle_image
            from app.core.config import get_config
            config = get_config()
            _task = {"_config": config, "message": ""}
            result = await handle_image(_task, file_bytes, safe_filename)
            mc = result.get("media_content", {})
            image_analysis = {
                "ocr_text": mc.get("ocr_text", ""),
                "description": mc.get("description", ""),
            }
        except Exception as exc:
            logger.warning(f"Image analysis failed for {safe_filename}: {exc}")

    response_data: dict = {
        "artifact_id": artifact["id"],
        "filename": safe_filename,
        "file_type": file_type,
        "scope": scope,
        "size_bytes": len(file_bytes),
        "download_url": artifact["download_url"],
    }
    if actual_mime.startswith("image/"):
        response_data["image_analysis"] = image_analysis
    return response_data


@router.get("/departments")
async def list_departments(
    current_user: dict = Depends(get_current_user),
):
    """Return all valid department names (Management only)."""
    if not _is_management(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Only the Management department can access this endpoint")
    # Use the canonical department list — not a DB query — so all depts always appear
    # even if no users are registered in a given department yet.
    departments = sorted(VALID_DEPARTMENTS - {"management"}) + ["management"]
    return {"departments": departments}


@router.get("/")
async def list_files(
    scope: str = Query("personal", pattern="^(personal|department|company)$"),
    folder_id: Optional[str] = Query(None),
    dept: Optional[str] = Query(None),
    limit: int = 50,
    offset: int = 0,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List artifacts for the current user by scope and optional folder.

    Management users may pass ?dept=<name> to list files from any department.
    For non-management users the dept param is silently ignored.
    """
    uid = current_user["user_id"]
    user_dept = current_user.get("department", "")
    email = current_user.get("email", "")

    # Management can request a specific department; others always use their own
    effective_dept = user_dept
    if scope == "department" and dept and _is_management(current_user):
        effective_dept = dept

    # Auto-sync orphaned disk files into DB
    if scope == "personal" and not folder_id:
        await sync_user_artifacts(db, uid, user_dept, email)
    elif scope == "department" and not folder_id:
        await sync_dept_artifacts(db, uid, effective_dept)

    artifacts = await list_artifacts(
        db=db,
        scope=scope,
        user_id=uid,
        department=effective_dept,
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

    # Management sees department files from ALL departments in search results
    if _is_management(current_user):
        dept_clause = "OR (a.scope = 'department')"
        params: dict = {"pat": pattern, "uid": uid, "lim": limit}
    else:
        dept_clause = "OR (a.scope = 'department' AND a.department = :dept)"
        params = {"pat": pattern, "uid": uid, "dept": dept, "lim": limit}

    result = await db.execute(
        text(f"""
            SELECT a.id, a.filename, a.file_type, a.scope, a.folder_id, a.created_at,
                   a.user_id AS created_by_id, u.name AS creator_name
            FROM artifacts a
            LEFT JOIN users u ON u.id = a.user_id
            WHERE a.filename ILIKE :pat
              AND (
                (a.scope = 'personal' AND a.user_id = :uid)
                {dept_clause}
                OR a.scope = 'company'
              )
            ORDER BY a.created_at DESC
            LIMIT :lim
        """),
        params,
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


@router.get("/storage-stats")
async def get_storage_stats(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return total disk usage (bytes) and count of personal artifacts for the current user."""
    user_id = current_user["user_id"]
    result = await db.execute(
        text("SELECT file_path FROM artifacts WHERE user_id = :uid AND scope = 'personal'"),
        {"uid": user_id},
    )
    rows = result.fetchall()
    total_bytes = 0
    for row in rows:
        try:
            total_bytes += os.path.getsize(row.file_path)
        except (OSError, TypeError):
            pass  # File missing or path null — skip
    return {"total_bytes": total_bytes, "count": len(rows)}


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

    # Defense-in-depth: ensure the DB-stored path stays within the artifact root
    resolved = Path(file_path).resolve()
    artifact_root = get_artifacts_dir().resolve()
    if not str(resolved).startswith(str(artifact_root)):
        logger.warning(f"get_file: path escape attempt blocked: {file_path!r}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="File not found or access denied")

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
        # Bounds-check before any disk operation
        resolved = Path(file_path).resolve()
        artifact_root = get_artifacts_dir().resolve()
        if not str(resolved).startswith(str(artifact_root)):
            logger.warning(f"delete_file: path escape attempt blocked: {file_path!r}")
            file_path = None  # skip disk delete; DB record already removed above

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
    if (
        not new_name
        or len(new_name) > 255
        or '/' in new_name
        or '\\' in new_name
        or '\x00' in new_name
        or new_name.startswith('.')
    ):
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
        # Bounds check: resolved new_path must stay inside the artifact root
        artifact_root = get_artifacts_dir().resolve()
        if not str(new_path.resolve()).startswith(str(artifact_root)):
            logger.warning(f"rename_file: path escape attempt blocked: {new_path!r}")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="Invalid filename")
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
