"""Tests for the shortname field on stocks."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import Stock, Tenant, User


@pytest.fixture
def stock_with_shortname(db: Session, test_tenant: Tenant, test_user: User) -> Stock:
    """Create a test stock with a shortname."""
    stock = Stock(
        tenant_id=test_tenant.id,
        stock_id="GFP-001",
        genotype="w[*]; P{w[+mC]=UAS-mCD8::GFP.L}Ptp4E[LL03]",
        shortname="GFP membrane marker",
        notes="Test stock with shortname",
        created_by_id=test_user.id,
        modified_by_id=test_user.id,
        owner_id=test_user.id,
    )
    db.add(stock)
    db.commit()
    db.refresh(stock)
    return stock


@pytest.fixture
def stock_without_shortname(db: Session, test_tenant: Tenant, test_user: User) -> Stock:
    """Create a test stock without a shortname."""
    stock = Stock(
        tenant_id=test_tenant.id,
        stock_id="BL-5678",
        genotype="w[1118]; P{GAL4-elav.L}3",
        created_by_id=test_user.id,
        modified_by_id=test_user.id,
        owner_id=test_user.id,
    )
    db.add(stock)
    db.commit()
    db.refresh(stock)
    return stock


class TestCreateStockWithShortname:
    """Tests for creating stocks with shortname."""

    def test_create_stock_with_shortname(self, authenticated_client: TestClient):
        """Test creating a stock with shortname."""
        response = authenticated_client.post(
            "/api/stocks",
            json={
                "stock_id": "NEW-SN-001",
                "genotype": "w[*]; UAS-GFP",
                "shortname": "GFP reporter",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["shortname"] == "GFP reporter"

    def test_create_stock_without_shortname(self, authenticated_client: TestClient):
        """Test creating a stock without shortname (should default to None)."""
        response = authenticated_client.post(
            "/api/stocks",
            json={
                "stock_id": "NEW-SN-002",
                "genotype": "w[*]; UAS-GFP",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["shortname"] is None

    def test_create_stock_shortname_too_long(self, authenticated_client: TestClient):
        """Test that shortname exceeding max length is rejected."""
        response = authenticated_client.post(
            "/api/stocks",
            json={
                "stock_id": "NEW-SN-003",
                "genotype": "w[*]; UAS-GFP",
                "shortname": "x" * 256,
            },
        )

        assert response.status_code == 422


class TestUpdateStockShortname:
    """Tests for updating stock shortname."""

    def test_update_shortname(
        self, authenticated_client: TestClient, stock_without_shortname: Stock
    ):
        """Test updating a stock's shortname."""
        response = authenticated_client.put(
            f"/api/stocks/{stock_without_shortname.id}",
            json={"shortname": "Elav GAL4 driver"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["shortname"] == "Elav GAL4 driver"

    def test_update_shortname_preserves_other_fields(
        self, authenticated_client: TestClient, stock_with_shortname: Stock
    ):
        """Test that updating shortname doesn't affect other fields."""
        response = authenticated_client.put(
            f"/api/stocks/{stock_with_shortname.id}",
            json={"shortname": "Updated marker"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["shortname"] == "Updated marker"
        assert data["genotype"] == stock_with_shortname.genotype
        assert data["stock_id"] == stock_with_shortname.stock_id


class TestSearchByShortname:
    """Tests for searching stocks by shortname."""

    def test_search_by_shortname(
        self, authenticated_client: TestClient, stock_with_shortname: Stock
    ):
        """Test that shortname is included in text search."""
        response = authenticated_client.get("/api/stocks?query=membrane")

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["stock_id"] == "GFP-001"

    def test_search_by_shortname_no_match(
        self, authenticated_client: TestClient, stock_with_shortname: Stock
    ):
        """Test search for shortname that doesn't exist returns nothing."""
        response = authenticated_client.get("/api/stocks?query=nonexistent_shortname")

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 0


class TestGetStockShortname:
    """Tests for retrieving stock shortname."""

    def test_get_stock_with_shortname(
        self, authenticated_client: TestClient, stock_with_shortname: Stock
    ):
        """Test that shortname is returned in stock response."""
        response = authenticated_client.get(f"/api/stocks/{stock_with_shortname.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["shortname"] == "GFP membrane marker"

    def test_get_stock_without_shortname(
        self, authenticated_client: TestClient, stock_without_shortname: Stock
    ):
        """Test that None shortname is returned correctly."""
        response = authenticated_client.get(f"/api/stocks/{stock_without_shortname.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["shortname"] is None


class TestSuggestShortname:
    """Tests for the suggest-shortname endpoint."""

    @patch("app.llm.service.get_llm_service")
    def test_suggest_shortname_success(self, mock_get_llm, authenticated_client: TestClient):
        """Test successful shortname suggestion."""
        mock_llm = mock_get_llm.return_value
        mock_llm.configured = True
        mock_llm.ask = AsyncMock(return_value="GFP membrane marker")

        response = authenticated_client.post(
            "/api/stocks/suggest-shortname",
            json={"genotype": "w[*]; P{w[+mC]=UAS-mCD8::GFP.L}Ptp4E[LL03]"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["shortname"] == "GFP membrane marker"

    @patch("app.llm.service.get_llm_service")
    def test_suggest_shortname_not_configured(self, mock_get_llm, authenticated_client: TestClient):
        """Test suggest-shortname when LLM is not configured."""
        mock_llm = mock_get_llm.return_value
        mock_llm.configured = False

        response = authenticated_client.post(
            "/api/stocks/suggest-shortname",
            json={"genotype": "w[*]; UAS-GFP"},
        )

        assert response.status_code == 400
        assert "not configured" in response.json()["detail"]

    @patch("app.llm.service.get_llm_service")
    def test_suggest_shortname_llm_error(self, mock_get_llm, authenticated_client: TestClient):
        """Test suggest-shortname when LLM returns an error."""
        mock_llm = mock_get_llm.return_value
        mock_llm.configured = True
        mock_llm.ask = AsyncMock(side_effect=ValueError("API error"))

        response = authenticated_client.post(
            "/api/stocks/suggest-shortname",
            json={"genotype": "w[*]; UAS-GFP"},
        )

        assert response.status_code == 500
        assert "Failed to generate" in response.json()["detail"]
