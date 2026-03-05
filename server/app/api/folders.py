"""
Folders API — create, list, rename, and delete file folders.

Endpoints:
    GET    /folders/              — List folders visible to the current user by scope
    POST   /folders/              — Create a folder (RBAC-checked)
    PUT    /folders/{folder_id}   — Rename a folder (RBAC-checked)
    DELETE /folders/{folder_id}   — Delete a folder; artifacts revert to root (RBAC-checked)

Access rules:
    personal  — owner only (owner_id = current_user.id)
    department — any user in the same department
    company   — any authenticated user can read; Management dept can write/delete
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db

logger = logging.getLogger("mezzofy.api.folders")
router = APIRouter(tags=["folders"])

_VALID_SCOPES = {"personal", "department", "company"}


# ── Request / Response models ─────────────────────────────────────────────────

class FolderCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    scope: str = Field(..., pattern="^(personal|department|company)$")


class FolderRename(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)


# ── RBAC helpers ──────────────────────────────────────────────────────────────

def _is_management(user: dict) -> bool:
    return (user.get("department") or "").lower() == "management"


def _can_write(scope: str, user: dict) -> bool:
    """Return True if the user has write access to the given scope."""
    if scope == "personal":
        return True
    if scope == "department":
        return True
    if scope == "company":
        return _is_management(user)
    return False


def _folder_visibility_clause(scope: str, user: dict) -> tuple[str, dict]:
    """
    Return (WHERE clause fragment, params dict) to filter folders
    that the current user is allowed to see.
    """
    if scope == "personal":
        return "scope = 'personal' AND owner_id = :uid", {"uid": user["user_id"]}
    if scope == "department":
        return "scope = 'department' AND department = :dept", {"dept": user.get("department", "")}
    # company — everyone can see
    return "scope = 'company'", {}


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/")
async def list_folders(
    scope: str = Query("personal", pattern="^(personal|department|company)$"),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List folders visible to the current user for the given scope."""
    where, params = _folder_visibility_clause(scope, current_user)
    result = await db.execute(
        text(f"SELECT id, name, scope, department, created_at FROM folders WHERE {where} ORDER BY name"),
        params,
    )
    folders = [
        {
            "id": str(row.id),
            "name": row.name,
            "scope": row.scope,
            "department": row.department,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in result.fetchall()
    ]
    return {"folders": folders, "count": len(folders)}


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_folder(
    body: FolderCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new folder in the specified scope (RBAC-checked)."""
    if not _can_write(body.scope, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to create folders in this scope",
        )

    folder_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    dept = current_user.get("department", "")

    await db.execute(
        text("""
            INSERT INTO folders (id, name, scope, owner_id, department, created_at)
            VALUES (:id, :name, :scope, :owner_id, :dept, :now)
        """),
        {
            "id": folder_id,
            "name": body.name,
            "scope": body.scope,
            "owner_id": current_user["user_id"] if body.scope == "personal" else None,
            "dept": dept if body.scope == "department" else (dept if body.scope == "company" else None),
            "now": now,
        },
    )
    await db.commit()

    logger.info(f"Created folder '{body.name}' scope={body.scope} by user={current_user['user_id']}")
    return {
        "id": folder_id,
        "name": body.name,
        "scope": body.scope,
        "created_at": now.isoformat(),
    }


@router.put("/{folder_id}")
async def rename_folder(
    folder_id: str,
    body: FolderRename,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Rename a folder (RBAC-checked)."""
    # Fetch existing folder
    result = await db.execute(
        text("SELECT id, name, scope, owner_id, department FROM folders WHERE id = :id"),
        {"id": folder_id},
    )
    folder = result.fetchone()
    if folder is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Folder not found")

    _assert_write_access(folder, current_user)

    await db.execute(
        text("UPDATE folders SET name = :name WHERE id = :id"),
        {"name": body.name, "id": folder_id},
    )
    await db.commit()

    logger.info(f"Renamed folder {folder_id} to '{body.name}' by user={current_user['user_id']}")
    return {"id": folder_id, "name": body.name, "scope": folder.scope}


@router.delete("/{folder_id}")
async def delete_folder(
    folder_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Delete a folder (RBAC-checked).
    Artifacts inside the folder are NOT deleted — they revert to root (folder_id = NULL).
    """
    result = await db.execute(
        text("SELECT id, name, scope, owner_id, department FROM folders WHERE id = :id"),
        {"id": folder_id},
    )
    folder = result.fetchone()
    if folder is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Folder not found")

    _assert_write_access(folder, current_user)

    # Orphan artifacts (set folder_id = NULL) — they appear at root level
    await db.execute(
        text("UPDATE artifacts SET folder_id = NULL WHERE folder_id = :fid"),
        {"fid": folder_id},
    )
    await db.execute(
        text("DELETE FROM folders WHERE id = :id"),
        {"id": folder_id},
    )
    await db.commit()

    logger.info(f"Deleted folder {folder_id} ('{folder.name}') by user={current_user['user_id']}")
    return {"deleted": True, "folder_id": folder_id}


# ── Internal helper ───────────────────────────────────────────────────────────

def _assert_write_access(folder, current_user: dict):
    """Raise 403 if the current user cannot modify the given folder row."""
    scope = folder.scope
    if scope == "personal":
        if str(folder.owner_id) != current_user["user_id"]:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    elif scope == "department":
        if (folder.department or "").lower() != (current_user.get("department") or "").lower():
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    elif scope == "company":
        if not _is_management(current_user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the Management department can modify company folders",
            )
