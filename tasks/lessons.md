# Lessons Learned

## 2026-02-02: BDSC Plugin Implementation

### Circular Import Prevention
- **Issue**: Importing `app.dependencies` at module level caused circular imports due to the dependency chain: `router.py` -> `dependencies.py` -> `auth/utils.py` -> `auth/router.py` -> `dependencies.py`
- **Solution**: Use late imports inside functions (like `_get_db()` and `_get_current_user()`) instead of importing at module level
- **Pattern**: For routers that need database and auth dependencies, define local dependency functions with late imports

### FlyBase Data Integration
- **Finding**: BDSC doesn't have a public API, but FlyBase provides bulk TSV files containing all stock center data
- **Data source**: `https://s3ftp.flybase.org/releases/current/precomputed_files/stocks/stocks_FB*.tsv.gz`
- **Key fields**: `FBst` (FlyBase ID), `stock_number`, `collection_short_name` (to filter BDSC), `FB_genotype`, `description`
- **Approach**: Download once, cache locally, filter to BDSC stocks, build in-memory index for fast search

### Testing Plugin Code
- **Pattern**: For async plugin code, pre-populate the data index in fixtures to avoid network calls
- **Pattern**: Use `MagicMock` and `AsyncMock` for testing router endpoints that depend on plugins
- **Pattern**: Test endpoint validation separately from business logic

## 2026-02-04: FlyBase Multi-Repository Support

### Plugin Refactoring Strategy
- **Approach**: When expanding a single-source plugin to multi-source, keep backward compatibility aliases
- **Pattern**: `BDSCPlugin = FlyBasePlugin` and `get_bdsc_plugin = get_flybase_plugin` allow existing code to work unchanged
- **Pattern**: Use source aliases in router (e.g., 'bdsc' -> 'flybase' with repository='bdsc') for backward compat

### Multi-Repository Index Structure
- **Design**: Two-level index structure: `{repository: {stock_number: data}}`
- **Benefit**: Allows both repository-specific and cross-repository searches efficiently
- **Pattern**: Transform records to include repository info during parsing, not at query time

### FlyBase Collection Mapping
- **Finding**: FlyBase `collection_short_name` maps to repository IDs:
  - `Bloomington` → `bdsc`
  - `Vienna` → `vdrc`
  - `Kyoto` → `kyoto`
  - `NIG-Fly` → `nig`
  - `KDRC` → `kdrc`
  - `FlyORF` → `flyorf`
  - `NDSSC` → `ndssc`
- **Pattern**: Define mappings as module-level constants for reuse across modules

### API Design for Multi-Repository
- **Pattern**: Use optional `repository` query param rather than separate endpoints per repo
- **Pattern**: Return repository info in stats endpoint to populate UI filters
- **Pattern**: Add `/repositories` endpoint for explicit listing of available repositories
