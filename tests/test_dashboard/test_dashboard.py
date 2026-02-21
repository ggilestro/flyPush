"""Tests for the dashboard API endpoint."""

from datetime import datetime, timedelta
from uuid import uuid4

from app.db.models import Cross, CrossStatus, FlipEvent, Stock, Tag


def _make_stock(db, tenant_id, user_id, stock_id="BL-001", created_at=None):
    """Create a test stock.

    Args:
        db: Database session.
        tenant_id: Tenant UUID.
        user_id: Creator user UUID.
        stock_id: Human-readable stock ID.
        created_at: Optional creation timestamp.

    Returns:
        Stock: The created stock.
    """
    stock = Stock(
        id=str(uuid4()),
        tenant_id=tenant_id,
        stock_id=stock_id,
        genotype="w[*]; +; +",
        is_active=True,
        created_by_id=user_id,
        created_at=created_at or datetime.utcnow(),
    )
    db.add(stock)
    db.commit()
    db.refresh(stock)
    return stock


def _make_cross(db, tenant_id, user_id, female, male, status=CrossStatus.PLANNED, created_at=None):
    """Create a test cross.

    Args:
        db: Database session.
        tenant_id: Tenant UUID.
        user_id: Creator user UUID.
        female: Female parent stock.
        male: Male parent stock.
        status: Cross status.
        created_at: Optional creation timestamp.

    Returns:
        Cross: The created cross.
    """
    cross = Cross(
        id=str(uuid4()),
        tenant_id=tenant_id,
        name=f"{female.stock_id} x {male.stock_id}",
        parent_female_id=female.id,
        parent_male_id=male.id,
        status=status,
        created_by_id=user_id,
        created_at=created_at or datetime.utcnow(),
    )
    db.add(cross)
    db.commit()
    db.refresh(cross)
    return cross


class TestDashboardAuth:
    """Test authentication requirements."""

    def test_unauthenticated_returns_401(self, client):
        """Unauthenticated request should return 401."""
        response = client.get("/api/dashboard")
        assert response.status_code == 401


class TestDashboardEmptyLab:
    """Test dashboard with no data."""

    def test_empty_lab_returns_valid_response(self, authenticated_client, test_user):
        """Empty lab should return valid zeros and empty arrays."""
        response = authenticated_client.get("/api/dashboard")
        assert response.status_code == 200
        data = response.json()

        assert data["stats"]["total_stocks"] == 0
        assert data["stats"]["active_crosses"] == 0
        assert data["stats"]["total_tags"] == 0
        assert data["stats"]["recent_stocks_7d"] == 0
        assert data["flip_alerts"] == []
        assert data["cross_reminders"] == []
        assert data["activity"] == []
        assert data["request_stats"]["pending_incoming"] == 0
        assert len(data["charts"]["stocks_per_month"]) == 6
        assert len(data["charts"]["flip_compliance"]) == 6
        assert len(data["charts"]["cross_outcomes"]) == 6


class TestDashboardStats:
    """Test stat counting."""

    def test_stats_count_stocks(self, authenticated_client, db, test_tenant, test_user):
        """Stats should count active stocks correctly."""
        _make_stock(db, test_tenant.id, test_user.id, "BL-001")
        _make_stock(db, test_tenant.id, test_user.id, "BL-002")
        # Inactive stock should not be counted
        inactive = Stock(
            id=str(uuid4()),
            tenant_id=test_tenant.id,
            stock_id="BL-003",
            genotype="w[*]",
            is_active=False,
            created_by_id=test_user.id,
        )
        db.add(inactive)
        db.commit()

        response = authenticated_client.get("/api/dashboard")
        assert response.status_code == 200
        assert response.json()["stats"]["total_stocks"] == 2

    def test_recent_stocks_7d_only_counts_last_week(self, authenticated_client, db, test_tenant, test_user):
        """recent_stocks_7d should only count stocks created in the last 7 days."""
        # Recent stock
        _make_stock(db, test_tenant.id, test_user.id, "BL-001")
        # Old stock (30 days ago)
        _make_stock(
            db, test_tenant.id, test_user.id, "BL-002",
            created_at=datetime.utcnow() - timedelta(days=30),
        )

        response = authenticated_client.get("/api/dashboard")
        assert response.status_code == 200
        data = response.json()
        assert data["stats"]["recent_stocks_7d"] == 1
        assert data["stats"]["total_stocks"] == 2

    def test_active_crosses_counted(self, authenticated_client, db, test_tenant, test_user):
        """Active crosses should include PLANNED and IN_PROGRESS."""
        female = _make_stock(db, test_tenant.id, test_user.id, "BL-F1")
        male = _make_stock(db, test_tenant.id, test_user.id, "BL-M1")
        _make_cross(db, test_tenant.id, test_user.id, female, male, CrossStatus.PLANNED)
        _make_cross(db, test_tenant.id, test_user.id, female, male, CrossStatus.IN_PROGRESS)
        _make_cross(db, test_tenant.id, test_user.id, female, male, CrossStatus.COMPLETED)

        response = authenticated_client.get("/api/dashboard")
        assert response.status_code == 200
        assert response.json()["stats"]["active_crosses"] == 2

    def test_tags_counted(self, authenticated_client, db, test_tenant):
        """Tags should be counted."""
        for name in ["tag1", "tag2", "tag3"]:
            db.add(Tag(id=str(uuid4()), tenant_id=test_tenant.id, name=name))
        db.commit()

        response = authenticated_client.get("/api/dashboard")
        assert response.status_code == 200
        assert response.json()["stats"]["total_tags"] == 3


