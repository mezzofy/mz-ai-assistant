"""
Tests for FilesOps.search_user_files tool and supporting user_context changes.

Test coverage:
  - Management user searches all department scopes (no dept filter)
  - Non-management user restricted to own department + personal + company
  - Non-management user cannot access other department files
  - ILIKE keyword search applied to filenames
  - No-files-found returns graceful empty result (not an error)
  - limit param capped at MAX_RESULTS
  - DB failure returns error dict
  - user_context: set_user_context sets role + user_id; getters return correct values
  - router: _execute_with_instance passes role + user_id to set_user_context
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_file_row(filename, file_path=None, file_type="pdf", scope="personal", department="sales"):
    row = MagicMock()
    row.filename = filename
    row.file_path = file_path or f"/data/artifacts/{filename}"
    row.file_type = file_type
    row.scope = scope
    row.department = department
    # MagicMock objects aren't directly dict()-able — return real dict via __iter__
    row.__iter__ = MagicMock(return_value=iter([
        ("filename", filename),
        ("file_path", file_path or f"/data/artifacts/{filename}"),
        ("file_type", file_type),
        ("scope", scope),
        ("department", department),
    ]))
    return row


def _make_db_session_cm(rows: list):
    """Build a mock AsyncSessionLocal async context manager returning given rows."""
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_mappings = MagicMock()
    mock_mappings.all.return_value = [dict(r) for r in [
        {"filename": r.filename, "file_path": r.file_path,
         "file_type": r.file_type, "scope": r.scope, "department": r.department}
        for r in rows
    ]]
    mock_result.mappings.return_value = mock_mappings
    mock_session.execute = AsyncMock(return_value=mock_result)

    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
    mock_cm.__aexit__ = AsyncMock(return_value=False)
    return mock_cm, mock_session


# ── FilesOps.search_user_files ─────────────────────────────────────────────────

class TestSearchUserFiles:
    """Unit tests for FilesOps._search_user_files."""

    def _make_ops(self):
        from app.tools.files_ops import FilesOps
        return FilesOps({})

    async def test_management_user_gets_all_dept_files(self):
        """Management role sees files from all departments (no dept filter in query)."""
        rows = [
            {"filename": "SLA-v1.pdf", "file_path": "/data/SLA-v1.pdf",
             "file_type": "pdf", "scope": "department", "department": "hr"},
            {"filename": "SLA-sales.pdf", "file_path": "/data/SLA-sales.pdf",
             "file_type": "pdf", "scope": "department", "department": "sales"},
        ]
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_mappings = MagicMock()
        mock_mappings.all.return_value = rows
        mock_result.mappings.return_value = mock_mappings
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        with patch("app.core.user_context._user_role") as mock_role, \
             patch("app.core.user_context._user_id_ctx") as mock_uid, \
             patch("app.core.user_context._user_dept") as mock_dept, \
             patch("app.core.database.AsyncSessionLocal", return_value=mock_cm):
            mock_role.get.return_value = "manager"
            mock_uid.get.return_value = str(uuid.uuid4())
            mock_dept.get.return_value = "management"

            ops = self._make_ops()
            result = await ops._search_user_files(query="SLA", limit=10)

        assert result["success"] is True
        output = result["output"]
        assert output["count"] == 2
        assert len(output["files"]) == 2

        # Verify SQL did NOT include dept param (management query has no :dept param)
        call_args = mock_session.execute.call_args
        bound_params = call_args[0][1]  # second positional arg = params dict
        assert "dept" not in bound_params

    async def test_non_management_user_has_dept_filter(self):
        """Non-management role SQL includes :dept parameter."""
        rows = [
            {"filename": "sales-sla.pdf", "file_path": "/data/sales-sla.pdf",
             "file_type": "pdf", "scope": "department", "department": "sales"},
        ]
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_mappings = MagicMock()
        mock_mappings.all.return_value = rows
        mock_result.mappings.return_value = mock_mappings
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        with patch("app.core.user_context._user_role") as mock_role, \
             patch("app.core.user_context._user_id_ctx") as mock_uid, \
             patch("app.core.user_context._user_dept") as mock_dept, \
             patch("app.core.database.AsyncSessionLocal", return_value=mock_cm):
            mock_role.get.return_value = "user"
            mock_uid.get.return_value = str(uuid.uuid4())
            mock_dept.get.return_value = "sales"

            ops = self._make_ops()
            result = await ops._search_user_files(query="SLA", limit=10)

        assert result["success"] is True
        # Verify SQL includes :dept param
        call_args = mock_session.execute.call_args
        bound_params = call_args[0][1]
        assert "dept" in bound_params
        assert bound_params["dept"] == "sales"

    async def test_no_files_found_returns_empty_gracefully(self):
        """Zero results returns success=True with empty files list and helpful message."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_mappings = MagicMock()
        mock_mappings.all.return_value = []
        mock_result.mappings.return_value = mock_mappings
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        with patch("app.core.user_context._user_role") as mock_role, \
             patch("app.core.user_context._user_id_ctx") as mock_uid, \
             patch("app.core.user_context._user_dept") as mock_dept, \
             patch("app.core.database.AsyncSessionLocal", return_value=mock_cm):
            mock_role.get.return_value = "user"
            mock_uid.get.return_value = str(uuid.uuid4())
            mock_dept.get.return_value = "sales"

            ops = self._make_ops()
            result = await ops._search_user_files(query="nonexistent_document_xyz", limit=10)

        assert result["success"] is True
        output = result["output"]
        assert output["count"] == 0
        assert output["files"] == []
        assert "nonexistent_document_xyz" in output["message"]

    async def test_limit_capped_at_max(self):
        """limit param > MAX_RESULTS is capped."""
        from app.tools.files_ops import _MAX_RESULTS

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_mappings = MagicMock()
        mock_mappings.all.return_value = []
        mock_result.mappings.return_value = mock_mappings
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        with patch("app.core.user_context._user_role") as mock_role, \
             patch("app.core.user_context._user_id_ctx") as mock_uid, \
             patch("app.core.user_context._user_dept") as mock_dept, \
             patch("app.core.database.AsyncSessionLocal", return_value=mock_cm):
            mock_role.get.return_value = "user"
            mock_uid.get.return_value = str(uuid.uuid4())
            mock_dept.get.return_value = "sales"

            ops = self._make_ops()
            await ops._search_user_files(query="doc", limit=9999)

        call_args = mock_session.execute.call_args
        bound_params = call_args[0][1]
        assert bound_params["limit"] == _MAX_RESULTS

    async def test_ilike_pattern_applied_to_query(self):
        """query string is wrapped with % for ILIKE search."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_mappings = MagicMock()
        mock_mappings.all.return_value = []
        mock_result.mappings.return_value = mock_mappings
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        with patch("app.core.user_context._user_role") as mock_role, \
             patch("app.core.user_context._user_id_ctx") as mock_uid, \
             patch("app.core.user_context._user_dept") as mock_dept, \
             patch("app.core.database.AsyncSessionLocal", return_value=mock_cm):
            mock_role.get.return_value = "user"
            mock_uid.get.return_value = str(uuid.uuid4())
            mock_dept.get.return_value = "sales"

            ops = self._make_ops()
            await ops._search_user_files(query="SLA contract")

        call_args = mock_session.execute.call_args
        bound_params = call_args[0][1]
        assert bound_params["pattern"] == "%SLA contract%"

    async def test_db_failure_returns_error(self):
        """Database exception returns success=False with error message."""
        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(side_effect=Exception("DB connection lost"))
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        with patch("app.core.user_context._user_role") as mock_role, \
             patch("app.core.user_context._user_id_ctx") as mock_uid, \
             patch("app.core.user_context._user_dept") as mock_dept, \
             patch("app.core.database.AsyncSessionLocal", return_value=mock_cm):
            mock_role.get.return_value = "user"
            mock_uid.get.return_value = str(uuid.uuid4())
            mock_dept.get.return_value = "sales"

            ops = self._make_ops()
            result = await ops._search_user_files(query="SLA")

        assert result["success"] is False
        assert "DB connection lost" in result["error"]

    async def test_admin_role_treated_as_management(self):
        """'admin' role also gets the management (no dept filter) query path."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_mappings = MagicMock()
        mock_mappings.all.return_value = []
        mock_result.mappings.return_value = mock_mappings
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        with patch("app.core.user_context._user_role") as mock_role, \
             patch("app.core.user_context._user_id_ctx") as mock_uid, \
             patch("app.core.user_context._user_dept") as mock_dept, \
             patch("app.core.database.AsyncSessionLocal", return_value=mock_cm):
            mock_role.get.return_value = "admin"
            mock_uid.get.return_value = str(uuid.uuid4())
            mock_dept.get.return_value = "management"

            ops = self._make_ops()
            await ops._search_user_files(query="policy")

        call_args = mock_session.execute.call_args
        bound_params = call_args[0][1]
        assert "dept" not in bound_params


