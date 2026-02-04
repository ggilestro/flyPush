"""FlyBase Stock Database plugin.

Provides unified access to all stock centers available in FlyBase data.
"""

from app.plugins.flybase.client import (
    FlyBasePlugin,
    get_flybase_plugin,
    # Backward compatibility aliases
    BDSCPlugin,
    get_bdsc_plugin,
)
from app.plugins.flybase.data_loader import (
    FlyBaseDataLoader,
    COLLECTION_TO_REPOSITORY,
    REPOSITORY_NAMES,
    REPOSITORY_URLS,
    get_flybase_url,
    get_repository_url,
    get_bdsc_search_url,
)

__all__ = [
    # Main exports
    "FlyBasePlugin",
    "get_flybase_plugin",
    "FlyBaseDataLoader",
    "COLLECTION_TO_REPOSITORY",
    "REPOSITORY_NAMES",
    "REPOSITORY_URLS",
    "get_flybase_url",
    "get_repository_url",
    # Backward compatibility
    "BDSCPlugin",
    "get_bdsc_plugin",
    "get_bdsc_search_url",
]
