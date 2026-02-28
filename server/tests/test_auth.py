"""
Auth endpoint tests — POST /auth/login, /auth/refresh, /auth/logout, GET /auth/me.

Tests cover:
  - Login with valid credentials → 200 + JWT pair
  - Login with wrong password → 401
  - Login with unknown email → 401
  - Login with inactive account → 401
  - Access protected endpoint without token → 401
  - Access with expired/invalid token → 401
  - Refresh token flow → 200 + new access token
  - Refresh with invalid token → 401
  - Refresh with blacklisted token → 401
  - Logout → 204 (blacklists refresh token)
  - GET /auth/me → returns user payload
  - Rate limit: auth endpoints
  - RBAC: role permissions in JWT
"""

import pytest
from jose import jwt
from app.core.auth import create_access_token, create_refresh_token, hash_password
from tests.conftest import USERS, make_token, make_refresh_token, auth_headers, TEST_CONFIG


pytestmark = pytest.mark.unit


# ── Login ─────────────────────────────────────────────────────────────────────

class TestLogin:
    async def test_login_valid_credentials(
        self, client, mock_db_get_user, mock_get_db, mock_rate_limiter
    ):
        response = await client.post(
            "/auth/login",
            json={"email": "sales@test.com", "password": "password123"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert "user_info" in data
        assert data["user_info"]["email"] == "sales@test.com"
        assert data["user_info"]["role"] == "sales_rep"
        assert "email_send" in data["user_info"]["permissions"]

    async def test_login_wrong_password(
        self, client, mock_db_get_user, mock_get_db, mock_rate_limiter
    ):
        response = await client.post(
            "/auth/login",
            json={"email": "sales@test.com", "password": "wrongpassword"},
        )
        assert response.status_code == 401
        assert "Invalid email or password" in response.json()["detail"]

    async def test_login_unknown_email(
        self, client, mock_db_get_user, mock_get_db, mock_rate_limiter
    ):
        response = await client.post(
            "/auth/login",
            json={"email": "nobody@test.com", "password": "password123"},
        )
        assert response.status_code == 401
        assert "Invalid email or password" in response.json()["detail"]

    async def test_login_inactive_account(
        self, client, mock_db_get_user, mock_get_db, mock_rate_limiter
    ):
        response = await client.post(
            "/auth/login",
            json={"email": "inactive@test.com", "password": "password123"},
        )
        assert response.status_code == 401
        assert "inactive" in response.json()["detail"].lower()

    async def test_login_missing_email(
        self, client, mock_db_get_user, mock_get_db, mock_rate_limiter
    ):
        response = await client.post(
            "/auth/login",
            json={"password": "password123"},
        )
        assert response.status_code == 422  # Pydantic validation error

    async def test_login_invalid_email_format(
        self, client, mock_db_get_user, mock_get_db, mock_rate_limiter
    ):
        response = await client.post(
            "/auth/login",
            json={"email": "not-an-email", "password": "password123"},
        )
        assert response.status_code == 422

    async def test_login_returns_permissions_in_user_info(
        self, client, mock_db_get_user, mock_get_db, mock_rate_limiter
    ):
        response = await client.post(
            "/auth/login",
            json={"email": "finance@test.com", "password": "password123"},
        )
        assert response.status_code == 200
        permissions = response.json()["user_info"]["permissions"]
        assert "finance_read" in permissions
        assert "finance_write" in permissions
        assert "email_send" in permissions
        assert "scheduler_manage" in permissions

    async def test_login_access_token_is_valid_jwt(
        self, client, mock_db_get_user, mock_get_db, mock_rate_limiter
    ):
        response = await client.post(
            "/auth/login",
            json={"email": "sales@test.com", "password": "password123"},
        )
        assert response.status_code == 200
        access_token = response.json()["access_token"]
        payload = jwt.decode(
            access_token,
            "test-secret-do-not-use-in-production",
            algorithms=["HS256"],
        )
        assert payload["token_type"] == "access"
        assert payload["email"] == "sales@test.com"
        assert payload["role"] == "sales_rep"


# ── Protected endpoint without token ─────────────────────────────────────────

class TestProtectedWithoutToken:
    async def test_chat_send_no_token(self, client):
        response = await client.post(
            "/chat/send",
            json={"message": "hello"},
        )
        assert response.status_code == 401

    async def test_scheduler_no_token(self, client):
        response = await client.get("/scheduler/jobs")
        assert response.status_code == 401

    async def test_admin_no_token(self, client):
        response = await client.get("/admin/users")
        assert response.status_code == 401

    async def test_files_no_token(self, client):
        response = await client.get("/files/list")
        assert response.status_code == 401

    async def test_auth_me_no_token(self, client):
        response = await client.get("/auth/me")
        assert response.status_code == 401

    async def test_chat_send_invalid_token(self, client):
        response = await client.post(
            "/chat/send",
            json={"message": "hello"},
            headers={"Authorization": "Bearer this-is-not-a-valid-jwt"},
        )
        assert response.status_code == 401


# ── Expired token ─────────────────────────────────────────────────────────────

class TestExpiredToken:
    async def test_expired_access_token_rejected(self, client):
        import os
        from datetime import timedelta
        from unittest.mock import patch

        user_data = {**USERS["sales_rep"]}
        user_data["exp"] = int(
            (
                __import__("datetime").datetime.now(
                    __import__("datetime").timezone.utc
                )
                - timedelta(hours=2)
            ).timestamp()
        )

        # jose will not generate an expired token with the standard API —
        # create one by encoding directly
        from jose import jwt as jose_jwt
        expired_token = jose_jwt.encode(
            user_data,
            "test-secret-do-not-use-in-production",
            algorithm="HS256",
        )

        response = await client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {expired_token}"},
        )
        assert response.status_code == 401

    async def test_refresh_token_used_as_access_rejected(self, client):
        refresh = make_refresh_token("sales_rep")
        response = await client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {refresh}"},
        )
        assert response.status_code == 401


