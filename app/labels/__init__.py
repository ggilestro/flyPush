"""Labels module for QR/barcode generation."""

from app.labels.router import router
from app.labels.service import LabelService

__all__ = ["router", "LabelService"]
