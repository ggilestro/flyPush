"""Tests for sliding session token refresh middleware."""

from datetime import timedelta

from fastapi.testclient import TestClient

from app.auth.utils import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
)
from app.db.models import User


class TestTokenRefreshMiddleware:
    """Tests for the refresh_token_middleware in main.py."""

    def test_valid_access_token_no_refresh(self, client: TestClient, test_user: User):
        """Active access token should not trigger a refresh."""
        access = create_access_token(test_user.id, test_user.tenant_id, test_user.email)
        client.cookies.set("access_token", access)
        response = client.get("/api/auth/me")

        assert response.status_code == 200
        # No new access_token cookie should be set
        assert "access_token" not in response.headers.get("set-cookie", "")

    def test_expired_access_refreshed_by_valid_refresh(self, client: TestClient, test_user: User):
        """Expired access token + valid refresh token should produce a new access token."""
        # Create an already-expired access token
        expired_access = create_access_token(
            test_user.id,
            test_user.tenant_id,
            test_user.email,
            expires_delta=timedelta(seconds=-1),
        )
        refresh = create_refresh_token(
            test_user.id,
            test_user.tenant_id,
            test_user.email,
        )

        client.cookies.set("access_token", expired_access)
        client.cookies.set("refresh_token", refresh)

        response = client.get("/api/auth/me")

        assert response.status_code == 200
        data = response.json()
        assert data["email"] == test_user.email

        # Verify a new access_token cookie was set on the response
        set_cookie = response.headers.get("set-cookie", "")
        assert "access_token" in set_cookie

    def test_missing_access_refreshed_by_valid_refresh(self, client: TestClient, test_user: User):
        """Missing access token + valid refresh token should produce a new access token."""
        refresh = create_refresh_token(
            test_user.id,
            test_user.tenant_id,
            test_user.email,
        )

        # Only set refresh, no access token
        client.cookies.set("refresh_token", refresh)

        response = client.get("/api/auth/me")

        assert response.status_code == 200
        data = response.json()
        assert data["email"] == test_user.email

    def test_expired_access_and_expired_refresh_returns_401(
        self, client: TestClient, test_user: User
    ):
        """Both tokens expired should return 401."""
        expired_access = create_access_token(
            test_user.id,
            test_user.tenant_id,
            test_user.email,
            expires_delta=timedelta(seconds=-1),
        )
        expired_refresh = create_refresh_token(
            test_user.id,
            test_user.tenant_id,
            test_user.email,
            expires_delta=timedelta(seconds=-1),
        )

        client.cookies.set("access_token", expired_access)
        client.cookies.set("refresh_token", expired_refresh)

        response = client.get("/api/auth/me")
        assert response.status_code == 401

    def test_no_tokens_returns_401(self, client: TestClient):
        """No tokens at all should return 401."""
        response = client.get("/api/auth/me")
        assert response.status_code == 401

    def test_refresh_rolls_refresh_token(self, client: TestClient, test_user: User):
        """When refreshing, the refresh token cookie should also be updated."""
        expired_access = create_access_token(
            test_user.id,
            test_user.tenant_id,
            test_user.email,
            expires_delta=timedelta(seconds=-1),
        )
        refresh = create_refresh_token(
            test_user.id,
            test_user.tenant_id,
            test_user.email,
        )

        client.cookies.set("access_token", expired_access)
        client.cookies.set("refresh_token", refresh)

        response = client.get("/api/auth/me")
        assert response.status_code == 200

        # Both cookies should be set in response
        cookie_header = response.headers.get("set-cookie", "")
        assert "access_token" in cookie_header
        assert "refresh_token" in cookie_header

    def test_page_view_refreshed_by_valid_refresh(self, client: TestClient, test_user: User):
        """Page routes using get_current_user_from_cookie also benefit from refresh."""
        expired_access = create_access_token(
            test_user.id,
            test_user.tenant_id,
            test_user.email,
            expires_delta=timedelta(seconds=-1),
        )
        refresh = create_refresh_token(
            test_user.id,
            test_user.tenant_id,
            test_user.email,
        )

        client.cookies.set("access_token", expired_access)
        client.cookies.set("refresh_token", refresh)

        response = client.get("/stocks")

        # Should not redirect to login — the middleware refreshed the token
        assert response.status_code == 200

    def test_refreshed_token_is_valid(self, client: TestClient, test_user: User):
        """The refreshed access token should be decodable and contain correct data."""
        expired_access = create_access_token(
            test_user.id,
            test_user.tenant_id,
            test_user.email,
            expires_delta=timedelta(seconds=-1),
        )
        refresh = create_refresh_token(
            test_user.id,
            test_user.tenant_id,
            test_user.email,
        )

        client.cookies.set("access_token", expired_access)
        client.cookies.set("refresh_token", refresh)

        response = client.get("/api/auth/me")
        assert response.status_code == 200

        # Extract the new access token from cookies
        new_token = response.cookies.get("access_token")
        assert new_token is not None

        # Verify the new token is valid
        token_data = decode_access_token(new_token)
        assert token_data is not None
        assert token_data.user_id == str(test_user.id)
        assert token_data.email == test_user.email

    def test_old_refresh_token_without_email_no_refresh(self, client: TestClient, test_user: User):
        """Refresh tokens without email (pre-migration) should not crash, just 401."""
        expired_access = create_access_token(
            test_user.id,
            test_user.tenant_id,
            test_user.email,
            expires_delta=timedelta(seconds=-1),
        )
        # Create a legacy refresh token without email
        old_refresh = create_refresh_token(
            test_user.id,
            test_user.tenant_id,
            email="",  # empty email, like pre-migration tokens
        )

        client.cookies.set("access_token", expired_access)
        client.cookies.set("refresh_token", old_refresh)

        response = client.get("/api/auth/me")
        # Should not refresh (no email in refresh token), so 401
        assert response.status_code == 401
