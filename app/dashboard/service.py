"""Dashboard aggregation service."""

import calendar
from datetime import datetime, timedelta

from sqlalchemy import case, extract, func
from sqlalchemy.orm import Session, joinedload

from app.crosses.schemas import CrossReminderInfo
from app.crosses.service import get_cross_service
from app.dashboard.schemas import (
    ActivityItem,
    ChartData,
    CrossOutcomeMonth,
    DashboardResponse,
    DashboardStats,
    FlipComplianceMonth,
    MonthlyCount,
)
from app.db.models import Cross, CrossStatus, FlipEvent, Stock, Tag, Tenant
from app.flips.schemas import StockFlipInfo
from app.flips.service import get_flip_service
from app.requests.schemas import StockRequestStats
from app.requests.service import get_stock_request_service


class DashboardService:
    """Aggregates data from multiple services into a single dashboard payload.

    Args:
        db: Database session.
        tenant_id: Current tenant ID.
        user_id: Current user ID.
    """

    def __init__(self, db: Session, tenant_id: str, user_id: str):
        self.db = db
        self.tenant_id = tenant_id
        self.user_id = user_id

    def get_dashboard(self) -> DashboardResponse:
        """Build the complete dashboard response.

        Returns:
            DashboardResponse: Aggregated dashboard data.
        """
        return DashboardResponse(
            stats=self._get_stats(),
            flip_alerts=self._get_flip_alerts(),
            cross_reminders=self._get_cross_reminders(),
            request_stats=self._get_request_stats(),
            activity=self._get_activity_feed(),
            charts=self._get_chart_data(),
        )

    def _get_stats(self) -> DashboardStats:
        """Get core lab statistics."""
        seven_days_ago = datetime.utcnow() - timedelta(days=7)

        total_stocks = (
            self.db.query(func.count(Stock.id))
            .filter(Stock.tenant_id == self.tenant_id, Stock.is_active.is_(True))
            .scalar()
        )

        active_crosses = (
            self.db.query(func.count(Cross.id))
            .filter(
                Cross.tenant_id == self.tenant_id,
                Cross.status.in_([CrossStatus.PLANNED, CrossStatus.IN_PROGRESS]),
            )
            .scalar()
        )

        total_tags = (
            self.db.query(func.count(Tag.id)).filter(Tag.tenant_id == self.tenant_id).scalar()
        )

        recent_stocks_7d = (
            self.db.query(func.count(Stock.id))
            .filter(
                Stock.tenant_id == self.tenant_id,
                Stock.is_active.is_(True),
                Stock.created_at >= seven_days_ago,
            )
            .scalar()
        )

        return DashboardStats(
            total_stocks=total_stocks or 0,
            active_crosses=active_crosses or 0,
            total_tags=total_tags or 0,
            recent_stocks_7d=recent_stocks_7d or 0,
        )

    def _get_flip_alerts(self) -> list[StockFlipInfo]:
        """Get critical + warning flip alerts, capped at 10."""
        svc = get_flip_service(self.db, self.tenant_id, self.user_id)
        result = svc.get_stocks_needing_flip()
        # Reason: critical first, then warning — most urgent on top
        alerts = result.critical + result.warning
        return alerts[:10]

    def _get_cross_reminders(self) -> list[CrossReminderInfo]:
        """Get crosses needing timeline reminders."""
        svc = get_cross_service(self.db, self.tenant_id)
        return svc.get_crosses_needing_reminders()

    def _get_request_stats(self) -> StockRequestStats:
        """Get stock request statistics."""
        svc = get_stock_request_service(self.db, self.tenant_id, self.user_id)
        return svc.get_stats()

    def _get_activity_feed(self, limit: int = 10) -> list[ActivityItem]:
        """Get the most recent lab events across stocks, flips, and crosses.

        Args:
            limit: Maximum events to return.

        Returns:
            list[ActivityItem]: Recent events sorted by timestamp descending.
        """
        fourteen_days_ago = datetime.utcnow() - timedelta(days=14)
        items: list[ActivityItem] = []

        # Recent stocks created
        stocks = (
            self.db.query(Stock)
            .options(joinedload(Stock.created_by))
            .filter(
                Stock.tenant_id == self.tenant_id,
                Stock.is_active.is_(True),
                Stock.created_at >= fourteen_days_ago,
            )
            .order_by(Stock.created_at.desc())
            .limit(limit)
            .all()
        )
        for s in stocks:
            user_name = s.created_by.full_name if s.created_by else None
            items.append(
                ActivityItem(
                    event_type="stock_created",
                    timestamp=s.created_at,
                    user_name=user_name,
                    entity_id=s.id,
                    entity_display_id=s.stock_id,
                    description=f"Added stock {s.stock_id}",
                )
            )

        # Recent flip events
        flips = (
            self.db.query(FlipEvent)
            .join(Stock, FlipEvent.stock_id == Stock.id)
            .options(joinedload(FlipEvent.flipped_by), joinedload(FlipEvent.stock))
            .filter(
                Stock.tenant_id == self.tenant_id,
                FlipEvent.flipped_at >= fourteen_days_ago,
            )
            .order_by(FlipEvent.flipped_at.desc())
            .limit(limit)
            .all()
        )
        for f in flips:
            user_name = f.flipped_by.full_name if f.flipped_by else None
            items.append(
                ActivityItem(
                    event_type="stock_flipped",
                    timestamp=f.flipped_at,
                    user_name=user_name,
                    entity_id=f.stock_id,
                    entity_display_id=f.stock.stock_id if f.stock else f.stock_id,
                    description=f"Flipped stock {f.stock.stock_id if f.stock else f.stock_id}",
                )
            )

        # Recent crosses (created, completed, failed)
        crosses = (
            self.db.query(Cross)
            .options(joinedload(Cross.created_by))
            .filter(
                Cross.tenant_id == self.tenant_id,
                Cross.created_at >= fourteen_days_ago,
            )
            .order_by(Cross.created_at.desc())
            .limit(limit)
            .all()
        )
        for c in crosses:
            user_name = c.created_by.full_name if c.created_by else None
            display_id = c.name or c.id[:8]

            if c.status == CrossStatus.COMPLETED:
                event_type = "cross_completed"
                desc = f"Completed cross {display_id}"
            elif c.status == CrossStatus.FAILED:
                event_type = "cross_failed"
                desc = f"Cross {display_id} failed"
            else:
                event_type = "cross_created"
                desc = f"Created cross {display_id}"

            items.append(
                ActivityItem(
                    event_type=event_type,
                    timestamp=c.created_at,
                    user_name=user_name,
                    entity_id=c.id,
                    entity_display_id=display_id,
                    description=desc,
                )
            )

        # Sort all items by timestamp descending and take top N
        items.sort(key=lambda x: x.timestamp, reverse=True)
        return items[:limit]

    def _get_chart_data(self) -> ChartData:
        """Build chart datasets for the last 6 months.

        Returns:
            ChartData: Stocks per month, flip compliance, cross outcomes.
        """
        return ChartData(
            stocks_per_month=self._stocks_per_month(),
            flip_compliance=self._flip_compliance(),
            cross_outcomes=self._cross_outcomes(),
        )

    def _month_range(self, months: int = 6) -> list[tuple[int, int]]:
        """Get (year, month) pairs for the last N months including current.

        Args:
            months: Number of months to look back.

        Returns:
            list[tuple[int, int]]: Ordered (year, month) pairs.
        """
        now = datetime.utcnow()
        result = []
        for i in range(months - 1, -1, -1):
            # Reason: subtract months by computing total_months to handle year boundaries
            total_months = now.year * 12 + (now.month - 1) - i
            y = total_months // 12
            m = total_months % 12 + 1
            result.append((y, m))
        return result

    def _month_start(self, months_ago: int = 6) -> datetime:
        """Get the start datetime for N months ago.

        Args:
            months_ago: How many months back.

        Returns:
            datetime: First day of the target month at midnight.
        """
        pairs = self._month_range(months_ago)
        y, m = pairs[0]
        return datetime(y, m, 1)

    def _stocks_per_month(self) -> list[MonthlyCount]:
        """Count stocks created per month for the last 6 months."""
        start = self._month_start(6)
        rows = (
            self.db.query(
                extract("year", Stock.created_at).label("y"),
                extract("month", Stock.created_at).label("m"),
                func.count(Stock.id).label("cnt"),
            )
            .filter(
                Stock.tenant_id == self.tenant_id,
                Stock.is_active.is_(True),
                Stock.created_at >= start,
            )
            .group_by("y", "m")
            .all()
        )

        counts = {(int(r.y), int(r.m)): int(r.cnt) for r in rows}
        return [
            MonthlyCount(
                month=f"{y:04d}-{m:02d}",
                label=calendar.month_abbr[m],
                count=counts.get((y, m), 0),
            )
            for y, m in self._month_range(6)
        ]

    def _flip_compliance(self) -> list[FlipComplianceMonth]:
        """Calculate flip compliance per month for the last 6 months.

        For each flip event, compute the gap from the previous flip (or stock creation).
        Classify as on_time if gap < tenant's flip_critical_days, else overdue.
        """
        start = self._month_start(6)

        tenant = self.db.query(Tenant).filter(Tenant.id == self.tenant_id).first()
        critical_days = tenant.flip_critical_days if tenant else 31

        # Get all flip events for this tenant in the window
        flips = (
            self.db.query(FlipEvent)
            .join(Stock, FlipEvent.stock_id == Stock.id)
            .filter(
                Stock.tenant_id == self.tenant_id,
                FlipEvent.flipped_at >= start,
            )
            .order_by(FlipEvent.stock_id, FlipEvent.flipped_at)
            .all()
        )

        if not flips:
            return [
                FlipComplianceMonth(
                    month=f"{y:04d}-{m:02d}",
                    label=calendar.month_abbr[m],
                    on_time=0,
                    overdue=0,
                    compliance_pct=0.0,
                )
                for y, m in self._month_range(6)
            ]

        # Build lookup: stock_id -> list of flip_at dates (ordered)
        stock_flip_dates: dict[str, list[datetime]] = {}
        for f in flips:
            stock_flip_dates.setdefault(f.stock_id, []).append(f.flipped_at)

        # For first flip per stock, get stock creation date as baseline
        stock_ids = list(stock_flip_dates.keys())
        stocks_created = {
            s.id: s.created_at
            for s in self.db.query(Stock.id, Stock.created_at).filter(Stock.id.in_(stock_ids)).all()
        }

        # Classify each flip event
        monthly: dict[tuple[int, int], dict[str, int]] = {}
        for stock_id, dates in stock_flip_dates.items():
            baseline = stocks_created.get(stock_id) or dates[0]
            for i, flip_at in enumerate(dates):
                prev = dates[i - 1] if i > 0 else baseline
                gap_days = (flip_at - prev).days
                key = (flip_at.year, flip_at.month)
                bucket = monthly.setdefault(key, {"on_time": 0, "overdue": 0})
                if gap_days <= critical_days:
                    bucket["on_time"] += 1
                else:
                    bucket["overdue"] += 1

        return [
            FlipComplianceMonth(
                month=f"{y:04d}-{m:02d}",
                label=calendar.month_abbr[m],
                on_time=monthly.get((y, m), {}).get("on_time", 0),
                overdue=monthly.get((y, m), {}).get("overdue", 0),
                compliance_pct=round(
                    monthly.get((y, m), {}).get("on_time", 0)
                    / max(
                        monthly.get((y, m), {}).get("on_time", 0)
                        + monthly.get((y, m), {}).get("overdue", 0),
                        1,
                    )
                    * 100,
                    1,
                ),
            )
            for y, m in self._month_range(6)
        ]

    def _cross_outcomes(self) -> list[CrossOutcomeMonth]:
        """Count completed vs failed crosses per month for the last 6 months."""
        start = self._month_start(6)

        rows = (
            self.db.query(
                extract("year", Cross.created_at).label("y"),
                extract("month", Cross.created_at).label("m"),
                func.sum(case((Cross.status == CrossStatus.COMPLETED, 1), else_=0)).label(
                    "completed"
                ),
                func.sum(case((Cross.status == CrossStatus.FAILED, 1), else_=0)).label("failed"),
            )
            .filter(
                Cross.tenant_id == self.tenant_id,
                Cross.status.in_([CrossStatus.COMPLETED, CrossStatus.FAILED]),
                Cross.created_at >= start,
            )
            .group_by("y", "m")
            .all()
        )

        data = {(int(r.y), int(r.m)): (int(r.completed), int(r.failed)) for r in rows}
        return [
            CrossOutcomeMonth(
                month=f"{y:04d}-{m:02d}",
                label=calendar.month_abbr[m],
                completed=data.get((y, m), (0, 0))[0],
                failed=data.get((y, m), (0, 0))[1],
                success_pct=round(
                    data.get((y, m), (0, 0))[0] / max(sum(data.get((y, m), (0, 0))), 1) * 100,
                    1,
                ),
            )
            for y, m in self._month_range(6)
        ]


def get_dashboard_service(db: Session, tenant_id: str, user_id: str) -> DashboardService:
    """Factory function for DashboardService.

    Args:
        db: Database session.
        tenant_id: Tenant ID.
        user_id: User ID.

    Returns:
        DashboardService: Service instance.
    """
    return DashboardService(db, tenant_id, user_id)