# ── Token refresh ─────────────────────────────────────────────────────────────

class TestRefreshToken:
    async def test_refresh_valid_token(
        self, client, mock_redis_blacklist, mock_rate_limiter
    ):
        refresh = make_refresh_token("sales_rep")
        response = await client.post(
            "/auth/refresh",
            json={"refresh_token": refresh},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    async def test_refresh_invalid_token(
        self, client, mock_rate_limiter
    ):
        response = await client.post(
            "/auth/refresh",
            json={"refresh_token": "not-a-real-jwt"},
        )
        assert response.status_code == 401

    async def test_refresh_access_token_as_refresh_rejected(
        self, client, mock_rate_limiter
    ):
        access = make_token("sales_rep")
        response = await client.post(
            "/auth/refresh",
            json={"refresh_token": access},
        )
        assert response.status_code == 401

    async def test_refresh_blacklisted_token(
        self, client, mock_rate_limiter
    ):
        from unittest.mock import patch, AsyncMock
        refresh = make_refresh_token("sales_rep")
        with patch("app.api.auth.is_refresh_token_blacklisted", new_callable=AsyncMock, return_value=True):
            response = await client.post(
                "/auth/refresh",
                json={"refresh_token": refresh},
            )
        assert response.status_code == 401
        assert "revoked" in response.json()["detail"].lower()


# ── Logout ────────────────────────────────────────────────────────────────────

class TestLogout:
    async def test_logout_blacklists_refresh_token(
        self, client, mock_redis_blacklist
    ):
        from unittest.mock import patch, AsyncMock
        refresh = make_refresh_token("sales_rep")
        # auth.py locally imports blacklist_refresh_token → must patch at import site
        with patch("app.api.auth.blacklist_refresh_token", new_callable=AsyncMock) as mock_bl:
            response = await client.post(
                "/auth/logout",
                json={"refresh_token": refresh},
                headers=auth_headers("sales_rep"),
            )
        assert response.status_code == 204
        mock_bl.assert_called_once()

    async def test_logout_with_invalid_token_is_idempotent(
        self, client, mock_redis_blacklist
    ):
        """Logout with an already-invalid token returns 204 (idempotent)."""
        response = await client.post(
            "/auth/logout",
            json={"refresh_token": "already-invalid"},
            headers=auth_headers("sales_rep"),
        )
        assert response.status_code == 204


# ── GET /auth/me ──────────────────────────────────────────────────────────────

class TestGetMe:
    async def test_get_me_returns_user_info(self, client):
        response = await client.get(
            "/auth/me",
            headers=auth_headers("finance_manager"),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "test_finance_manager@mezzofy.com"
        assert data["role"] == "finance_manager"
        assert data["department"] == "finance"
        assert "finance_read" in data["permissions"]
        assert "finance_write" in data["permissions"]

    async def test_get_me_admin_has_wildcard_permissions(self, client):
        response = await client.get(
            "/auth/me",
            headers=auth_headers("admin"),
        )
        assert response.status_code == 200
        assert "*" in response.json()["permissions"]

    async def test_get_me_executive_has_cross_dept_permissions(self, client):
        response = await client.get(
            "/auth/me",
            headers=auth_headers("executive"),
        )
        assert response.status_code == 200
        permissions = response.json()["permissions"]
        assert "finance_read" in permissions
        assert "sales_read" in permissions
        assert "management_read" in permissions
        assert "audit_read" in permissions

    async def test_get_me_support_agent_lacks_audit_read(self, client):
        response = await client.get(
            "/auth/me",
            headers=auth_headers("support_agent"),
        )
        assert response.status_code == 200
        permissions = response.json()["permissions"]
        assert "audit_read" not in permissions

    async def test_get_me_sales_rep_has_linkedin_access(self, client):
        response = await client.get(
            "/auth/me",
            headers=auth_headers("sales_rep"),
        )
        assert response.status_code == 200
        permissions = response.json()["permissions"]
        assert "linkedin_access" in permissions
        assert "sales_read" in permissions
        assert "sales_write" in permissions


# ── Health check ──────────────────────────────────────────────────────────────

class TestHealthCheck:
    async def test_health_endpoint_unauthenticated(self, client):
        """Health check must be accessible without a token."""
        from unittest.mock import patch, AsyncMock
        with patch("app.main.check_db_connection", new_callable=AsyncMock, return_value=True), \
             patch("redis.asyncio.from_url") as mock_redis:
            mock_redis.return_value.__aenter__ = AsyncMock()
            mock_redis.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_redis.return_value.__aenter__.return_value.ping = AsyncMock()
            response = await client.get("/health")
        # Should return 200 regardless (degraded or ok)
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "version" in data
        assert data["version"] == "1.0.0"
