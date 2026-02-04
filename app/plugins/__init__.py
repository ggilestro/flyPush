"""Plugins module for external integrations."""

from app.plugins.base import StockPlugin, StockImportData
from app.plugins.flybase.client import (
    FlyBasePlugin,
    get_flybase_plugin,
    # Backward compatibility aliases
    BDSCPlugin,
    get_bdsc_plugin,
)

__all__ = [
    "StockPlugin",
    "StockImportData",
    "FlyBasePlugin",
    "get_flybase_plugin",
    # Backward compatibility
    "BDSCPlugin",
    "get_bdsc_plugin",
]
