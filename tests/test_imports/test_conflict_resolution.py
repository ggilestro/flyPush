"""Tests for import conflict resolution system.

Covers:
- RuleBasedDetector unit tests (coalesce, genotype mismatch, duplicate, missing required, repo match)
- CompositeDetector aggregation and detect_all
- Session storage (create, get, tenant isolation, expiry, cleanup)
- Phase 1 endpoint integration (clean import, conflicts, mixed, summary, session)
- Phase 2 endpoint integration (use_value, skip, manual, flags, validation, cleanup)
- End-to-end flow (phase 1 -> resolve -> phase 2)
- Edge cases (empty file, invalid JSON, expired session, partial success)
- Repository match detection
"""

import io
import json
from datetime import datetime, timedelta

import pytest

from app.db.models import Stock, StockOrigin
from app.imports.conflict_detectors import (
    CompositeDetector,
    DetectionContext,
    RepositoryMatch,
    RuleBasedDetector,
    get_conflict_detector,
)
from app.imports.schemas import (
    ConflictingRow,
    ConflictResolution,
    ConflictType,
    ImportConfig,
    ImportPhase1Result,
    ImportPhase2Request,
    RowConflict,
)

# ====================================================================
# Category 1: RuleBasedDetector unit tests
# ====================================================================


class TestRuleBasedDetectorCoalesce:
    """Tests for coalesce conflict detection."""

    @pytest.mark.asyncio
    async def test_coalesce_conflict_detected(self):
        """Detect coalesce conflict when multiple columns have values."""
        detector = RuleBasedDetector()
        context = DetectionContext()

        row = {
            "repository_stock_id": "12345",
            "_coalesce_conflicts": [
                {
                    "field": "repository_stock_id",
                    "columns": {"BDSC": "12345", "VDRC": "v98765"},
                }
            ],
        }

        conflicts = await detector.detect(row, 1, context)

        assert len(conflicts) == 1
        assert conflicts[0].conflict_type == ConflictType.COALESCE_CONFLICT
        assert conflicts[0].field == "repository_stock_id"
        assert conflicts[0].values == {"BDSC": "12345", "VDRC": "v98765"}
        assert conflicts[0].detector == "rule"

    @pytest.mark.asyncio
    async def test_no_coalesce_conflict_single_value(self):
        """No conflict when only one column has a value."""
        detector = RuleBasedDetector()
        context = DetectionContext()

        row = {
            "repository_stock_id": "12345",
            "genotype": "w1118",
        }

        conflicts = await detector.detect(row, 1, context)

        # No coalesce conflict (no _coalesce_conflicts key)
        coalesce = [c for c in conflicts if c.conflict_type == ConflictType.COALESCE_CONFLICT]
        assert len(coalesce) == 0

    @pytest.mark.asyncio
    async def test_coalesce_conflict_multiple_fields(self):
        """Multiple coalesce conflicts for different fields."""
        detector = RuleBasedDetector()
        context = DetectionContext()

        row = {
            "repository_stock_id": "12345",
            "genotype": "w1118",
            "_coalesce_conflicts": [
                {
                    "field": "repository_stock_id",
                    "columns": {"BDSC": "12345", "VDRC": "v98765"},
                },
                {
                    "field": "genotype",
                    "columns": {"Geno1": "w1118", "Geno2": "yw"},
                },
            ],
        }

        conflicts = await detector.detect(row, 1, context)

        coalesce = [c for c in conflicts if c.conflict_type == ConflictType.COALESCE_CONFLICT]
        assert len(coalesce) == 2
        fields = {c.field for c in coalesce}
        assert fields == {"repository_stock_id", "genotype"}

    @pytest.mark.asyncio
    async def test_coalesce_conflict_empty_list(self):
        """No conflict when _coalesce_conflicts is empty list."""
        detector = RuleBasedDetector()
        context = DetectionContext()

        row = {
            "genotype": "w1118",
            "_coalesce_conflicts": [],
        }

        conflicts = await detector.detect(row, 1, context)

        coalesce = [c for c in conflicts if c.conflict_type == ConflictType.COALESCE_CONFLICT]
        assert len(coalesce) == 0


class TestRuleBasedDetectorGenotypeMismatch:
    """Tests for genotype mismatch detection."""

    @pytest.mark.asyncio
    async def test_genotype_mismatch_detected(self):
        """Detect mismatch between local and remote genotype."""
        detector = RuleBasedDetector()
        context = DetectionContext(
            remote_metadata={"3605": {"genotype": "w[1118]; P{da-GAL4.w[-]}3"}}
        )

        row = {
            "repository_stock_id": "3605",
            "genotype": "w[1118]; P{GAL4-da.G32}UH1",
        }

        conflicts = await detector.detect(row, 1, context)

        mismatch = [c for c in conflicts if c.conflict_type == ConflictType.GENOTYPE_MISMATCH]
        assert len(mismatch) == 1
        assert mismatch[0].field == "genotype"
        assert mismatch[0].remote_value == "w[1118]; P{da-GAL4.w[-]}3"
        assert mismatch[0].values == {"local": "w[1118]; P{GAL4-da.G32}UH1"}

    @pytest.mark.asyncio
    async def test_genotype_mismatch_case_insensitive(self):
        """No mismatch when genotypes differ only in case."""
        detector = RuleBasedDetector()
        context = DetectionContext(remote_metadata={"3605": {"genotype": "w[1118]"}})

        row = {
            "repository_stock_id": "3605",
            "genotype": "W[1118]",
        }

        conflicts = await detector.detect(row, 1, context)

        mismatch = [c for c in conflicts if c.conflict_type == ConflictType.GENOTYPE_MISMATCH]
        assert len(mismatch) == 0

    @pytest.mark.asyncio
    async def test_genotype_mismatch_whitespace_normalized(self):
        """No mismatch when genotypes differ only in whitespace."""
        detector = RuleBasedDetector()
        context = DetectionContext(remote_metadata={"3605": {"genotype": "w[1118];  P{GAL4}"}})

        row = {
            "repository_stock_id": "3605",
            "genotype": "w[1118]; P{GAL4}",
        }

        conflicts = await detector.detect(row, 1, context)

        mismatch = [c for c in conflicts if c.conflict_type == ConflictType.GENOTYPE_MISMATCH]
        assert len(mismatch) == 0

    @pytest.mark.asyncio
    async def test_genotype_mismatch_no_remote_data(self):
        """No mismatch when remote metadata is not available."""
        detector = RuleBasedDetector()
        context = DetectionContext(remote_metadata={})

        row = {
            "repository_stock_id": "3605",
            "genotype": "w[1118]",
        }

        conflicts = await detector.detect(row, 1, context)

        mismatch = [c for c in conflicts if c.conflict_type == ConflictType.GENOTYPE_MISMATCH]
        assert len(mismatch) == 0

    @pytest.mark.asyncio
    async def test_genotype_mismatch_no_local_genotype(self):
        """No mismatch when local genotype is empty."""
        detector = RuleBasedDetector()
        context = DetectionContext(remote_metadata={"3605": {"genotype": "w[1118]"}})

        row = {
            "repository_stock_id": "3605",
        }

        conflicts = await detector.detect(row, 1, context)

        mismatch = [c for c in conflicts if c.conflict_type == ConflictType.GENOTYPE_MISMATCH]
        assert len(mismatch) == 0

    @pytest.mark.asyncio
    async def test_genotype_mismatch_remote_has_fb_genotype(self):
        """Detect mismatch using FB_genotype fallback field."""
        detector = RuleBasedDetector()
        context = DetectionContext(remote_metadata={"3605": {"FB_genotype": "w[1118]; P{da-GAL4}"}})

        row = {
            "repository_stock_id": "3605",
            "genotype": "completely different",
        }

        conflicts = await detector.detect(row, 1, context)

        mismatch = [c for c in conflicts if c.conflict_type == ConflictType.GENOTYPE_MISMATCH]
        assert len(mismatch) == 1
        assert mismatch[0].remote_value == "w[1118]; P{da-GAL4}"


