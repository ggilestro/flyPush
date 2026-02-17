"""Dashboard KPI aggregations."""

from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.db.models import Cross, Organization, Stock, Tenant, User


def get_overview(db: Session) -> dict:
    """Total counts for KPI cards."""
    tenants_total = db.query(func.count(Tenant.id)).scalar() or 0
    tenants_active = (
        db.query(func.count(Tenant.id)).filter(Tenant.is_active.is_(True)).scalar() or 0
    )
    users_total = db.query(func.count(User.id)).scalar() or 0
    users_active = db.query(func.count(User.id)).filter(User.is_active.is_(True)).scalar() or 0
    stocks_total = db.query(func.count(Stock.id)).scalar() or 0
    crosses_total = db.query(func.count(Cross.id)).scalar() or 0
    orgs_total = db.query(func.count(Organization.id)).scalar() or 0

    return {
        "tenants_total": tenants_total,
        "tenants_active": tenants_active,
        "users_total": users_total,
        "users_active": users_active,
        "stocks_total": stocks_total,
        "crosses_total": crosses_total,
        "organizations_total": orgs_total,
    }


def get_plan_distribution(db: Session) -> list[dict]:
    """Tenant counts grouped by plan tier."""
    rows = db.query(Tenant.plan, func.count(Tenant.id).label("count")).group_by(Tenant.plan).all()
    return [{"plan": r.plan.value if r.plan else "unknown", "count": r.count} for r in rows]


def get_subscription_status(db: Session) -> list[dict]:
    """Tenant counts grouped by subscription status."""
    rows = (
        db.query(Tenant.subscription_status, func.count(Tenant.id).label("count"))
        .group_by(Tenant.subscription_status)
        .all()
    )
    return [
        {
            "status": r.subscription_status.value if r.subscription_status else "unknown",
            "count": r.count,
        }
        for r in rows
    ]


def get_growth(db: Session) -> dict:
    """Monthly tenant and user creation time series."""
    tenant_rows = (
        db.query(
            func.date_format(Tenant.created_at, "%Y-%m").label("month"),
            func.count(Tenant.id).label("count"),
        )
        .group_by(text("month"))
        .order_by(text("month"))
        .all()
    )
    user_rows = (
        db.query(
            func.date_format(User.created_at, "%Y-%m").label("month"),
            func.count(User.id).label("count"),
        )
        .group_by(text("month"))
        .order_by(text("month"))
        .all()
    )
    return {
        "tenants": [{"month": r.month, "count": r.count} for r in tenant_rows],
        "users": [{"month": r.month, "count": r.count} for r in user_rows],
    }


def get_top_tenants(db: Session, limit: int = 10) -> list[dict]:
    """Top tenants by stock count."""
    rows = (
        db.query(
            Tenant.id,
            Tenant.name,
            Tenant.plan,
            func.count(Stock.id).label("stock_count"),
        )
        .outerjoin(Stock, Stock.tenant_id == Tenant.id)
        .group_by(Tenant.id, Tenant.name, Tenant.plan)
        .order_by(func.count(Stock.id).desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": r.id,
            "name": r.name,
            "plan": r.plan.value if r.plan else "unknown",
            "stock_count": r.stock_count,
        }
        for r in rows
    ]
