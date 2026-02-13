"""Tests for adjacent stock navigation."""

from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import Stock, Tenant, Tray, TrayType, User


@pytest.fixture
def three_stocks(db: Session, test_tenant: Tenant, test_user: User) -> list[Stock]:
    """Create three stocks with distinct modified_at timestamps."""
    stocks = []
    base_time = datetime(2026, 1, 1, 12, 0, 0)
    for i, (sid, genotype) in enumerate(
        [
            ("STOCK-A", "w[1118]"),
            ("STOCK-B", "y[1] w[*]"),
            ("STOCK-C", "Canton-S"),
        ]
    ):
        stock = Stock(
            tenant_id=test_tenant.id,
            stock_id=sid,
            genotype=genotype,
            created_by_id=test_user.id,
            modified_by_id=test_user.id,
            owner_id=test_user.id,
        )
        db.add(stock)
        db.flush()
        # Set modified_at explicitly with distinct values
        stock.modified_at = base_time + timedelta(hours=i)
        stocks.append(stock)
    db.commit()
    for s in stocks:
        db.refresh(s)
    return stocks


@pytest.fixture
def stocks_with_tray(db: Session, test_tenant: Tenant, test_user: User) -> tuple[list[Stock], Tray]:
    """Create stocks, some in a tray, some not."""
    tray = Tray(
        tenant_id=test_tenant.id,
        name="Fridge A",
        tray_type=TrayType.NUMERIC,
        max_positions=50,
    )
    db.add(tray)
    db.flush()

    base_time = datetime(2026, 1, 1, 12, 0, 0)
    stocks = []
    for i, (sid, in_tray) in enumerate(
        [
            ("T-001", True),
            ("T-002", False),
            ("T-003", True),
            ("T-004", True),
        ]
    ):
        stock = Stock(
            tenant_id=test_tenant.id,
            stock_id=sid,
            genotype=f"genotype-{i}",
            tray_id=tray.id if in_tray else None,
            created_by_id=test_user.id,
            modified_by_id=test_user.id,
            owner_id=test_user.id,
        )
        db.add(stock)
        db.flush()
        stock.modified_at = base_time + timedelta(hours=i)
        stocks.append(stock)
    db.commit()
    for s in stocks:
        db.refresh(s)
    return stocks, tray