class TestRuleBasedDetectorDuplicateStock:
    """Tests for duplicate stock detection."""

    @pytest.mark.asyncio
    async def test_duplicate_stock_detected(self):
        """Detect duplicate when stock_id exists in database."""
        detector = RuleBasedDetector()
        context = DetectionContext(existing_stock_ids={"LAB-001", "LAB-002"})

        row = {"stock_id": "LAB-001", "genotype": "w1118"}

        conflicts = await detector.detect(row, 1, context)

        dup = [c for c in conflicts if c.conflict_type == ConflictType.DUPLICATE_STOCK]
        assert len(dup) == 1
        assert dup[0].field == "stock_id"
        assert dup[0].values == {"stock_id": "LAB-001"}

    @pytest.mark.asyncio
    async def test_no_duplicate_for_new_stock(self):
        """No duplicate when stock_id doesn't exist."""
        detector = RuleBasedDetector()
        context = DetectionContext(existing_stock_ids={"LAB-001"})

        row = {"stock_id": "LAB-999", "genotype": "w1118"}

        conflicts = await detector.detect(row, 1, context)

        dup = [c for c in conflicts if c.conflict_type == ConflictType.DUPLICATE_STOCK]
        assert len(dup) == 0

    @pytest.mark.asyncio
    async def test_no_duplicate_when_no_stock_id(self):
        """No duplicate check when stock_id is missing."""
        detector = RuleBasedDetector()
        context = DetectionContext(existing_stock_ids={"LAB-001"})

        row = {"genotype": "w1118"}

        conflicts = await detector.detect(row, 1, context)

        dup = [c for c in conflicts if c.conflict_type == ConflictType.DUPLICATE_STOCK]
        assert len(dup) == 0


class TestRuleBasedDetectorMissingRequired:
    """Tests for missing required field detection."""

    @pytest.mark.asyncio
    async def test_missing_both_genotype_and_repo_id(self):
        """Detect missing required when both genotype and repo_id absent."""
        detector = RuleBasedDetector()
        context = DetectionContext()

        row = {"stock_id": "LAB-001", "notes": "some notes"}

        conflicts = await detector.detect(row, 1, context)

        missing = [c for c in conflicts if c.conflict_type == ConflictType.MISSING_REQUIRED]
        assert len(missing) == 1
        assert "genotype" in missing[0].field

    @pytest.mark.asyncio
    async def test_has_genotype_only(self):
        """No missing required when genotype is present."""
        detector = RuleBasedDetector()
        context = DetectionContext()

        row = {"genotype": "w1118"}

        conflicts = await detector.detect(row, 1, context)

        missing = [c for c in conflicts if c.conflict_type == ConflictType.MISSING_REQUIRED]
        assert len(missing) == 0

    @pytest.mark.asyncio
    async def test_has_repo_id_only(self):
        """No missing required when repository_stock_id is present."""
        detector = RuleBasedDetector()
        context = DetectionContext()

        row = {"repository_stock_id": "3605"}

        conflicts = await detector.detect(row, 1, context)

        missing = [c for c in conflicts if c.conflict_type == ConflictType.MISSING_REQUIRED]
        assert len(missing) == 0


class TestRuleBasedDetectorRepositoryMatch:
    """Tests for repository match detection."""

    @pytest.mark.asyncio
    async def test_repository_match_detected(self):
        """Detect potential match for internal stock matching a repository genotype."""
        detector = RuleBasedDetector()
        match = RepositoryMatch(repository="bdsc", stock_id="3605", genotype="w[1118]")
        context = DetectionContext(repository_matches={1: [match]})

        row = {"genotype": "w[1118]", "origin": "internal"}

        conflicts = await detector.detect(row, 1, context)

        repo_match = [
            c for c in conflicts if c.conflict_type == ConflictType.POTENTIAL_REPOSITORY_MATCH
        ]
        assert len(repo_match) == 1
        assert repo_match[0].field == "origin"
        assert repo_match[0].values["repository"] == "BDSC"
        assert repo_match[0].values["repository_stock_id"] == "3605"

    @pytest.mark.asyncio
    async def test_repository_match_skipped_for_repo_stock(self):
        """No match detection for stocks already marked as repository."""
        detector = RuleBasedDetector()
        match = RepositoryMatch(repository="bdsc", stock_id="3605", genotype="w[1118]")
        context = DetectionContext(repository_matches={1: [match]})

        row = {"genotype": "w[1118]", "origin": "repository"}

        conflicts = await detector.detect(row, 1, context)

        repo_match = [
            c for c in conflicts if c.conflict_type == ConflictType.POTENTIAL_REPOSITORY_MATCH
        ]
        assert len(repo_match) == 0

    @pytest.mark.asyncio
    async def test_repository_match_skipped_when_has_repo_id(self):
        """No match detection for stocks with existing repository_stock_id."""
        detector = RuleBasedDetector()
        match = RepositoryMatch(repository="bdsc", stock_id="3605", genotype="w[1118]")
        context = DetectionContext(repository_matches={1: [match]})

        row = {"genotype": "w[1118]", "repository_stock_id": "9999"}

        conflicts = await detector.detect(row, 1, context)

        repo_match = [
            c for c in conflicts if c.conflict_type == ConflictType.POTENTIAL_REPOSITORY_MATCH
        ]
        assert len(repo_match) == 0

    @pytest.mark.asyncio
    async def test_no_repository_match_when_empty(self):
        """No conflict when repository search returns no matches."""
        detector = RuleBasedDetector()
        context = DetectionContext(repository_matches={})

        row = {"genotype": "w[1118]", "origin": "internal"}

        conflicts = await detector.detect(row, 1, context)

        repo_match = [
            c for c in conflicts if c.conflict_type == ConflictType.POTENTIAL_REPOSITORY_MATCH
        ]
        assert len(repo_match) == 0

    @pytest.mark.asyncio
    async def test_repository_match_uses_best_match(self):
        """When multiple matches, use the first (best) one."""
        detector = RuleBasedDetector()
        match1 = RepositoryMatch(repository="bdsc", stock_id="3605", genotype="w[1118]; P{exact}")
        match2 = RepositoryMatch(repository="vdrc", stock_id="v100", genotype="w[1118]; P{close}")
        context = DetectionContext(repository_matches={1: [match1, match2]})

        row = {"genotype": "w[1118]; P{exact}", "origin": "internal"}

        conflicts = await detector.detect(row, 1, context)

        repo_match = [
            c for c in conflicts if c.conflict_type == ConflictType.POTENTIAL_REPOSITORY_MATCH
        ]
        assert len(repo_match) == 1
        assert repo_match[0].values["repository"] == "BDSC"
        assert repo_match[0].values["repository_stock_id"] == "3605"


