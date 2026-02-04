"""Pydantic schemas for crosses."""

from datetime import datetime, date
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.db.models import CrossStatus


class CrossBase(BaseModel):
    """Base schema for crosses."""

    name: Optional[str] = Field(None, max_length=255)
    parent_female_id: str
    parent_male_id: str
    planned_date: Optional[date] = None
    notes: Optional[str] = None


class CrossCreate(CrossBase):
    """Schema for creating a cross."""

    pass


class CrossUpdate(BaseModel):
    """Schema for updating a cross."""

    name: Optional[str] = Field(None, max_length=255)
    planned_date: Optional[date] = None
    executed_date: Optional[date] = None
    status: Optional[CrossStatus] = None
    notes: Optional[str] = None
    offspring_id: Optional[str] = None


class StockSummary(BaseModel):
    """Brief stock info for cross display."""

    id: str
    stock_id: str
    genotype: str

    model_config = ConfigDict(from_attributes=True)


class CrossResponse(BaseModel):
    """Schema for cross response."""

    id: str
    name: Optional[str]
    parent_female: StockSummary
    parent_male: StockSummary
    offspring: Optional[StockSummary] = None
    planned_date: Optional[date]
    executed_date: Optional[date]
    status: CrossStatus
    expected_outcomes: Optional[dict] = None
    notes: Optional[str]
    created_at: datetime
    created_by_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class CrossListResponse(BaseModel):
    """Schema for paginated cross list response."""

    items: list[CrossResponse]
    total: int
    page: int
    page_size: int
    pages: int


class CrossSearchParams(BaseModel):
    """Schema for cross search parameters."""

    query: Optional[str] = None
    status: Optional[CrossStatus] = None
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)


class CrossComplete(BaseModel):
    """Schema for marking a cross as completed."""

    offspring_id: Optional[str] = None
    notes: Optional[str] = None