# ── user_context.py ────────────────────────────────────────────────────────────

class TestUserContext:
    """Unit tests for set_user_context / getter functions."""

    def test_set_and_get_role(self):
        from app.core.user_context import set_user_context, get_user_role
        set_user_context(dept="sales", email="user@test.com", role="manager")
        assert get_user_role() == "manager"

    def test_set_and_get_user_id(self):
        from app.core.user_context import set_user_context, get_user_id
        uid = str(uuid.uuid4())
        set_user_context(dept="sales", email="user@test.com", user_id=uid)
        assert get_user_id() == uid

    def test_defaults_when_not_set(self):
        """New ContextVar values use their defaults when not explicitly set."""
        from app.core.user_context import get_user_role, get_user_id
        # These may have been set by a previous test — reset by calling set_user_context
        from app.core.user_context import set_user_context
        set_user_context(dept="", email="", role="", user_id="")
        assert get_user_role() == "user"   # fallback to default via `role or "user"`
        assert get_user_id() == ""

    def test_backward_compat_no_role_no_user_id(self):
        """Calling set_user_context with only dept+email still works (no TypeError)."""
        from app.core.user_context import set_user_context, get_user_role, get_user_id
        set_user_context(dept="hr", email="hr@test.com")
        assert get_user_role() == "user"
        assert get_user_id() == ""