# ====================================================================
# Category 2: CompositeDetector tests
# ====================================================================


class TestCompositeDetector:
    """Tests for CompositeDetector aggregation."""

    @pytest.mark.asyncio
    async def test_aggregates_from_all_detectors(self):
        """Composite detector combines results from all registered detectors."""
        detector = get_conflict_detector()
        context = DetectionContext(existing_stock_ids={"DUPE-001"})

        # Row with both duplicate and missing required
        row = {"stock_id": "DUPE-001"}

        conflicts = await detector.detect(row, 1, context)

        types = {c.conflict_type for c in conflicts}
        assert ConflictType.DUPLICATE_STOCK in types
        assert ConflictType.MISSING_REQUIRED in types

    @pytest.mark.asyncio
    async def test_detect_all_filters_clean_rows(self):
        """detect_all only returns rows that have conflicts."""
        detector = get_conflict_detector()
        context = DetectionContext()

        rows = [
            {"genotype": "w1118"},  # Clean
            {"stock_id": "TEST", "notes": "no genotype or repo"},  # Missing required
            {"genotype": "yw"},  # Clean
        ]

        result = await detector.detect_all(rows, context)

        assert len(result) == 1
        assert result[0].row_index == 2
        assert result[0].conflicts[0].conflict_type == ConflictType.MISSING_REQUIRED

    @pytest.mark.asyncio
    async def test_detect_all_preserves_original_row(self):
        """detect_all stores original_row from _original_row key."""
        detector = get_conflict_detector()
        context = DetectionContext()

        original = {"Stock ID": "T1", "Notes": "raw data"}
        rows = [
            {"stock_id": "T1", "_original_row": original},
        ]

        result = await detector.detect_all(rows, context)

        assert len(result) == 1
        assert result[0].original_row == original

    @pytest.mark.asyncio
    async def test_detect_all_groups_conflicts_per_row(self):
        """Each ConflictingRow groups all conflicts for that row."""
        detector = get_conflict_detector()
        context = DetectionContext(existing_stock_ids={"DUPE-001"})

        rows = [
            {
                "stock_id": "DUPE-001",
                # Missing genotype AND duplicate
            },
        ]

        result = await detector.detect_all(rows, context)

        assert len(result) == 1
        assert len(result[0].conflicts) >= 2


# ====================================================================
# Category 3: Session storage tests
# ====================================================================


class TestSessionStorage:
    """Tests for in-memory import session storage."""

    def setup_method(self):
        """Clean up sessions before each test."""
        from app.imports.router import _import_sessions

        _import_sessions.clear()

    def test_create_returns_uuid(self):
        """Creating a session returns a UUID string."""
        from app.imports.router import _create_import_session

        config = ImportConfig()
        session_id = _create_import_session("tenant-1", [], config, [])

        assert session_id
        assert len(session_id) == 36  # UUID format

    def test_get_with_correct_tenant(self):
        """Session is returned for matching tenant."""
        from app.imports.router import _create_import_session, _get_import_session

        config = ImportConfig()
        session_id = _create_import_session(
            "tenant-1",
            [{"row_index": 1, "data": "test"}],
            config,
            [{"column_name": "col1"}],
        )

        session = _get_import_session(session_id, "tenant-1")

        assert session is not None
        assert session["tenant_id"] == "tenant-1"
        assert len(session["conflicting_rows"]) == 1

    def test_get_with_wrong_tenant_returns_none(self):
        """Session is NOT returned for different tenant (security)."""
        from app.imports.router import _create_import_session, _get_import_session

        config = ImportConfig()
        session_id = _create_import_session("tenant-1", [], config, [])

        session = _get_import_session(session_id, "tenant-2")

        assert session is None

    def test_expired_session_auto_deleted(self):
        """Expired sessions are cleaned up on access."""
        from app.imports.router import (
            _create_import_session,
            _get_import_session,
            _import_sessions,
        )

        config = ImportConfig()
        session_id = _create_import_session("tenant-1", [], config, [])

        # Manually expire it
        _import_sessions[session_id]["expires_at"] = datetime.utcnow() - timedelta(minutes=1)

        session = _get_import_session(session_id, "tenant-1")

        assert session is None
        assert session_id not in _import_sessions

    def test_cleanup_removes_all_expired(self):
        """Cleanup removes all expired sessions."""
        from app.imports.router import (
            _cleanup_expired_sessions,
            _create_import_session,
            _import_sessions,
        )

        config = ImportConfig()
        s1 = _create_import_session("t1", [], config, [])
        s2 = _create_import_session("t2", [], config, [])
        s3 = _create_import_session("t3", [], config, [])

        # Expire first two
        past = datetime.utcnow() - timedelta(minutes=5)
        _import_sessions[s1]["expires_at"] = past
        _import_sessions[s2]["expires_at"] = past

        _cleanup_expired_sessions()

        assert s1 not in _import_sessions
        assert s2 not in _import_sessions
        assert s3 in _import_sessions

    def test_delete_session(self):
        """Session can be explicitly deleted."""
        from app.imports.router import (
            _create_import_session,
            _delete_import_session,
            _get_import_session,
        )

        config = ImportConfig()
        session_id = _create_import_session("tenant-1", [], config, [])

        _delete_import_session(session_id)

        session = _get_import_session(session_id, "tenant-1")
        assert session is None


# ====================================================================
# Category 4: Phase 1 endpoint integration tests
# ====================================================================


