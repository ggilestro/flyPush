"""Imports module for CSV/Excel import."""

from app.imports.router import router
from app.imports.parsers import (
    parse_csv,
    parse_excel,
    validate_import_data,
    normalize_repository,
    infer_origin,
    parse_tags,
    REPOSITORY_ALIASES,
)
from app.imports.schemas import (
    ImportPreview,
    ImportStats,
    ImportConfig,
    ImportExecuteRequest,
    ImportExecuteResult,
    ConflictType,
    RowConflict,
    ConflictingRow,
    ConflictResolution,
    ImportPhase1Result,
    ImportPhase2Request,
)
from app.imports.conflict_detectors import (
    DetectionContext,
    ConflictDetector,
    RuleBasedDetector,
    CompositeDetector,
    get_conflict_detector,
)

__all__ = [
    "router",
    "parse_csv",
    "parse_excel",
    "validate_import_data",
    "normalize_repository",
    "infer_origin",
    "parse_tags",
    "REPOSITORY_ALIASES",
    "ImportPreview",
    "ImportStats",
    "ImportConfig",
    "ImportExecuteRequest",
    "ImportExecuteResult",
    # Conflict detection
    "ConflictType",
    "RowConflict",
    "ConflictingRow",
    "ConflictResolution",
    "ImportPhase1Result",
    "ImportPhase2Request",
    "DetectionContext",
    "ConflictDetector",
    "RuleBasedDetector",
    "CompositeDetector",
    "get_conflict_detector",
]
