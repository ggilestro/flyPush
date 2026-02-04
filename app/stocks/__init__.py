"""Stocks module."""

from app.stocks.router import router
from app.stocks.service import StockService

__all__ = ["router", "StockService"]
