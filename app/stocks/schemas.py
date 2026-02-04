"""Pydantic schemas for stocks."""

import enum
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.db.models import StockVisibility, StockOrigin, StockRepository


class StockScope(str, enum.Enum):
    """Stock search scope enumeration."""

    LAB = "lab"  # Only stocks from current lab
    ORGANIZATION = "organization"  # Stocks visible within organization
    PUBLIC = "public"  # All public stocks


class TagBase(BaseModel):
    """Base schema for tags."""

    name: str = Field(..., min_length=1, max_length=100)
    color: Optional[str] = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$")


class TagCreate(TagBase):
    """Schema for creating a tag."""

    pass


class TagResponse(TagBase):
    """Schema for tag response."""

    id: str

    model_config = ConfigDict(from_attributes=True)


class TrayInfo(BaseModel):
    """Schema for tray info in stock response."""

    id: str
    name: str


class OwnerInfo(BaseModel):
    """Schema for owner info in stock response."""

    id: str
    full_name: str


class TenantInfo(BaseModel):
    """Schema for tenant info in stock response (for cross-lab visibility)."""

    id: str
    name: str
    city: Optional[str] = None
    country: Optional[str] = None


class StockBase(BaseModel):
    """Base schema for stocks."""

    stock_id: str = Field(..., min_length=1, max_length=100)
    genotype: str = Field(..., min_length=1)
    # Origin tracking
    origin: StockOrigin = StockOrigin.INTERNAL
    repository: Optional[StockRepository] = None  # Only if origin=repository
    repository_stock_id: Optional[str] = Field(None, max_length=50)
    external_source: Optional[str] = Field(None, max_length=255)  # Only if origin=external
    original_genotype: Optional[str] = None  # Original from repository
    notes: Optional[str] = None


class StockCreate(StockBase):
    """Schema for creating a stock."""

    tag_ids: list[str] = Field(default_factory=list)
    tray_id: Optional[str] = None
    position: Optional[str] = Field(None, max_length=20)
    owner_id: Optional[str] = None  # Defaults to created_by_id
    visibility: StockVisibility = StockVisibility.LAB_ONLY
    hide_from_org: bool = False


class StockUpdate(BaseModel):
    """Schema for updating a stock."""

    stock_id: Optional[str] = Field(None, min_length=1, max_length=100)
    genotype: Optional[str] = Field(None, min_length=1)
    # Origin tracking
    origin: Optional[StockOrigin] = None
    repository: Optional[StockRepository] = None
    repository_stock_id: Optional[str] = Field(None, max_length=50)
    external_source: Optional[str] = Field(None, max_length=255)
    original_genotype: Optional[str] = None
    notes: Optional[str] = None
    tag_ids: Optional[list[str]] = None
    tray_id: Optional[str] = None
    position: Optional[str] = Field(None, max_length=20)
    owner_id: Optional[str] = None
    visibility: Optional[StockVisibility] = None
    hide_from_org: Optional[bool] = None


class StockResponse(StockBase):
    """Schema for stock response."""

    id: str
    is_active: bool
    created_at: datetime
    modified_at: datetime
    created_by_name: Optional[str] = None
    modified_by_name: Optional[str] = None
    tags: list[TagResponse] = Field(default_factory=list)
    # Physical location
    tray: Optional[TrayInfo] = None
    position: Optional[str] = None
    owner: Optional[OwnerInfo] = None
    visibility: StockVisibility = StockVisibility.LAB_ONLY
    hide_from_org: bool = False
    # For cross-lab visibility
    tenant: Optional[TenantInfo] = None

    model_config = ConfigDict(from_attributes=True)


class StockListResponse(BaseModel):
    """Schema for paginated stock list response."""

    items: list[StockResponse]
    total: int
    page: int
    page_size: int
    pages: int


class StockSearchParams(BaseModel):
    """Schema for stock search parameters."""

    query: Optional[str] = None
    tag_ids: Optional[list[str]] = None
    origin: Optional[StockOrigin] = None
    repository: Optional[StockRepository] = None
    tray_id: Optional[str] = None
    owner_id: Optional[str] = None
    visibility: Optional[StockVisibility] = None
    scope: StockScope = StockScope.LAB
    is_active: bool = True
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)