class TestPhase1Endpoint:
    """Integration tests for /execute-v2-phase1."""

    def _make_csv(self, content: str) -> io.BytesIO:
        """Create a CSV file-like object."""
        return io.BytesIO(content.encode("utf-8"))

    def _post_phase1(self, client, csv_content, mappings_data):
        """Helper to POST to phase1 endpoint."""
        csv_file = self._make_csv(csv_content)
        return client.post(
            "/api/imports/execute-v2-phase1",
            files={"file": ("test.csv", csv_file, "text/csv")},
            data={"mappings_json": json.dumps(mappings_data)},
        )

    def test_all_clean_rows_imported(self, authenticated_client, test_tenant, test_user, db):
        """All clean rows are imported in phase 1, no conflicts."""
        csv_content = "stock_id,genotype\nLAB-001,w1118\nLAB-002,yw"
        mappings = {
            "column_mappings": [
                {"column_name": "stock_id", "target_field": "stock_id"},
                {"column_name": "genotype", "target_field": "genotype"},
            ],
            "config": {"fetch_metadata": False, "auto_create_trays": False},
        }

        response = self._post_phase1(authenticated_client, csv_content, mappings)

        assert response.status_code == 200
        data = response.json()
        assert data["imported_count"] == 2
        assert "LAB-001" in data["imported_stock_ids"]
        assert "LAB-002" in data["imported_stock_ids"]
        assert len(data["conflicting_rows"]) == 0
        assert data["session_id"] == ""

    def test_all_conflicting_rows_returned(self, authenticated_client, test_tenant, test_user, db):
        """When all rows conflict, none imported, all returned."""
        # Pre-create stocks so they're duplicates
        db.add(
            Stock(
                tenant_id=test_tenant.id,
                stock_id="DUPE-001",
                genotype="w1118",
                origin=StockOrigin.INTERNAL,
                created_by_id=test_user.id,
                modified_by_id=test_user.id,
            )
        )
        db.add(
            Stock(
                tenant_id=test_tenant.id,
                stock_id="DUPE-002",
                genotype="yw",
                origin=StockOrigin.INTERNAL,
                created_by_id=test_user.id,
                modified_by_id=test_user.id,
            )
        )
        db.commit()

        csv_content = "stock_id,genotype\nDUPE-001,w1118\nDUPE-002,yw"
        mappings = {
            "column_mappings": [
                {"column_name": "stock_id", "target_field": "stock_id"},
                {"column_name": "genotype", "target_field": "genotype"},
            ],
            "config": {"fetch_metadata": False},
        }

        response = self._post_phase1(authenticated_client, csv_content, mappings)

        assert response.status_code == 200
        data = response.json()
        assert data["imported_count"] == 0
        assert len(data["conflicting_rows"]) == 2
        assert data["session_id"] != ""

    def test_mixed_clean_and_conflicting(self, authenticated_client, test_tenant, test_user, db):
        """Clean rows imported, conflicting rows returned for review."""
        db.add(
            Stock(
                tenant_id=test_tenant.id,
                stock_id="DUPE-001",
                genotype="w1118",
                origin=StockOrigin.INTERNAL,
                created_by_id=test_user.id,
                modified_by_id=test_user.id,
            )
        )
        db.commit()

        csv_content = "stock_id,genotype\nDUPE-001,w1118\nNEW-001,yw"
        mappings = {
            "column_mappings": [
                {"column_name": "stock_id", "target_field": "stock_id"},
                {"column_name": "genotype", "target_field": "genotype"},
            ],
            "config": {"fetch_metadata": False},
        }

        response = self._post_phase1(authenticated_client, csv_content, mappings)

        assert response.status_code == 200
        data = response.json()
        assert data["imported_count"] == 1
        assert "NEW-001" in data["imported_stock_ids"]
        assert len(data["conflicting_rows"]) == 1
        assert data["conflicting_rows"][0]["conflicts"][0]["conflict_type"] == "duplicate_stock"

    def test_conflict_summary_counts(self, authenticated_client, test_tenant, test_user, db):
        """Conflict summary shows correct counts by type."""
        db.add(
            Stock(
                tenant_id=test_tenant.id,
                stock_id="DUPE-001",
                genotype="w1118",
                origin=StockOrigin.INTERNAL,
                created_by_id=test_user.id,
                modified_by_id=test_user.id,
            )
        )
        db.commit()

        csv_content = "stock_id,genotype\nDUPE-001,w1118\nNO-ID,"
        mappings = {
            "column_mappings": [
                {"column_name": "stock_id", "target_field": "stock_id"},
                {"column_name": "genotype", "target_field": "genotype"},
            ],
            "config": {"fetch_metadata": False},
        }

        response = self._post_phase1(authenticated_client, csv_content, mappings)

        data = response.json()
        summary = data["conflict_summary"]
        assert summary.get("duplicate_stock", 0) == 1
        assert summary.get("missing_required", 0) == 1

    def test_session_stored_for_conflicts(self, authenticated_client, test_tenant, test_user, db):
        """Phase 1 creates a session with conflicting data."""
        from app.imports.router import _get_import_session

        db.add(
            Stock(
                tenant_id=test_tenant.id,
                stock_id="DUPE-001",
                genotype="w1118",
                origin=StockOrigin.INTERNAL,
                created_by_id=test_user.id,
                modified_by_id=test_user.id,
            )
        )
        db.commit()

        csv_content = "stock_id,genotype\nDUPE-001,w1118"
        mappings = {
            "column_mappings": [
                {"column_name": "stock_id", "target_field": "stock_id"},
                {"column_name": "genotype", "target_field": "genotype"},
            ],
            "config": {"fetch_metadata": False},
        }

        response = self._post_phase1(authenticated_client, csv_content, mappings)

        data = response.json()
        session_id = data["session_id"]
        assert session_id

        session = _get_import_session(session_id, test_tenant.id)
        assert session is not None
        assert len(session["conflicting_rows"]) == 1

    def test_empty_file_rejected(self, authenticated_client, test_tenant, test_user, db):
        """Empty file (headers only) is rejected."""
        csv_content = "stock_id,genotype\n"
        mappings = {
            "column_mappings": [
                {"column_name": "stock_id", "target_field": "stock_id"},
                {"column_name": "genotype", "target_field": "genotype"},
            ],
            "config": {"fetch_metadata": False},
        }

        response = self._post_phase1(authenticated_client, csv_content, mappings)

        assert response.status_code == 400
        assert "No data rows" in response.json()["detail"]

    def test_invalid_json_rejected(self, authenticated_client, test_tenant, test_user, db):
        """Invalid JSON in mappings is rejected."""
        csv_file = io.BytesIO(b"stock_id,genotype\nLAB-001,w1118")
        response = authenticated_client.post(
            "/api/imports/execute-v2-phase1",
            files={"file": ("test.csv", csv_file, "text/csv")},
            data={"mappings_json": "not valid json {{{"},
        )

        assert response.status_code == 400
        assert "Invalid JSON" in response.json()["detail"]

    def test_coalesce_conflict_in_phase1(self, authenticated_client, test_tenant, test_user, db):
        """Coalesce conflicts are detected when both columns have values."""
        csv_content = "BDSC,VDRC,genotype\n12345,v98765,w1118"
        mappings = {
            "column_mappings": [
                {"column_name": "BDSC", "target_field": "repository_stock_id"},
                {"column_name": "VDRC", "target_field": "repository_stock_id"},
                {"column_name": "genotype", "target_field": "genotype"},
            ],
            "config": {"fetch_metadata": False},
        }

        response = self._post_phase1(authenticated_client, csv_content, mappings)

        assert response.status_code == 200
        data = response.json()
        assert len(data["conflicting_rows"]) == 1
        conflict_types = [c["conflict_type"] for c in data["conflicting_rows"][0]["conflicts"]]
        assert "coalesce_conflict" in conflict_types


