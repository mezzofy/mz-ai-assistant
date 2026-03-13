"""
Auth OTP tests — Login OTP, Forgot Password, Change Password flows.

Covers:
  - TestLoginWithOTP:       POST /auth/login → otp_required response
  - TestVerifyOTP:          POST /auth/verify-otp → JWT or lockout
  - TestResendOTP:          POST /auth/resend-otp → sent or 429/404
  - TestForgotPassword:     POST /auth/forgot-password → always 200
  - TestVerifyResetOTP:     POST /auth/verify-reset-otp → reset_token or 400
  - TestResetPassword:      POST /auth/reset-password → ok or 422/400
  - TestChangePassword:     POST /auth/change-password → ok or 401/422
  - TestPasswordValidator:  validate_password_complexity() edge cases
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.core.password_validator import validate_password_complexity
from tests.conftest import auth_headers, hash_password, USERS


def _make_test_user(role: str) -> dict:
    """Build a user dict whose email matches the JWT token for the given role."""
    return {
        "id": USERS[role]["user_id"],
        "email": USERS[role]["email"],
        "password_hash": hash_password(VALID_PASSWORD),
        "name": f"Test {role}",
        "department": USERS[role]["department"],
        "role": role,
        "is_active": True,
    }


# ── Shared test data ──────────────────────────────────────────────────────────

VALID_EMAIL = "sales@test.com"
VALID_PASSWORD = "password123"
VALID_OTP_TOKEN = "test-otp-token-uuid"
VALID_OTP_CODE = "123456"
VALID_RESET_TOKEN = "test-reset-token-uuid"
STRONG_PASSWORD = "NewPass@2024"


# ── TestLoginWithOTP ──────────────────────────────────────────────────────────

class TestLoginWithOTP:
    """POST /auth/login now returns otp_required instead of JWT tokens."""

    @pytest.mark.asyncio
    async def test_valid_credentials_returns_otp_required(
        self, client, mock_db_get_user, mock_rate_limiter, mock_otp_store, mock_email_sender
    ):
        mock_otp_store["api_get_login_otp"].return_value = None  # not called on login

        response = await client.post("/auth/login", json={
            "email": VALID_EMAIL,
            "password": VALID_PASSWORD,
        })
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "otp_required"
        assert "otp_token" in data
        assert "message" in data
        # Should NOT contain tokens
        assert "access_token" not in data
        assert "refresh_token" not in data

    @pytest.mark.asyncio
    async def test_wrong_password_returns_401(
        self, client, mock_db_get_user, mock_rate_limiter, mock_otp_store, mock_email_sender
    ):
        response = await client.post("/auth/login", json={
            "email": VALID_EMAIL,
            "password": "wrongpassword",
        })
        assert response.status_code == 401
        assert "Invalid email or password" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_unknown_email_returns_401(
        self, client, mock_db_get_user, mock_rate_limiter, mock_otp_store, mock_email_sender
    ):
        response = await client.post("/auth/login", json={
            "email": "nobody@test.com",
            "password": VALID_PASSWORD,
        })
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_locked_account_returns_423(
        self, client, mock_db_get_user, mock_rate_limiter, mock_otp_store, mock_email_sender
    ):
        mock_otp_store["api_is_account_locked"].return_value = True

        response = await client.post("/auth/login", json={
            "email": VALID_EMAIL,
            "password": VALID_PASSWORD,
        })
        assert response.status_code == 423
        assert "locked" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_inactive_account_returns_401(
        self, client, mock_db_get_user, mock_rate_limiter, mock_otp_store, mock_email_sender
    ):
        response = await client.post("/auth/login", json={
            "email": "inactive@test.com",
            "password": VALID_PASSWORD,
        })
        assert response.status_code == 401


# ── TestVerifyOTP ─────────────────────────────────────────────────────────────

class TestVerifyOTP:
    """POST /auth/verify-otp → JWT tokens on success, lockout on 3 wrong attempts."""

    @pytest.mark.asyncio
    async def test_correct_otp_returns_jwt(
        self, client, mock_db_get_user, mock_rate_limiter, mock_otp_store, mock_email_sender
    ):
        mock_otp_store["api_get_login_otp"].return_value = {
            "email": VALID_EMAIL,
            "code": VALID_OTP_CODE,
        }

        response = await client.post("/auth/verify-otp", json={
            "otp_token": VALID_OTP_TOKEN,
            "code": VALID_OTP_CODE,
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert "user_info" in data

    @pytest.mark.asyncio
    async def test_wrong_otp_increments_attempts(
        self, client, mock_db_get_user, mock_rate_limiter, mock_otp_store, mock_email_sender
    ):
        mock_otp_store["api_get_login_otp"].return_value = {
            "email": VALID_EMAIL,
            "code": VALID_OTP_CODE,
        }
        mock_otp_store["api_increment_otp_attempts"].return_value = 1

        response = await client.post("/auth/verify-otp", json={
            "otp_token": VALID_OTP_TOKEN,
            "code": "000000",
        })
        assert response.status_code == 400
        assert "Incorrect code" in response.json()["detail"]
        assert "2 attempts remaining" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_third_wrong_otp_locks_account(
        self, client, mock_db_get_user, mock_rate_limiter, mock_otp_store, mock_email_sender
    ):
        mock_otp_store["api_get_login_otp"].return_value = {
            "email": VALID_EMAIL,
            "code": VALID_OTP_CODE,
        }
        mock_otp_store["api_increment_otp_attempts"].return_value = 3

        response = await client.post("/auth/verify-otp", json={
            "otp_token": VALID_OTP_TOKEN,
            "code": "000000",
        })
        assert response.status_code == 429
        assert "locked" in response.json()["detail"].lower()
        mock_otp_store["api_lock_account"].assert_called_once()

    @pytest.mark.asyncio
    async def test_expired_otp_returns_400(
        self, client, mock_rate_limiter, mock_otp_store, mock_email_sender
    ):
        mock_otp_store["api_get_login_otp"].return_value = None

        response = await client.post("/auth/verify-otp", json={
            "otp_token": "expired-token",
            "code": VALID_OTP_CODE,
        })
        assert response.status_code == 400
        assert "expired" in response.json()["detail"].lower()


# ── TestResendOTP ─────────────────────────────────────────────────────────────

class TestResendOTP:
    """POST /auth/resend-otp — resend within session, 60s cooldown."""

    @pytest.mark.asyncio
    async def test_resend_success(
        self, client, mock_rate_limiter, mock_otp_store, mock_email_sender
    ):
        mock_otp_store["api_get_login_otp"].return_value = {
            "email": VALID_EMAIL,
            "code": "654321",
        }
        mock_otp_store["api_can_resend_otp"].return_value = True

        response = await client.post("/auth/resend-otp", json={"otp_token": VALID_OTP_TOKEN})
        assert response.status_code == 200
        assert response.json()["status"] == "sent"

    @pytest.mark.asyncio
    async def test_resend_on_cooldown_returns_429(
        self, client, mock_rate_limiter, mock_otp_store, mock_email_sender
    ):
        mock_otp_store["api_get_login_otp"].return_value = {
            "email": VALID_EMAIL,
            "code": "654321",
        }
        mock_otp_store["api_can_resend_otp"].return_value = False

        response = await client.post("/auth/resend-otp", json={"otp_token": VALID_OTP_TOKEN})
        assert response.status_code == 429

    @pytest.mark.asyncio
    async def test_resend_unknown_token_returns_404(
        self, client, mock_rate_limiter, mock_otp_store, mock_email_sender
    ):
        mock_otp_store["api_get_login_otp"].return_value = None

        response = await client.post("/auth/resend-otp", json={"otp_token": "bad-token"})
        assert response.status_code == 404


# ── TestForgotPassword ────────────────────────────────────────────────────────

class TestForgotPassword:
    """POST /auth/forgot-password — always 200 to prevent email enumeration."""

    @pytest.mark.asyncio
    async def test_known_email_sends_otp_and_returns_200(
        self, client, mock_db_get_user, mock_rate_limiter, mock_otp_store, mock_email_sender
    ):
        response = await client.post("/auth/forgot-password", json={"email": VALID_EMAIL})
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "sent"
        assert "message" in data
        mock_otp_store["api_store_reset_otp"].assert_called_once()

    @pytest.mark.asyncio
    async def test_unknown_email_still_returns_200(
        self, client, mock_db_get_user, mock_rate_limiter, mock_otp_store, mock_email_sender
    ):
        response = await client.post("/auth/forgot-password", json={"email": "ghost@test.com"})
        assert response.status_code == 200
        # No OTP should be stored for unknown email
        mock_otp_store["api_store_reset_otp"].assert_not_called()


# ── TestVerifyResetOTP ────────────────────────────────────────────────────────

class TestVerifyResetOTP:
    """POST /auth/verify-reset-otp → reset_token on success."""

    @pytest.mark.asyncio
    async def test_correct_code_returns_reset_token(
        self, client, mock_rate_limiter, mock_otp_store, mock_email_sender
    ):
        mock_otp_store["api_get_reset_otp"].return_value = {"code": VALID_OTP_CODE}

        response = await client.post("/auth/verify-reset-otp", json={
            "email": VALID_EMAIL,
            "code": VALID_OTP_CODE,
        })
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "verified"
        assert "reset_token" in data

    @pytest.mark.asyncio
    async def test_wrong_code_returns_400(
        self, client, mock_rate_limiter, mock_otp_store, mock_email_sender
    ):
        mock_otp_store["api_get_reset_otp"].return_value = {"code": VALID_OTP_CODE}

        response = await client.post("/auth/verify-reset-otp", json={
            "email": VALID_EMAIL,
            "code": "000000",
        })
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_expired_otp_returns_400(
        self, client, mock_rate_limiter, mock_otp_store, mock_email_sender
    ):
        mock_otp_store["api_get_reset_otp"].return_value = None

        response = await client.post("/auth/verify-reset-otp", json={
            "email": VALID_EMAIL,
            "code": VALID_OTP_CODE,
        })
        assert response.status_code == 400


# ── TestResetPassword ─────────────────────────────────────────────────────────

class TestResetPassword:
    """POST /auth/reset-password — uses reset_token to set new password."""

    @pytest.mark.asyncio
    async def test_valid_reset_succeeds(
        self, client, mock_db_get_user, mock_rate_limiter, mock_otp_store, mock_email_sender
    ):
        mock_otp_store["api_get_reset_token_email"].return_value = VALID_EMAIL

        response = await client.post("/auth/reset-password", json={
            "reset_token": VALID_RESET_TOKEN,
            "new_password": STRONG_PASSWORD,
        })
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    @pytest.mark.asyncio
    async def test_weak_password_returns_422(
        self, client, mock_db_get_user, mock_rate_limiter, mock_otp_store, mock_email_sender
    ):
        mock_otp_store["api_get_reset_token_email"].return_value = VALID_EMAIL

        response = await client.post("/auth/reset-password", json={
            "reset_token": VALID_RESET_TOKEN,
            "new_password": "weak",
        })
        assert response.status_code == 422
        detail = response.json()["detail"]
        assert "violations" in detail

    @pytest.mark.asyncio
    async def test_bad_token_returns_400(
        self, client, mock_rate_limiter, mock_otp_store, mock_email_sender
    ):
        mock_otp_store["api_get_reset_token_email"].return_value = None

        response = await client.post("/auth/reset-password", json={
            "reset_token": "invalid-token",
            "new_password": STRONG_PASSWORD,
        })
        assert response.status_code == 400


# ── TestChangePassword ────────────────────────────────────────────────────────

class TestChangePassword:
    """POST /auth/change-password — requires Bearer token + correct current password."""

    @pytest.mark.asyncio
    async def test_valid_change_succeeds(
        self, client, mock_rate_limiter, mock_otp_store, mock_email_sender
    ):
        # JWT token for "sales_rep" has email=test_sales_rep@mezzofy.com
        # Patch async DB lookup to return a user with matching email and known password hash
        mock_get = AsyncMock(return_value=_make_test_user("sales_rep"))
        with patch("app.api.auth._get_user_by_email", mock_get), \
             patch("app.api.auth._update_password", new_callable=AsyncMock):
            response = await client.post(
                "/auth/change-password",
                json={"current_password": VALID_PASSWORD, "new_password": STRONG_PASSWORD},
                headers=auth_headers("sales_rep"),
            )
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    @pytest.mark.asyncio
    async def test_wrong_current_password_returns_401(
        self, client, mock_rate_limiter, mock_otp_store, mock_email_sender
    ):
        mock_get = AsyncMock(return_value=_make_test_user("sales_rep"))
        with patch("app.api.auth._get_user_by_email", mock_get), \
             patch("app.api.auth._update_password", new_callable=AsyncMock):
            response = await client.post(
                "/auth/change-password",
                json={"current_password": "wrongpassword", "new_password": STRONG_PASSWORD},
                headers=auth_headers("sales_rep"),
            )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_weak_new_password_returns_422(
        self, client, mock_rate_limiter, mock_otp_store, mock_email_sender
    ):
        mock_get = AsyncMock(return_value=_make_test_user("sales_rep"))
        with patch("app.api.auth._get_user_by_email", mock_get), \
             patch("app.api.auth._update_password", new_callable=AsyncMock):
            response = await client.post(
                "/auth/change-password",
                json={"current_password": VALID_PASSWORD, "new_password": "short"},
                headers=auth_headers("sales_rep"),
            )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_no_auth_returns_401(
        self, client, mock_rate_limiter, mock_otp_store, mock_email_sender
    ):
        response = await client.post(
            "/auth/change-password",
            json={"current_password": VALID_PASSWORD, "new_password": STRONG_PASSWORD},
        )
        assert response.status_code == 401


# ── TestPasswordValidator ─────────────────────────────────────────────────────

class TestPasswordValidator:
    """Unit tests for validate_password_complexity()."""

    def test_valid_password_has_no_violations(self):
        assert validate_password_complexity("SecurePass@1") == []

    def test_too_short(self):
        violations = validate_password_complexity("Ab@1")
        assert any("8" in v for v in violations)

    def test_no_uppercase(self):
        violations = validate_password_complexity("alllower@123")
        assert any("uppercase" in v.lower() for v in violations)

    def test_no_lowercase(self):
        violations = validate_password_complexity("ALLUPPER@123")
        assert any("lowercase" in v.lower() for v in violations)

    def test_no_digit(self):
        violations = validate_password_complexity("NoDigits@Here")
        assert any("digit" in v.lower() for v in violations)

    def test_no_special_char(self):
        violations = validate_password_complexity("NoSpecial123")
        assert any("special" in v.lower() for v in violations)

    def test_all_rules_missing(self):
        violations = validate_password_complexity("abc")
        assert len(violations) >= 4

    def test_exactly_eight_chars_passes_length(self):
        # "Ab@1abcd" — 8 chars with all rule types
        violations = validate_password_complexity("Ab@1abcd")
        assert not any("8" in v for v in violations)
