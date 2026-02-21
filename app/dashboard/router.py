"""Dashboard API routes."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.dashboard.schemas import DashboardResponse
from app.dashboard.service import DashboardService, get_dashboard_service


def _get_db():
    """Late import to avoid circular imports."""
    from app.dependencies import get_db

    return get_db


def _get_current_user():
    """Late import to avoid circular imports."""
    from app.dependencies import get_current_user

    return get_current_user


router = APIRouter()


def get_service(
    db: Annotated[Session, Depends(_get_db())],
    current_user=Depends(_get_current_user()),
) -> DashboardService:
    """Get dashboard service dependency."""
    return get_dashboard_service(db, str(current_user.tenant_id), str(current_user.id))


@router.get("", response_model=DashboardResponse)
async def get_dashboard(
    service: Annotated[DashboardService, Depends(get_service)],
):
    """Get aggregated dashboard data.

    Returns all data needed for the dashboard in a single response:
    stats, flip alerts, cross reminders, request stats, activity feed, and chart data.

    Args:
        service: Dashboard service.

    Returns:
        DashboardResponse: Complete dashboard payload.
    """
    return service.get_dashboard()