# ====================================================================
# Category 5: Phase 2 endpoint integration tests
# ====================================================================


class TestPhase2Endpoint:
    """Integration tests for /execute-v2-phase2."""

    def setup_method(self):
        """Clean up sessions before each test."""
        from app.imports.router import _import_sessions

        _import_sessions.clear()

    def _create_session(self, tenant_id, rows, config=None, mappings=None):
        """Helper to create a test session."""
        from app.imports.router import _create_import_session

        if config is None:
            config = ImportConfig()
        if mappings is None:
            mappings = []
        return _create_import_session(tenant_id, rows, config, mappings)

    def _post_phase2(self, client, request_data):
        """Helper to POST to phase2 endpoint."""
        return client.post(
            "/api/imports/execute-v2-phase2",
            data={"request_json": json.dumps(request_data)},
        )

    def test_use_value_resolution(self, authenticated_client, test_tenant, test_user, db):
        """Resolve conflict by choosing a specific value."""
        conflicting_rows = [
            {
                "row_index": 1,
                "original_row": {"BDSC": "12345", "VDRC": "v98765"},
                "transformed_row": {
                    "repository_stock_id": "12345",
                    "genotype": "w1118",
                    "stock_id": "IMP-0001",
                },
                "conflicts": [
                    {
                        "conflict_type": "coalesce_conflict",
                        "field": "repository_stock_id",
                        "values": {"BDSC": "12345", "VDRC": "v98765"},
                        "message": "Multiple values",
                        "detector": "rule",
                    }
                ],
            }
        ]

        session_id = self._create_session(test_tenant.id, conflicting_rows)

        request_data = {
            "session_id": session_id,
            "resolutions": [
                {
                    "row_index": 1,
                    "action": "use_value",
                    "field_values": {"repository_stock_id": "v98765"},
                }
            ],
        }

        response = self._post_phase2(authenticated_client, request_data)

        assert response.status_code == 200
        data = response.json()
        assert data["imported_count"] == 1

        # Verify the stock was created with the resolved value
        stock = (
            db.query(Stock)
            .filter(
                Stock.tenant_id == test_tenant.id,
                Stock.stock_id == "IMP-0001",
            )
            .first()
        )
        assert stock is not None

    def test_skip_resolution(self, authenticated_client, test_tenant, test_user, db):
        """Skipped rows are not imported."""
        conflicting_rows = [
            {
                "row_index": 1,
                "original_row": {},
                "transformed_row": {
                    "genotype": "w1118",
                    "stock_id": "IMP-0001",
                },
                "conflicts": [
                    {
                        "conflict_type": "duplicate_stock",
                        "field": "stock_id",
                        "values": {"stock_id": "IMP-0001"},
                        "message": "Duplicate",
                        "detector": "rule",
                    }
                ],
            }
        ]

        session_id = self._create_session(test_tenant.id, conflicting_rows)

        request_data = {
            "session_id": session_id,
            "resolutions": [
                {
                    "row_index": 1,
                    "action": "skip",
                    "field_values": {},
                }
            ],
        }

        response = self._post_phase2(authenticated_client, request_data)

        assert response.status_code == 200
        data = response.json()
        assert data["imported_count"] == 0
        assert "skipped 1" in data["message"]

    def test_manual_resolution(self, authenticated_client, test_tenant, test_user, db):
        """Manual resolution applies user-provided field values."""
        conflicting_rows = [
            {
                "row_index": 1,
                "original_row": {},
                "transformed_row": {
                    "genotype": "old genotype",
                    "stock_id": "MANUAL-001",
                },
                "conflicts": [
                    {
                        "conflict_type": "genotype_mismatch",
                        "field": "genotype",
                        "values": {"local": "old genotype"},
                        "message": "Mismatch",
                        "remote_value": "remote genotype",
                        "detector": "rule",
                    }
                ],
            }
        ]

        session_id = self._create_session(test_tenant.id, conflicting_rows)

        request_data = {
            "session_id": session_id,
            "resolutions": [
                {
                    "row_index": 1,
                    "action": "manual",
                    "field_values": {"genotype": "manually edited genotype"},
                }
            ],
        }

        response = self._post_phase2(authenticated_client, request_data)

        assert response.status_code == 200
        data = response.json()
        assert data["imported_count"] == 1

        stock = db.query(Stock).filter(Stock.stock_id == "MANUAL-001").first()
        assert stock is not None
        assert stock.genotype == "manually edited genotype"

    def test_flag_note_appended(self, authenticated_client, test_tenant, test_user, db):
        """_flag_note is appended to stock notes."""
        conflicting_rows = [
            {
                "row_index": 1,
                "original_row": {},
                "transformed_row": {
                    "genotype": "w1118",
                    "stock_id": "FLAG-001",
                    "notes": "existing notes",
                },
                "conflicts": [
                    {
                        "conflict_type": "genotype_mismatch",
                        "field": "genotype",
                        "values": {},
                        "message": "Mismatch",
                        "detector": "rule",
                    }
                ],
            }
        ]

        session_id = self._create_session(test_tenant.id, conflicting_rows)

        request_data = {
            "session_id": session_id,
            "resolutions": [
                {
                    "row_index": 1,
                    "action": "use_value",
                    "field_values": {
                        "genotype": "w1118",
                        "_flag_note": "REVIEW: genotype differs from repository",
                    },
                }
            ],
        }

        response = self._post_phase2(authenticated_client, request_data)

        assert response.status_code == 200
        stock = db.query(Stock).filter(Stock.stock_id == "FLAG-001").first()
        assert stock is not None
        assert "existing notes" in stock.notes
        assert "REVIEW: genotype differs from repository" in stock.notes

    def test_flag_note_on_empty_notes(self, authenticated_client, test_tenant, test_user, db):
        """_flag_note works when existing notes are empty."""
        conflicting_rows = [
            {
                "row_index": 1,
                "original_row": {},
                "transformed_row": {
                    "genotype": "w1118",
                    "stock_id": "FLAG-002",
                },
                "conflicts": [
                    {
                        "conflict_type": "genotype_mismatch",
                        "field": "genotype",
                        "values": {},
                        "message": "Mismatch",
                        "detector": "rule",
                    }
                ],
            }
        ]

        session_id = self._create_session(test_tenant.id, conflicting_rows)

        request_data = {
            "session_id": session_id,
            "resolutions": [
                {
                    "row_index": 1,
                    "action": "use_value",
                    "field_values": {
                        "genotype": "w1118",
                        "_flag_note": "REVIEW: needs verification",
                    },
                }
            ],
        }

        response = self._post_phase2(authenticated_client, request_data)

        assert response.status_code == 200
        stock = db.query(Stock).filter(Stock.stock_id == "FLAG-002").first()
        assert stock.notes == "REVIEW: needs verification"

    def test_flag_tag_added(self, authenticated_client, test_tenant, test_user, db):
        """_flag_tag is added as a tag to the stock."""
        conflicting_rows = [
            {
                "row_index": 1,
                "original_row": {},
                "transformed_row": {
                    "genotype": "w1118",
                    "stock_id": "TAGG-001",
                },
                "conflicts": [
                    {
                        "conflict_type": "genotype_mismatch",
                        "field": "genotype",
                        "values": {},
                        "message": "Mismatch",
                        "detector": "rule",
                    }
                ],
            }
        ]

        session_id = self._create_session(test_tenant.id, conflicting_rows)

        request_data = {
            "session_id": session_id,
            "resolutions": [
                {
                    "row_index": 1,
                    "action": "use_value",
                    "field_values": {
                        "genotype": "w1118",
                        "_flag_tag": "needs-review",
                    },
                }
            ],
        }

        response = self._post_phase2(authenticated_client, request_data)

        assert response.status_code == 200
        stock = db.query(Stock).filter(Stock.stock_id == "TAGG-001").first()
        assert stock is not None
        tag_names = [t.name for t in stock.tags]
        assert "needs-review" in tag_names

    def test_session_not_found_404(self, authenticated_client, test_tenant, test_user, db):
        """Return 404 when session doesn't exist."""
        request_data = {
            "session_id": "nonexistent-session-id",
            "resolutions": [],
        }

        response = self._post_phase2(authenticated_client, request_data)

        assert response.status_code == 404
        assert "not found or expired" in response.json()["detail"]

    def test_session_cleaned_up_after_phase2(
        self, authenticated_client, test_tenant, test_user, db
    ):
        """Session is deleted after phase 2 completes."""
        from app.imports.router import _get_import_session

        conflicting_rows = [
            {
                "row_index": 1,
                "original_row": {},
                "transformed_row": {
                    "genotype": "w1118",
                    "stock_id": "CLEAN-001",
                },
                "conflicts": [
                    {
                        "conflict_type": "missing_required",
                        "field": "genotype",
                        "values": {},
                        "message": "Missing",
                        "detector": "rule",
                    }
                ],
            }
        ]

        session_id = self._create_session(test_tenant.id, conflicting_rows)

        request_data = {
            "session_id": session_id,
            "resolutions": [
                {"row_index": 1, "action": "use_value", "field_values": {"genotype": "w1118"}},
            ],
        }

        self._post_phase2(authenticated_client, request_data)

        session = _get_import_session(session_id, test_tenant.id)
        assert session is None

    def test_preserves_original_genotype_in_metadata(
        self, authenticated_client, test_tenant, test_user, db
    ):
        """_original_genotype is preserved in external_metadata."""
        conflicting_rows = [
            {
                "row_index": 1,
                "original_row": {},
                "transformed_row": {
                    "genotype": "remote genotype",
                    "stock_id": "ORIG-001",
                    "_original_genotype": "my local genotype",
                },
                "conflicts": [
                    {
                        "conflict_type": "genotype_mismatch",
                        "field": "genotype",
                        "values": {},
                        "message": "Mismatch",
                        "detector": "rule",
                    }
                ],
            }
        ]

        session_id = self._create_session(test_tenant.id, conflicting_rows)

        request_data = {
            "session_id": session_id,
            "resolutions": [
                {
                    "row_index": 1,
                    "action": "use_value",
                    "field_values": {"genotype": "remote genotype"},
                },
            ],
        }

        response = self._post_phase2(authenticated_client, request_data)

        assert response.status_code == 200
        stock = db.query(Stock).filter(Stock.stock_id == "ORIG-001").first()
        assert stock is not None
        assert stock.external_metadata is not None
        assert stock.external_metadata.get("original_genotype_from_import") == "my local genotype"

    def test_no_resolution_skips_row(self, authenticated_client, test_tenant, test_user, db):
        """Rows with no resolution provided are skipped."""
        conflicting_rows = [
            {
                "row_index": 1,
                "original_row": {},
                "transformed_row": {
                    "genotype": "w1118",
                    "stock_id": "SKIP-001",
                },
                "conflicts": [
                    {
                        "conflict_type": "duplicate_stock",
                        "field": "stock_id",
                        "values": {},
                        "message": "Duplicate",
                        "detector": "rule",
                    }
                ],
            }
        ]

        session_id = self._create_session(test_tenant.id, conflicting_rows)

        # Submit with empty resolutions list
        request_data = {
            "session_id": session_id,
            "resolutions": [],
        }

        response = self._post_phase2(authenticated_client, request_data)

        assert response.status_code == 200
        data = response.json()
        assert data["imported_count"] == 0
        assert "skipped 1" in data["message"]

    def test_invalid_json_in_phase2(self, authenticated_client, test_tenant, test_user, db):
        """Invalid JSON in phase 2 request is rejected."""
        response = authenticated_client.post(
            "/api/imports/execute-v2-phase2",
            data={"request_json": "not json {{{"},
        )

        assert response.status_code == 400
        assert "Invalid JSON" in response.json()["detail"]


