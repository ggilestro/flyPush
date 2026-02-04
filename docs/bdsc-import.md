# BDSC Import Quick Reference

Import stocks from the Bloomington Drosophila Stock Center directly into your database.

## Quick Start

1. Go to **Import from BDSC** in the sidebar
2. Enter a stock number (e.g., `80563`) or genotype text (e.g., `GAL4`)
3. Select stocks from the results
4. Click **Import Selected**

## Search Tips

| Search Type | Example | What It Finds |
|-------------|---------|---------------|
| Stock number | `80563` | Exact match for BDSC stock #80563 |
| Number prefix | `8056` | All stocks starting with 8056 |
| Genotype text | `GAL4` | Stocks with "GAL4" in genotype |
| Gene name | `prospero` | Stocks mentioning "prospero" |

## What Gets Imported

| Field | Example Value |
|-------|---------------|
| Stock ID | `BDSC-80563` |
| Genotype | `w[*]; P{Gr21a-GAL80.1756}attP2` |
| Source | `BDSC (80563)` |

## Metadata Stored

Each imported stock includes links to external resources:
- **FlyBase URL**: `https://flybase.org/reports/FBst0080563`
- **BDSC URL**: `https://bdsc.indiana.edu/Home/Search?presearch=80563`
- **FlyBase ID**: `FBst0080563`
- **Data Version**: FlyBase release (e.g., `FB2025_05`)

## Data Source

Stock data comes from [FlyBase](https://flybase.org/) bulk data files, which are:
- Downloaded automatically on first search
- Cached locally for fast subsequent searches
- Updated monthly with new FlyBase releases

## Current Statistics

Check data status via the API:
```bash
curl http://localhost:8000/api/plugins/sources/bdsc/stats
```

Returns:
```json
{
  "total_stocks": 91288,
  "data_version": "FB2025_05",
  "cache_valid": true
}
```

## Troubleshooting

### "No stocks found"
- Check spelling of stock number
- Try broader search terms
- Genotype search is case-insensitive

### "Stock already exists"
- A stock with ID `BDSC-{number}` is already in your database
- Find and update the existing stock, or use a custom Stock ID

### Slow first search
- First search downloads ~3MB of data from FlyBase
- Subsequent searches are instant (data is cached)

## API Examples

```bash
# Search
curl "http://localhost:8000/api/plugins/search?query=80563&source=bdsc"

# Get details
curl "http://localhost:8000/api/plugins/details/bdsc/80563"

# Import (requires authentication)
curl -X POST http://localhost:8000/api/plugins/import \
  -H "Content-Type: application/json" \
  -H "Cookie: access_token=YOUR_TOKEN" \
  -d '{"stocks": [{"external_id": "80563", "source": "bdsc"}]}'
```

## Related Links

- [BDSC Website](https://bdsc.indiana.edu/)
- [FlyBase Stock Reports](https://flybase.org/reports/)
- [User Guide](user-guide.md#importing-stocks-from-bdsc)
- [Developer Guide](plugins-dev-guide.md)
