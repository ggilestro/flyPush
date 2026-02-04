"""Pydantic schemas for stock requests."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.db.models import StockRequestStatus


class StockRequestCreate(BaseModel):
    """Schema for creating a stock request."""

    stock_id: str
    message: Optional[str] = None


class StockRequestRespond(BaseModel):
    """Schema for responding to a stock request."""

    response_message: Optional[str] = None


class StockRequestResponse(BaseModel):
    """Schema for stock request response."""

    id: str
    stock_id: str
    stock_name: str  # stock.stock_id
    stock_genotype: str
    requester_user_id: Optional[str] = None
    requester_user_name: Optional[str] = None
    requester_tenant_id: str
    requester_tenant_name: str
    owner_tenant_id: str
    owner_tenant_name: str
    status: StockRequestStatus
    message: Optional[str] = None
    response_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    responded_at: Optional[datetime] = None
    responded_by_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class StockRequestListResponse(BaseModel):
    """Schema for paginated stock request list."""

    items: list[StockRequestResponse]
    total: int
    page: int
    page_size: int
    pages: int


class StockRequestStats(BaseModel):
    """Schema for stock request statistics."""

    pending_incoming: int
    pending_outgoing: int
    approved_outgoing: int
    fulfilled_total: int