class TestDashboardFlipAlerts:
    """Test flip alert data."""

    def test_flip_alerts_for_old_stocks(self, authenticated_client, db, test_tenant, test_user):
        """Stocks past the critical flip threshold should appear as alerts."""
        stock = _make_stock(
            db, test_tenant.id, test_user.id, "BL-OLD",
            created_at=datetime.utcnow() - timedelta(days=60),
        )
        # Add a flip from 40 days ago (past default 31-day critical)
        flip = FlipEvent(
            id=str(uuid4()),
            stock_id=stock.id,
            flipped_by_id=test_user.id,
            flipped_at=datetime.utcnow() - timedelta(days=40),
        )
        db.add(flip)
        db.commit()

        response = authenticated_client.get("/api/dashboard")
        assert response.status_code == 200
        alerts = response.json()["flip_alerts"]
        assert len(alerts) >= 1
        display_ids = [a["stock_display_id"] for a in alerts]
        assert "BL-OLD" in display_ids

    def test_flip_alerts_capped_at_10(self, authenticated_client, db, test_tenant, test_user):
        """Flip alerts should be capped at 10."""
        for i in range(15):
            stock = _make_stock(
                db, test_tenant.id, test_user.id, f"BL-{i:03d}",
                created_at=datetime.utcnow() - timedelta(days=60),
            )
            # Add old flip to make it critical
            db.add(FlipEvent(
                id=str(uuid4()),
                stock_id=stock.id,
                flipped_at=datetime.utcnow() - timedelta(days=40),
            ))
        db.commit()

        response = authenticated_client.get("/api/dashboard")
        assert response.status_code == 200
        assert len(response.json()["flip_alerts"]) <= 10


class TestDashboardActivityFeed:
    """Test activity feed."""

    def test_activity_includes_recent_stocks(self, authenticated_client, db, test_tenant, test_user):
        """Activity feed should include recently created stocks."""
        _make_stock(db, test_tenant.id, test_user.id, "BL-NEW")

        response = authenticated_client.get("/api/dashboard")
        assert response.status_code == 200
        activity = response.json()["activity"]
        assert any(a["event_type"] == "stock_created" for a in activity)
        assert any("BL-NEW" in a["description"] for a in activity)

    def test_activity_sorted_by_timestamp_desc(self, authenticated_client, db, test_tenant, test_user):
        """Activity feed should be sorted newest first."""
        _make_stock(
            db, test_tenant.id, test_user.id, "BL-OLD",
            created_at=datetime.utcnow() - timedelta(days=5),
        )
        _make_stock(db, test_tenant.id, test_user.id, "BL-NEW")

        response = authenticated_client.get("/api/dashboard")
        assert response.status_code == 200
        activity = response.json()["activity"]
        assert len(activity) >= 2
        # First item should be more recent
        ts0 = datetime.fromisoformat(activity[0]["timestamp"])
        ts1 = datetime.fromisoformat(activity[1]["timestamp"])
        assert ts0 >= ts1


class TestDashboardCharts:
    """Test chart data."""

    def test_stocks_per_month_chart(self, authenticated_client, db, test_tenant, test_user):
        """Stocks per month should reflect creation dates."""
        _make_stock(db, test_tenant.id, test_user.id, "BL-001")
        _make_stock(db, test_tenant.id, test_user.id, "BL-002")

        response = authenticated_client.get("/api/dashboard")
        assert response.status_code == 200
        spm = response.json()["charts"]["stocks_per_month"]
        assert len(spm) == 6
        # Current month should have count >= 2
        current = spm[-1]
        assert current["count"] >= 2

    def test_cross_outcomes_chart(self, authenticated_client, db, test_tenant, test_user):
        """Cross outcomes chart should show completed vs failed."""
        female = _make_stock(db, test_tenant.id, test_user.id, "BL-F1")
        male = _make_stock(db, test_tenant.id, test_user.id, "BL-M1")
        _make_cross(db, test_tenant.id, test_user.id, female, male, CrossStatus.COMPLETED)
        _make_cross(db, test_tenant.id, test_user.id, female, male, CrossStatus.FAILED)

        response = authenticated_client.get("/api/dashboard")
        assert response.status_code == 200
        co = response.json()["charts"]["cross_outcomes"]
        assert len(co) == 6
        current = co[-1]
        assert current["completed"] >= 1
        assert current["failed"] >= 1


class TestDashboardTenantIsolation:
    """Test multi-tenant isolation."""

    def test_other_tenant_data_not_visible(self, authenticated_client, db, test_tenant, test_user):
        """Data from other tenants should not appear."""
        from app.db.models import Tenant

        other_tenant = Tenant(
            id=str(uuid4()),
            name="Other Lab",
            slug="other-lab",
            is_active=True,
        )
        db.add(other_tenant)
        db.commit()

        # Create stock in other tenant
        _make_stock(db, other_tenant.id, test_user.id, "OTHER-001")
        # Create stock in our tenant
        _make_stock(db, test_tenant.id, test_user.id, "BL-001")

        response = authenticated_client.get("/api/dashboard")
        assert response.status_code == 200
        data = response.json()
        assert data["stats"]["total_stocks"] == 1
        # Activity should only show our tenant's stock
        for item in data["activity"]:
            assert "OTHER" not in item["entity_display_id"]


class TestDashboardRequestStats:
    """Test request stats are included."""

    def test_request_stats_present(self, authenticated_client, test_user):
        """Response should include request stats fields."""
        response = authenticated_client.get("/api/dashboard")
        assert response.status_code == 200
        rs = response.json()["request_stats"]
        assert "pending_incoming" in rs
        assert "pending_outgoing" in rs
        assert "approved_outgoing" in rs
        assert "fulfilled_total" in rs