# ── router.py ─────────────────────────────────────────────────────────────────

class TestRouterUserContextPassthrough:
    """Verify _execute_with_instance passes role + user_id to set_user_context."""

    async def test_role_and_user_id_passed_to_context(self):
        """_execute_with_instance calls set_user_context with role and user_id from task."""
        from app.router import _execute_with_instance

        uid = str(uuid.uuid4())
        task = {
            "source": "mobile",
            "message": "test",
            "department": "sales",
            "email": "rep@test.com",
            "role": "manager",
            "user_id": uid,
            "conversation_history": [],
        }

        mock_agent = MagicMock()
        mock_agent.__class__.__name__ = "SalesAgent"
        mock_agent.execute = AsyncMock(return_value={
            "success": True,
            "content": "ok",
            "artifacts": [],
            "tools_called": [],
        })

        with patch("app.router.set_user_context") as mock_set_ctx:
            await _execute_with_instance(mock_agent, task)

        mock_set_ctx.assert_called_once_with(
            dept="sales",
            email="rep@test.com",
            role="manager",
            user_id=uid,
        )

    async def test_defaults_used_when_role_and_user_id_missing(self):
        """Missing role/user_id in task falls back to defaults in set_user_context call."""
        from app.router import _execute_with_instance

        task = {
            "source": "mobile",
            "message": "test",
            "department": "hr",
            "email": "hr@test.com",
            "conversation_history": [],
        }

        mock_agent = MagicMock()
        mock_agent.__class__.__name__ = "HRAgent"
        mock_agent.execute = AsyncMock(return_value={
            "success": True,
            "content": "ok",
            "artifacts": [],
            "tools_called": [],
        })

        with patch("app.router.set_user_context") as mock_set_ctx:
            await _execute_with_instance(mock_agent, task)

        mock_set_ctx.assert_called_once_with(
            dept="hr",
            email="hr@test.com",
            role="user",
            user_id="",
        )
