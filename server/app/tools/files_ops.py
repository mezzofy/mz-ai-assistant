"""
Files Tool — Search files and documents in the user's accessible folders.

Tools provided:
    search_user_files  — Keyword search over the artifacts table, scoped by user role

Scope access rules:
  - All users:    personal (own) files + company-wide files
  - Management:   + department files from ALL departments
  - Others:       + department files from their own department only

Security rules:
  - Access is enforced server-side using ContextVar values set by router.py
  - All DB queries use parameterized SQLAlchemy text() — no string interpolation
  - Filename ILIKE search is safe: value bound via params dict
"""

import logging
from typing import Optional

from app.core.user_context import get_user_dept, get_user_id, get_user_role
from app.tools.base_tool import BaseTool

logger = logging.getLogger("mezzofy.tools.files")

_MANAGEMENT_ROLES = {"manager", "admin", "superadmin", "management"}

# Maximum rows returned per search
_MAX_RESULTS = 50


class FilesOps(BaseTool):
    """File discovery tool — scope-aware search over user-accessible artifacts."""

    def get_tools(self) -> list[dict]:
        return [
            {
                "name": "search_user_files",
                "description": (
                    "Search files and documents in the user's accessible folders "
                    "(personal, department, company). Use this when the user asks about "
                    "information that might be in their files, documents, or folders "
                    "(e.g. 'check the SLA', 'find our pricing doc', 'look up the contract'). "
                    "Returns a list of matching files with their paths so you can read them."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": (
                                "Keyword or topic to search for, matched against filenames. "
                                "E.g. 'SLA', 'pricing', 'contract', 'onboarding'."
                            ),
                        },
                        "limit": {
                            "type": "integer",
                            "description": f"Maximum number of results to return (default: 10, max: {_MAX_RESULTS}).",
                            "default": 10,
                        },
                    },
                    "required": ["query"],
                },
                "handler": self._search_user_files,
            }
        ]

    async def _search_user_files(
        self,
        query: str,
        limit: int = 10,
    ) -> dict:
        """
        Search artifacts accessible to the current user.

        Scope logic:
          - Always returns: scope='personal' AND user_id = <current_user>
          - Always returns: scope='company'
          - Management role: scope='department' (all departments)
          - Other roles:     scope='department' AND department = <user_dept>
        """
        from sqlalchemy import text
        from app.core.database import AsyncSessionLocal

        user_id = get_user_id()
        user_dept = get_user_dept()
        user_role = get_user_role()
        is_management = user_role.lower() in _MANAGEMENT_ROLES

        limit = min(max(1, limit), _MAX_RESULTS)
        like_pattern = f"%{query}%"

        try:
            # Build scope condition using UNION for clarity and safety
            if is_management:
                sql = text("""
                    SELECT filename, file_path, file_type, scope, department
                    FROM artifacts
                    WHERE filename ILIKE :pattern
                      AND (
                        scope = 'company'
                        OR scope = 'department'
                        OR (scope = 'personal' AND user_id = :user_id)
                      )
                    ORDER BY created_at DESC
                    LIMIT :limit
                """)
                params = {
                    "pattern": like_pattern,
                    "user_id": user_id,
                    "limit": limit,
                }
            else:
                sql = text("""
                    SELECT filename, file_path, file_type, scope, department
                    FROM artifacts
                    WHERE filename ILIKE :pattern
                      AND (
                        scope = 'company'
                        OR (scope = 'department' AND department = :dept)
                        OR (scope = 'personal' AND user_id = :user_id)
                      )
                    ORDER BY created_at DESC
                    LIMIT :limit
                """)
                params = {
                    "pattern": like_pattern,
                    "user_id": user_id,
                    "dept": user_dept,
                    "limit": limit,
                }

            async with AsyncSessionLocal() as session:
                result = await session.execute(sql, params)
                rows = result.mappings().all()

            files = [dict(r) for r in rows]
            logger.info(
                f"search_user_files: query={query!r} role={user_role} "
                f"dept={user_dept} found={len(files)}"
            )

            if not files:
                return self._ok({
                    "files": [],
                    "count": 0,
                    "message": f"No files found matching '{query}' in your accessible folders.",
                })

            return self._ok({
                "files": files,
                "count": len(files),
            })

        except Exception as e:
            logger.error(f"search_user_files failed: {e}")
            return self._err(f"File search failed: {e}")
