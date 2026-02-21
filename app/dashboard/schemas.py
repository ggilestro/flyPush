"""Pydantic schemas for the dashboard API."""

from datetime import datetime

from pydantic import BaseModel

from app.crosses.schemas import CrossReminderInfo
from app.flips.schemas import StockFlipInfo
from app.requests.schemas import StockRequestStats


class DashboardStats(BaseModel):
    """Core lab statistics."""

    total_stocks: int
    active_crosses: int
    total_tags: int
    recent_stocks_7d: int


class ActivityItem(BaseModel):
    """A single event in the activity feed."""

    event_type: str  # stock_created, stock_flipped, cross_created, cross_completed, cross_failed
    timestamp: datetime
    user_name: str | None = None
    entity_id: str
    entity_display_id: str  # human-readable (stock_id or cross name)
    description: str


class MonthlyCount(BaseModel):
    """Monthly aggregation for a simple count metric."""

    month: str  # "2026-01"
    label: str  # "Jan"
    count: int


class FlipComplianceMonth(BaseModel):
    """Monthly flip compliance breakdown."""

    month: str
    label: str
    on_time: int
    overdue: int
    compliance_pct: float


class CrossOutcomeMonth(BaseModel):
    """Monthly cross outcome breakdown."""

    month: str
    label: str
    completed: int
    failed: int
    success_pct: float


class ChartData(BaseModel):
    """All chart datasets for the dashboard."""

    stocks_per_month: list[MonthlyCount]
    flip_compliance: list[FlipComplianceMonth]
    cross_outcomes: list[CrossOutcomeMonth]


class DashboardResponse(BaseModel):
    """Complete dashboard payload returned by GET /api/dashboard."""

    stats: DashboardStats
    flip_alerts: list[StockFlipInfo]
    cross_reminders: list[CrossReminderInfo]
    request_stats: StockRequestStats
    activity: list[ActivityItem]
    charts: ChartData
