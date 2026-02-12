"""Tests for the stock wizard page route."""

from unittest.mock import patch

from fastapi.testclient import TestClient

from app.db.models import User


class TestWizardPageRoute:
    """Tests for GET /stocks/wizard page route."""

    def test_wizard_page_authenticated(self, client: TestClient, test_user: User):
        """Test that authenticated users can access the wizard page."""
        with patch("app.main.get_current_user_from_cookie", return_value=test_user):
            response = client.get("/stocks/wizard")
        assert response.status_code == 200
        assert "Add Stock" in response.text
        assert "stockWizard" in response.text

    def test_wizard_page_unauthenticated(self, client: TestClient):
        """Test that unauthenticated users are redirected to login."""
        response = client.get("/stocks/wizard", follow_redirects=False)
        assert response.status_code == 302
        assert "/login" in response.headers["location"]

    def test_wizard_page_contains_steps(self, client: TestClient, test_user: User):
        """Test that the wizard page contains all 4 step labels."""
        with patch("app.main.get_current_user_from_cookie", return_value=test_user):
            response = client.get("/stocks/wizard")
        assert response.status_code == 200
        assert "Origin" in response.text
        assert "Identity" in response.text
        assert "Location" in response.text
        assert "Review" in response.text
