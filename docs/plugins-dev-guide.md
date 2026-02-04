# Plugins Developer Guide

This guide explains the plugin architecture for integrating external stock databases.

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [BDSC Plugin Implementation](#bdsc-plugin-implementation)
3. [Creating a New Plugin](#creating-a-new-plugin)
4. [API Reference](#api-reference)
5. [Data Flow](#data-flow)
6. [Testing Plugins](#testing-plugins)
7. [Deployment Considerations](#deployment-considerations)

---

## Architecture Overview

The plugin system allows integration with external stock databases (BDSC, VDRC, Kyoto, etc.) through a common interface.

### Directory Structure

```
app/plugins/
├── __init__.py           # Exports base classes
├── base.py               # Abstract plugin interface
├── schemas.py            # Pydantic schemas for API
├── router.py             # FastAPI endpoints
└── bdsc/                 # BDSC plugin implementation
    ├── __init__.py
    ├── client.py         # Main plugin class
    └── data_loader.py    # Data fetching/caching
```

### Key Components

| Component | Purpose |
|-----------|---------|
| `StockPlugin` | Abstract base class defining the plugin interface |
| `StockImportData` | Data model for stocks from external sources |
| `FlyBaseDataLoader` | Downloads and caches FlyBase bulk data |
| `BDSCPlugin` | Concrete implementation for BDSC |
| Plugin Router | REST API endpoints for search/import |

---

## BDSC Plugin Implementation

The BDSC plugin demonstrates the recommended approach for integrating external databases.

### Data Strategy

BDSC doesn't provide a public API, so we use FlyBase bulk data files:

```
https://s3ftp.flybase.org/releases/current/precomputed_files/stocks/stocks_FB*.tsv.gz
```

**Why this approach?**
- No web scraping (stable, no HTML parsing)
- Complete dataset (~90,000 BDSC stocks)
- Fast local searches (O(1) lookup by stock number)
- Works offline after initial download
- Automatic refresh capability

### Data Flow

```
┌─────────────────┐
│    FlyBase      │
│  (TSV.gz file)  │
└────────┬────────┘
         │ Download (on first use)
         ▼
┌─────────────────┐
│  Local Cache    │
│  data/flybase/  │
└────────┬────────┘
         │ Parse & Filter (Bloomington only)
         ▼
┌─────────────────┐
│  Memory Index   │
│  {stock_num: {}}│
└────────┬────────┘
         │ Search/Lookup
         ▼
┌─────────────────┐
│  API Response   │
│  StockImportData│
└─────────────────┘
```

### FlyBase TSV Format

| Column | Description | Example |
|--------|-------------|---------|
| `FBst` | FlyBase stock ID | FBst0080563 |
| `collection_short_name` | Stock center | Bloomington |
| `stock_type_cv` | Stock state | living stock ; FBsv:0000002 |
| `species` | Species code | Dmel |
| `FB_genotype` | FlyBase notation | w[*]; P{Gr21a-GAL80.1756}attP2 |
| `description` | Original genotype | w[*]; P{y[+t7.7]... |
| `stock_number` | Center's stock # | 80563 |

### Key Classes

#### FlyBaseDataLoader (`data_loader.py`)

```python
class FlyBaseDataLoader:
    """Handles downloading, caching, and parsing FlyBase data."""

    def __init__(self, data_dir: Path, cache_max_age: timedelta):
        ...

    async def download_stocks_file(self, force: bool = False) -> Path:
        """Download TSV from FlyBase if cache is stale."""

    def parse_stocks_tsv(self, path: Path) -> Iterator[dict]:
        """Stream-parse gzipped TSV file."""

    def filter_bdsc_stocks(self, stocks: Iterator) -> Iterator:
        """Filter to only Bloomington stocks."""

    def build_stock_index(self, stocks: Iterator) -> dict[str, dict]:
        """Build stock_number -> data mapping."""

    async def load_bdsc_stocks(self, force_refresh: bool = False) -> dict:
        """Main entry point: load and index all BDSC stocks."""
```

#### BDSCPlugin (`client.py`)

```python
class BDSCPlugin(StockPlugin):
    """BDSC integration using FlyBase bulk data."""

    name = "Bloomington Drosophila Stock Center"
    source_id = "bdsc"

    async def search(self, query: str, limit: int = 20) -> list[StockImportData]:
        """Search by stock number (prefix) or genotype (substring)."""

    async def get_details(self, external_id: str) -> Optional[StockImportData]:
        """Get full details for a stock by number."""

    async def refresh_data(self) -> int:
        """Force refresh from FlyBase."""

    async def get_stats(self) -> dict:
        """Return plugin statistics."""
```

---

## Creating a New Plugin

### Step 1: Create Plugin Directory

```bash
mkdir -p app/plugins/vdrc
touch app/plugins/vdrc/__init__.py
touch app/plugins/vdrc/client.py
```

### Step 2: Implement the Plugin Class

```python
# app/plugins/vdrc/client.py
from typing import Optional
from app.plugins.base import StockPlugin, StockImportData

class VDRCPlugin(StockPlugin):
    """Vienna Drosophila Resource Center plugin."""

    name = "Vienna Drosophila Resource Center"
    source_id = "vdrc"

    async def search(self, query: str, limit: int = 20) -> list[StockImportData]:
        """Search VDRC stocks.

        Args:
            query: Search query (stock number or genotype).
            limit: Maximum results to return.

        Returns:
            List of matching stocks.
        """
        # Your implementation here
        results = []
        # ... search logic ...
        return results

    async def get_details(self, external_id: str) -> Optional[StockImportData]:
        """Get stock details by VDRC ID.

        Args:
            external_id: VDRC stock identifier.

        Returns:
            Stock data or None if not found.
        """
        # Your implementation here
        return None

    async def validate_connection(self) -> bool:
        """Check if VDRC data source is available."""
        return True
```

### Step 3: Export the Plugin

```python
# app/plugins/vdrc/__init__.py
from app.plugins.vdrc.client import VDRCPlugin

__all__ = ["VDRCPlugin"]
```

### Step 4: Register in Router

Edit `app/plugins/router.py`:

```python
from app.plugins.vdrc.client import VDRCPlugin

# Add to get_plugin function
def get_plugin(source: str):
    if source == "bdsc":
        return get_bdsc_plugin()
    if source == "vdrc":
        return VDRCPlugin()  # Or use a singleton
    raise HTTPException(status_code=404, detail=f"Unknown source: {source}")

# Add to list_sources endpoint
@router.get("/sources")
async def list_sources():
    return [
        PluginSourceInfo(source_id="bdsc", name="BDSC", ...),
        PluginSourceInfo(source_id="vdrc", name="VDRC", ...),
    ]
```

### Step 5: Add Tests

```python
# tests/test_plugins/test_vdrc_client.py
import pytest
from app.plugins.vdrc.client import VDRCPlugin

@pytest.fixture
def vdrc_plugin():
    return VDRCPlugin()

class TestVDRCPlugin:
    @pytest.mark.asyncio
    async def test_search_returns_results(self, vdrc_plugin):
        results = await vdrc_plugin.search("GD12345")
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_get_details_existing(self, vdrc_plugin):
        result = await vdrc_plugin.get_details("12345")
        # Assert expected structure
```

---

## API Reference

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/plugins/sources` | List available plugins |
| `GET` | `/api/plugins/sources/{source}/stats` | Plugin statistics |
| `POST` | `/api/plugins/sources/{source}/refresh` | Force data refresh |
| `GET` | `/api/plugins/search` | Search external source |
| `GET` | `/api/plugins/details/{source}/{id}` | Get stock details |
| `POST` | `/api/plugins/import` | Import stocks |

### Request/Response Schemas

#### PluginSourceInfo
```python
class PluginSourceInfo(BaseModel):
    source_id: str      # e.g., "bdsc"
    name: str           # e.g., "Bloomington Drosophila Stock Center"
    description: str    # Human-readable description
    available: bool     # Whether the source is operational
```

#### ExternalStockResult
```python
class ExternalStockResult(BaseModel):
    external_id: str    # ID in external system
    genotype: str       # Genotype string
    source: str         # Source identifier
    metadata: dict      # Additional data (flybase_id, urls, etc.)
```

#### ImportFromExternalRequest
```python
class ImportFromExternalRequest(BaseModel):
    stocks: list[ExternalStockImportItem]

class ExternalStockImportItem(BaseModel):
    external_id: str            # Required
    source: str                 # Required (e.g., "bdsc")
    stock_id: Optional[str]     # Custom ID, defaults to "BDSC-{external_id}"
    location: Optional[str]     # Where to store the stock
    notes: Optional[str]        # Additional notes
```

#### ImportFromExternalResult
```python
class ImportFromExternalResult(BaseModel):
    imported: int           # Successfully imported count
    skipped: int            # Skipped (duplicates) count
    errors: list[str]       # Error messages
    imported_ids: list[str] # UUIDs of imported stocks
```

### Example API Calls

```bash
# List sources
curl http://localhost:8000/api/plugins/sources

# Search BDSC
curl "http://localhost:8000/api/plugins/search?query=80563&source=bdsc&limit=10"

# Get details
curl http://localhost:8000/api/plugins/details/bdsc/80563

# Import stocks (requires auth)
curl -X POST http://localhost:8000/api/plugins/import \
  -H "Content-Type: application/json" \
  -H "Cookie: access_token=..." \
  -d '{
    "stocks": [
      {"external_id": "80563", "source": "bdsc"},
      {"external_id": "80564", "source": "bdsc", "location": "Rack A"}
    ]
  }'
```

---

## Data Flow

### Search Flow

```
User Input ("80563")
       │
       ▼
┌──────────────────┐
│  /api/plugins/   │
│     search       │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  get_plugin()    │─── Returns BDSCPlugin instance
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  plugin.search() │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ _ensure_loaded() │─── Downloads data if needed
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  Index lookup    │─── O(1) for exact match
│  + genotype scan │─── O(n) for substring
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  StockImportData │─── Formatted results
└──────────────────┘
```

### Import Flow

```
Selected Stocks [{external_id, source}, ...]
         │
         ▼
┌──────────────────┐
│  /api/plugins/   │
│     import       │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ For each stock:  │
│ 1. get_details() │
│ 2. Check dupe    │
│ 3. Create Stock  │
│ 4. Create ExtRef │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  Commit to DB    │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ ImportResult     │
│ {imported, skip} │
└──────────────────┘
```

---

## Testing Plugins

### Unit Test Structure

```python
# tests/test_plugins/test_bdsc_client.py

# Fixtures with mock data (no network calls)
SAMPLE_STOCK_INDEX = {
    "80563": {
        "external_id": "80563",
        "flybase_id": "FBst0080563",
        "genotype": "w[*]; P{Gr21a-GAL80.1756}attP2",
        ...
    }
}

@pytest.fixture
def bdsc_plugin(tmp_path):
    plugin = BDSCPlugin(data_dir=tmp_path)
    plugin._stocks_index = SAMPLE_STOCK_INDEX.copy()
    plugin._loaded = True
    return plugin

class TestSearch:
    @pytest.mark.asyncio
    async def test_exact_match(self, bdsc_plugin):
        results = await bdsc_plugin.search("80563")
        assert len(results) == 1
        assert results[0].external_id == "80563"
```

### Integration Tests

For full integration tests, use a test database and mock HTTP responses:

```python
@pytest.fixture
def mock_flybase_response(httpx_mock):
    # Create mock gzipped TSV
    tsv_content = "FBst\tcollection_short_name\t...\nFBst0080563\tBloomington\t..."
    compressed = gzip.compress(tsv_content.encode())
    httpx_mock.add_response(url=re.compile(r".*flybase.*"), content=compressed)
```

### Running Tests

```bash
# Run plugin tests only
pytest tests/test_plugins/ -v

# With coverage
pytest tests/test_plugins/ --cov=app/plugins --cov-report=html
```

---

## Deployment Considerations

### Data Directory

The BDSC plugin stores cached data in `data/flybase/`. Ensure this directory:
- Is writable by the application
- Is persisted across container restarts (use a Docker volume)
- Has sufficient space (~10MB for cached data)

```yaml
# docker-compose.yml
volumes:
  - ./data:/app/data  # Persist plugin data
```

### Memory Usage

The BDSC plugin loads ~90,000 stocks into memory (~50-100MB). For memory-constrained environments:
- Consider lazy loading on first search
- Implement pagination for very large result sets
- Use SQLite cache instead of in-memory dict

### Refresh Strategy

Data is refreshed when:
- Cache file doesn't exist (first run)
- Cache is older than 30 days (configurable)
- Manual refresh via API endpoint

For production, consider:
- Background refresh job (don't block user requests)
- Webhook/cron to refresh monthly
- Health check endpoint to verify data freshness

### Error Handling

The plugin handles common errors gracefully:

| Error | Handling |
|-------|----------|
| Network failure during download | Retry with backoff, fall back to stale cache |
| Malformed TSV row | Log and skip, continue processing |
| Stock not found | Return None, let router return 404 |
| Download timeout | Configurable timeout (default 60s) |

---

## Future Enhancements

Potential improvements for the plugin system:

1. **More stock centers**: VDRC, Kyoto, NIG-Fly, Harvard TRiP
2. **Background data refresh**: Celery task for periodic updates
3. **Incremental updates**: Only fetch changed records
4. **Search improvements**: Fuzzy matching, relevance scoring
5. **Batch import progress**: WebSocket updates for large imports
6. **Plugin registry**: Auto-discover plugins at startup