# ====================================================================
# Category 6: End-to-end flow tests
# ====================================================================


class TestEndToEndFlow:
    """End-to-end tests: phase 1 → resolve → phase 2."""

    def setup_method(self):
        """Clean up sessions before each test."""
        from app.imports.router import _import_sessions

        _import_sessions.clear()

    def test_coalesce_resolve_import(self, authenticated_client, test_tenant, test_user, db):
        """Full flow: coalesce conflict detected, resolved, and imported."""
        # Phase 1: Upload file with coalesce conflict
        csv_content = "BDSC,VDRC,genotype\n12345,v98765,w1118"
        csv_file = io.BytesIO(csv_content.encode())

        mappings = {
            "column_mappings": [
                {"column_name": "BDSC", "target_field": "repository_stock_id"},
                {"column_name": "VDRC", "target_field": "repository_stock_id"},
                {"column_name": "genotype", "target_field": "genotype"},
            ],
            "config": {"fetch_metadata": False},
        }

        r1 = authenticated_client.post(
            "/api/imports/execute-v2-phase1",
            files={"file": ("test.csv", csv_file, "text/csv")},
            data={"mappings_json": json.dumps(mappings)},
        )

        assert r1.status_code == 200
        phase1 = r1.json()
        assert phase1["imported_count"] == 0
        assert len(phase1["conflicting_rows"]) == 1
        session_id = phase1["session_id"]
        assert session_id

        # Phase 2: Resolve by choosing VDRC value
        r2 = authenticated_client.post(
            "/api/imports/execute-v2-phase2",
            data={
                "request_json": json.dumps(
                    {
                        "session_id": session_id,
                        "resolutions": [
                            {
                                "row_index": 1,
                                "action": "use_value",
                                "field_values": {"repository_stock_id": "v98765"},
                            },
                        ],
                    }
                )
            },
        )

        assert r2.status_code == 200
        phase2 = r2.json()
        assert phase2["imported_count"] == 1

    def test_duplicate_resolve_with_new_id(self, authenticated_client, test_tenant, test_user, db):
        """Duplicate conflict resolved by changing stock_id."""
        db.add(
            Stock(
                tenant_id=test_tenant.id,
                stock_id="EXISTING-001",
                genotype="w1118",
                origin=StockOrigin.INTERNAL,
                created_by_id=test_user.id,
                modified_by_id=test_user.id,
            )
        )
        db.commit()

        # Phase 1
        csv_content = "stock_id,genotype\nEXISTING-001,w1118"
        csv_file = io.BytesIO(csv_content.encode())
        mappings = {
            "column_mappings": [
                {"column_name": "stock_id", "target_field": "stock_id"},
                {"column_name": "genotype", "target_field": "genotype"},
            ],
            "config": {"fetch_metadata": False},
        }

        r1 = authenticated_client.post(
            "/api/imports/execute-v2-phase1",
            files={"file": ("test.csv", csv_file, "text/csv")},
            data={"mappings_json": json.dumps(mappings)},
        )

        phase1 = r1.json()
        assert phase1["imported_count"] == 0
        session_id = phase1["session_id"]

        # Phase 2: Resolve by changing stock_id
        r2 = authenticated_client.post(
            "/api/imports/execute-v2-phase2",
            data={
                "request_json": json.dumps(
                    {
                        "session_id": session_id,
                        "resolutions": [
                            {
                                "row_index": 1,
                                "action": "use_value",
                                "field_values": {"stock_id": "RENAMED-001"},
                            },
                        ],
                    }
                )
            },
        )

        assert r2.status_code == 200
        assert r2.json()["imported_count"] == 1

        stock = db.query(Stock).filter(Stock.stock_id == "RENAMED-001").first()
        assert stock is not None
        assert stock.genotype == "w1118"

    def test_mixed_resolutions_across_types(self, authenticated_client, test_tenant, test_user, db):
        """Multiple conflict types with different resolutions."""
        db.add(
            Stock(
                tenant_id=test_tenant.id,
                stock_id="DUPE-001",
                genotype="w1118",
                origin=StockOrigin.INTERNAL,
                created_by_id=test_user.id,
                modified_by_id=test_user.id,
            )
        )
        db.commit()

        # Row 1: duplicate, Row 2: missing genotype, Row 3: clean
        csv_content = "stock_id,genotype\nDUPE-001,w1118\nNO-GENO,\nCLEAN-001,yw"
        csv_file = io.BytesIO(csv_content.encode())
        mappings = {
            "column_mappings": [
                {"column_name": "stock_id", "target_field": "stock_id"},
                {"column_name": "genotype", "target_field": "genotype"},
            ],
            "config": {"fetch_metadata": False},
        }

        r1 = authenticated_client.post(
            "/api/imports/execute-v2-phase1",
            files={"file": ("test.csv", csv_file, "text/csv")},
            data={"mappings_json": json.dumps(mappings)},
        )

        phase1 = r1.json()
        assert phase1["imported_count"] == 1  # CLEAN-001
        assert "CLEAN-001" in phase1["imported_stock_ids"]
        assert len(phase1["conflicting_rows"]) == 2

        session_id = phase1["session_id"]

        # Phase 2: skip the duplicate, fix the missing genotype
        r2 = authenticated_client.post(
            "/api/imports/execute-v2-phase2",
            data={
                "request_json": json.dumps(
                    {
                        "session_id": session_id,
                        "resolutions": [
                            {"row_index": 1, "action": "skip", "field_values": {}},
                            {
                                "row_index": 2,
                                "action": "manual",
                                "field_values": {"genotype": "manually added genotype"},
                            },
                        ],
                    }
                )
            },
        )

        phase2 = r2.json()
        assert phase2["imported_count"] == 1
        assert "skipped 1" in phase2["message"]

        stock = db.query(Stock).filter(Stock.stock_id == "NO-GENO").first()
        assert stock is not None
        assert stock.genotype == "manually added genotype"


