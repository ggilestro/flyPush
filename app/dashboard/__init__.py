"""Dashboard module for aggregated lab overview data."""

from app.dashboard.router import router
from app.dashboard.service import DashboardService, get_dashboard_service

__all__ = ["DashboardService", "get_dashboard_service", "router"]
