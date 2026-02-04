"""Tenants module for admin operations."""

from app.tenants.router import router
from app.tenants.service import TenantService

__all__ = ["router", "TenantService"]