# ====================================================================
# Category 7: Edge cases
# ====================================================================


class TestEdgeCases:
    """Edge case tests."""

    def setup_method(self):
        """Clean up sessions before each test."""
        from app.imports.router import _import_sessions

        _import_sessions.clear()

    def test_session_expired_between_phases(self, authenticated_client, test_tenant, test_user, db):
        """Return 404 when session expires between phase 1 and phase 2."""
        from app.imports.router import _create_import_session, _import_sessions

        config = ImportConfig()
        session_id = _create_import_session(
            test_tenant.id,
            [{"row_index": 1, "transformed_row": {"genotype": "w"}, "conflicts": []}],
            config,
            [],
        )

        # Manually expire
        _import_sessions[session_id]["expires_at"] = datetime.utcnow() - timedelta(minutes=1)

        response = authenticated_client.post(
            "/api/imports/execute-v2-phase2",
            data={
                "request_json": json.dumps(
                    {
                        "session_id": session_id,
                        "resolutions": [],
                    }
                )
            },
        )

        assert response.status_code == 404

    def test_duplicate_after_resolution_reported_as_error(
        self, authenticated_client, test_tenant, test_user, db
    ):
        """If resolved stock_id still duplicates, it's reported as error."""
        db.add(
            Stock(
                tenant_id=test_tenant.id,
                stock_id="EXISTING-001",
                genotype="w1118",
                origin=StockOrigin.INTERNAL,
                created_by_id=test_user.id,
                modified_by_id=test_user.id,
            )
        )
        db.commit()

        from app.imports.router import _create_import_session

        config = ImportConfig()
        conflicting_rows = [
            {
                "row_index": 1,
                "original_row": {},
                "transformed_row": {
                    "genotype": "w1118",
                    "stock_id": "EXISTING-001",
                },
                "conflicts": [
                    {
                        "conflict_type": "coalesce_conflict",
                        "field": "genotype",
                        "values": {},
                        "message": "Test",
                        "detector": "rule",
                    }
                ],
            }
        ]
        session_id = _create_import_session(test_tenant.id, conflicting_rows, config, [])

        response = authenticated_client.post(
            "/api/imports/execute-v2-phase2",
            data={
                "request_json": json.dumps(
                    {
                        "session_id": session_id,
                        "resolutions": [
                            {
                                "row_index": 1,
                                "action": "use_value",
                                "field_values": {"genotype": "w1118"},
                            },
                        ],
                    }
                )
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["imported_count"] == 0
        assert len(data["errors"]) == 1
        assert "already exists" in data["errors"][0]["errors"][0]

    def test_partial_success_continues_after_errors(
        self, authenticated_client, test_tenant, test_user, db
    ):
        """Some rows succeed even when others fail validation."""
        db.add(
            Stock(
                tenant_id=test_tenant.id,
                stock_id="EXISTING-001",
                genotype="w1118",
                origin=StockOrigin.INTERNAL,
                created_by_id=test_user.id,
                modified_by_id=test_user.id,
            )
        )
        db.commit()

        from app.imports.router import _create_import_session

        config = ImportConfig()
        conflicting_rows = [
            {
                "row_index": 1,
                "original_row": {},
                "transformed_row": {
                    "genotype": "w1118",
                    "stock_id": "EXISTING-001",  # Will fail: duplicate
                },
                "conflicts": [
                    {
                        "conflict_type": "coalesce_conflict",
                        "field": "genotype",
                        "values": {},
                        "message": "Test",
                        "detector": "rule",
                    }
                ],
            },
            {
                "row_index": 2,
                "original_row": {},
                "transformed_row": {
                    "genotype": "yw",
                    "stock_id": "SUCCESS-001",  # Will succeed
                },
                "conflicts": [
                    {
                        "conflict_type": "coalesce_conflict",
                        "field": "genotype",
                        "values": {},
                        "message": "Test",
                        "detector": "rule",
                    }
                ],
            },
        ]
        session_id = _create_import_session(test_tenant.id, conflicting_rows, config, [])

        response = authenticated_client.post(
            "/api/imports/execute-v2-phase2",
            data={
                "request_json": json.dumps(
                    {
                        "session_id": session_id,
                        "resolutions": [
                            {
                                "row_index": 1,
                                "action": "use_value",
                                "field_values": {"genotype": "w1118"},
                            },
                            {
                                "row_index": 2,
                                "action": "use_value",
                                "field_values": {"genotype": "yw"},
                            },
                        ],
                    }
                )
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["imported_count"] == 1
        assert len(data["errors"]) == 1

    @pytest.mark.asyncio
    async def test_detector_handles_empty_row(self):
        """Detector doesn't crash on completely empty row."""
        detector = get_conflict_detector()
        context = DetectionContext()

        conflicts = await detector.detect({}, 1, context)

        # Should detect missing required at minimum
        missing = [c for c in conflicts if c.conflict_type == ConflictType.MISSING_REQUIRED]
        assert len(missing) == 1

    @pytest.mark.asyncio
    async def test_detector_handles_none_values(self):
        """Detector handles None values in row fields gracefully."""
        detector = get_conflict_detector()
        context = DetectionContext()

        row = {
            "stock_id": None,
            "genotype": None,
            "repository_stock_id": None,
        }

        conflicts = await detector.detect(row, 1, context)

        # Should detect missing required
        missing = [c for c in conflicts if c.conflict_type == ConflictType.MISSING_REQUIRED]
        assert len(missing) == 1


# ====================================================================
# Category 8: Schema tests
# ====================================================================


class TestSchemas:
    """Tests for conflict resolution Pydantic schemas."""

    def test_conflict_type_values(self):
        """All expected ConflictType enum values exist."""
        assert ConflictType.COALESCE_CONFLICT == "coalesce_conflict"
        assert ConflictType.GENOTYPE_MISMATCH == "genotype_mismatch"
        assert ConflictType.DUPLICATE_STOCK == "duplicate_stock"
        assert ConflictType.MISSING_REQUIRED == "missing_required"
        assert ConflictType.VALIDATION_ERROR == "validation_error"
        assert ConflictType.LLM_FLAGGED == "llm_flagged"
        assert ConflictType.POTENTIAL_REPOSITORY_MATCH == "potential_repository_match"

    def test_row_conflict_defaults(self):
        """RowConflict has correct default values."""
        conflict = RowConflict(
            conflict_type=ConflictType.COALESCE_CONFLICT,
            field="genotype",
            message="Test conflict",
        )
        assert conflict.detector == "rule"
        assert conflict.confidence is None
        assert conflict.suggestion is None
        assert conflict.remote_value is None
        assert conflict.values == {}

    def test_conflicting_row_structure(self):
        """ConflictingRow groups conflicts for a row."""
        row = ConflictingRow(
            row_index=5,
            original_row={"col": "val"},
            transformed_row={"genotype": "w1118"},
            conflicts=[
                RowConflict(
                    conflict_type=ConflictType.COALESCE_CONFLICT,
                    field="genotype",
                    message="Conflict 1",
                ),
                RowConflict(
                    conflict_type=ConflictType.MISSING_REQUIRED,
                    field="stock_id",
                    message="Conflict 2",
                ),
            ],
        )
        assert row.row_index == 5
        assert len(row.conflicts) == 2

    def test_conflict_resolution_schema(self):
        """ConflictResolution schema accepts valid data."""
        resolution = ConflictResolution(
            row_index=1,
            action="use_value",
            field_values={"genotype": "w1118"},
        )
        assert resolution.row_index == 1
        assert resolution.action == "use_value"

    def test_phase1_result_defaults(self):
        """ImportPhase1Result has correct defaults."""
        result = ImportPhase1Result()
        assert result.imported_count == 0
        assert result.imported_stock_ids == []
        assert result.conflicting_rows == []
        assert result.conflict_summary == {}
        assert result.session_id == ""

    def test_phase2_request_schema(self):
        """ImportPhase2Request schema accepts valid data."""
        request = ImportPhase2Request(
            session_id="test-id",
            resolutions=[
                ConflictResolution(row_index=1, action="skip"),
            ],
        )
        assert request.session_id == "test-id"
        assert len(request.resolutions) == 1

    def test_factory_returns_composite_with_rule_detector(self):
        """get_conflict_detector returns CompositeDetector with RuleBasedDetector."""
        detector = get_conflict_detector()
        assert isinstance(detector, CompositeDetector)
        assert len(detector.detectors) == 1
        assert isinstance(detector.detectors[0], RuleBasedDetector)

    def test_factory_without_llm(self):
        """get_conflict_detector(enable_llm=False) doesn't include LLM detector."""
        detector = get_conflict_detector(enable_llm=False)
        assert len(detector.detectors) == 1
