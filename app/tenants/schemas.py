"""Pydantic schemas for tenant administration."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.db.models import UserRole


class UserInvite(BaseModel):
    """Schema for inviting a new user."""

    email: EmailStr
    full_name: str = Field(..., min_length=2, max_length=255)
    role: UserRole = UserRole.USER


class UserUpdateAdmin(BaseModel):
    """Schema for admin updating a user."""

    full_name: Optional[str] = Field(None, min_length=2, max_length=255)
    email: Optional[EmailStr] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None


class UserListResponse(BaseModel):
    """Schema for user list item."""

    id: str
    email: str
    full_name: str
    role: str
    is_active: bool
    created_at: datetime
    last_login: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class OrganizationInfo(BaseModel):
    """Schema for organization info in tenant response."""

    id: str
    name: str
    slug: str


class TenantResponse(BaseModel):
    """Schema for tenant information."""

    id: str
    name: str
    slug: str
    is_active: bool
    created_at: datetime
    user_count: int
    stock_count: int
    # New organization fields
    organization: Optional[OrganizationInfo] = None
    is_org_admin: bool = False
    city: Optional[str] = None
    country: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)


class TenantUpdate(BaseModel):
    """Schema for updating tenant."""

    name: Optional[str] = Field(None, min_length=2, max_length=255)