class TestAdjacentStocks:
    """Tests for the /{stock_id}/adjacent endpoint."""

    def test_basic_navigation(self, authenticated_client: TestClient, three_stocks: list[Stock]):
        """Test that middle stock has correct prev/next."""
        # Default sort: modified_at desc -> order is C, B, A
        # So for B: prev=C, next=A
        stock_b = three_stocks[1]  # STOCK-B
        stock_a = three_stocks[0]  # STOCK-A
        stock_c = three_stocks[2]  # STOCK-C

        response = authenticated_client.get(f"/api/stocks/{stock_b.id}/adjacent")
        assert response.status_code == 200
        data = response.json()

        assert data["prev_id"] == stock_c.id
        assert data["prev_stock_id"] == "STOCK-C"
        assert data["next_id"] == stock_a.id
        assert data["next_stock_id"] == "STOCK-A"

    def test_first_stock_no_prev(self, authenticated_client: TestClient, three_stocks: list[Stock]):
        """Test that first stock in sort order has no prev."""
        # Default sort: modified_at desc -> C is first
        stock_c = three_stocks[2]

        response = authenticated_client.get(f"/api/stocks/{stock_c.id}/adjacent")
        assert response.status_code == 200
        data = response.json()

        assert data["prev_id"] is None
        assert data["prev_stock_id"] is None
        assert data["next_id"] is not None

    def test_last_stock_no_next(self, authenticated_client: TestClient, three_stocks: list[Stock]):
        """Test that last stock in sort order has no next."""
        # Default sort: modified_at desc -> A is last
        stock_a = three_stocks[0]

        response = authenticated_client.get(f"/api/stocks/{stock_a.id}/adjacent")
        assert response.status_code == 200
        data = response.json()

        assert data["next_id"] is None
        assert data["next_stock_id"] is None
        assert data["prev_id"] is not None

    def test_single_stock(
        self, authenticated_client: TestClient, db: Session, test_tenant: Tenant, test_user: User
    ):
        """Test that a single stock has no prev or next."""
        stock = Stock(
            tenant_id=test_tenant.id,
            stock_id="ONLY-ONE",
            genotype="w[*]",
            created_by_id=test_user.id,
            modified_by_id=test_user.id,
            owner_id=test_user.id,
        )
        db.add(stock)
        db.commit()
        db.refresh(stock)

        response = authenticated_client.get(f"/api/stocks/{stock.id}/adjacent")
        assert response.status_code == 200
        data = response.json()

        assert data["prev_id"] is None
        assert data["next_id"] is None

    def test_with_tray_filter(
        self, authenticated_client: TestClient, stocks_with_tray: tuple[list[Stock], Tray]
    ):
        """Test navigation with tray_id filter excludes non-tray stocks."""
        stocks, tray = stocks_with_tray
        # In tray: T-001 (idx 0), T-003 (idx 2), T-004 (idx 3)
        # Default sort desc: T-004, T-003, T-001
        # T-003 should have prev=T-004, next=T-001

        stock_003 = stocks[2]  # T-003
        stock_001 = stocks[0]  # T-001
        stock_004 = stocks[3]  # T-004

        response = authenticated_client.get(
            f"/api/stocks/{stock_003.id}/adjacent?tray_id={tray.id}"
        )
        assert response.status_code == 200
        data = response.json()

        assert data["prev_id"] == stock_004.id
        assert data["next_id"] == stock_001.id

    def test_custom_sort_asc(self, authenticated_client: TestClient, three_stocks: list[Stock]):
        """Test navigation with ascending sort by stock_id."""
        # sort by stock_id asc -> STOCK-A, STOCK-B, STOCK-C
        # For B: prev=A, next=C
        stock_a = three_stocks[0]
        stock_b = three_stocks[1]
        stock_c = three_stocks[2]

        response = authenticated_client.get(
            f"/api/stocks/{stock_b.id}/adjacent?sort_by=stock_id&sort_order=asc"
        )
        assert response.status_code == 200
        data = response.json()

        assert data["prev_id"] == stock_a.id
        assert data["prev_stock_id"] == "STOCK-A"
        assert data["next_id"] == stock_c.id
        assert data["next_stock_id"] == "STOCK-C"

    def test_custom_sort_desc(self, authenticated_client: TestClient, three_stocks: list[Stock]):
        """Test navigation with descending sort by stock_id."""
        # sort by stock_id desc -> STOCK-C, STOCK-B, STOCK-A
        # For B: prev=C, next=A
        stock_a = three_stocks[0]
        stock_b = three_stocks[1]
        stock_c = three_stocks[2]

        response = authenticated_client.get(
            f"/api/stocks/{stock_b.id}/adjacent?sort_by=stock_id&sort_order=desc"
        )
        assert response.status_code == 200
        data = response.json()

        assert data["prev_id"] == stock_c.id
        assert data["next_id"] == stock_a.id

    def test_nonexistent_stock(self, authenticated_client: TestClient):
        """Test adjacent with nonexistent stock returns empty."""
        response = authenticated_client.get(
            "/api/stocks/00000000-0000-0000-0000-000000000000/adjacent"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["prev_id"] is None
        assert data["next_id"] is None

    def test_with_search_query(self, authenticated_client: TestClient, three_stocks: list[Stock]):
        """Test navigation with search query filter."""
        # Search for "STOCK" matches all three
        stock_b = three_stocks[1]

        response = authenticated_client.get(f"/api/stocks/{stock_b.id}/adjacent?q=STOCK")
        assert response.status_code == 200
        data = response.json()
        # Should still find prev and next since all match
        assert data["prev_id"] is not None
        assert data["next_id"] is not None

    def test_tie_breaking_same_modified_at(
        self, authenticated_client: TestClient, db: Session, test_tenant: Tenant, test_user: User
    ):
        """Test deterministic ordering when modified_at values are identical."""
        same_time = datetime(2026, 6, 1, 12, 0, 0)
        stocks = []
        for sid in ["TIE-A", "TIE-B", "TIE-C"]:
            stock = Stock(
                tenant_id=test_tenant.id,
                stock_id=sid,
                genotype="w[*]",
                created_by_id=test_user.id,
                modified_by_id=test_user.id,
                owner_id=test_user.id,
            )
            db.add(stock)
            db.flush()
            stock.modified_at = same_time
            stocks.append(stock)
        db.commit()
        for s in stocks:
            db.refresh(s)

        # Sort IDs to know tie-breaking order (desc modified_at, then desc id)
        sorted_by_id_desc = sorted(stocks, key=lambda s: s.id, reverse=True)

        # Middle stock should have both prev and next
        middle = sorted_by_id_desc[1]
        response = authenticated_client.get(f"/api/stocks/{middle.id}/adjacent")
        assert response.status_code == 200
        data = response.json()

        assert data["prev_id"] == sorted_by_id_desc[0].id
        assert data["next_id"] == sorted_by_id_desc[2].id
