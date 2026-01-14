"""Tests for the storage module - TinyDB wrapper for runs, repos, and progress.

This module tests the Storage class and Pydantic models:
- Run, RepoRecord, Progress models
- Storage CRUD operations
- Atomic checkpoint saves
- Retention policy

Tests are organized as:
1. Executable Documentation (above the fold) - DAMP style
2. Coverage tests - comprehensive parametrized tests
"""

from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from conv_commit_stats.storage import (
    CommitTypeCounts,
    ExportData,
    Methodology,
    Progress,
    RepoRecord,
    Run,
    RunStatus,
    SearchCursor,
    Storage,
)


# =============================================================================
# EXECUTABLE DOCUMENTATION - Read these first to understand the API
# =============================================================================


class TestStorageBasics:
    """Basic examples showing how Storage works."""

    def test_create_and_retrieve_run(self, tmp_db_path: Path) -> None:
        """Create a new run and retrieve it by ID."""
        with Storage(tmp_db_path) as storage:
            # Create a new run
            run = Run(
                run_id="run_2026-01-12T04:00:00Z",
                started_at=datetime(2026, 1, 12, 4, 0, 0, tzinfo=UTC),
                status=RunStatus.RUNNING,
            )
            storage.save_run(run)

            # Retrieve it
            retrieved = storage.get_run("run_2026-01-12T04:00:00Z")
            assert retrieved is not None
            assert retrieved.run_id == "run_2026-01-12T04:00:00Z"
            assert retrieved.status == RunStatus.RUNNING

    def test_save_repo_record(self, tmp_db_path: Path) -> None:
        """Save a repository record with commit type counts."""
        with Storage(tmp_db_path) as storage:
            # First create a run
            run = Run(
                run_id="run_2026-01-12T04:00:00Z",
                started_at=datetime(2026, 1, 12, 4, 0, 0, tzinfo=UTC),
                status=RunStatus.RUNNING,
            )
            storage.save_run(run)

            # Save a repo record
            record = RepoRecord(
                run_id="run_2026-01-12T04:00:00Z",
                repo="facebook/react",
                default_branch="main",
                head_commit="abc123def",
                stars=220000,
                language="JavaScript",
                created_at=datetime(2013, 5, 24, 16, 15, 54, tzinfo=UTC),
                license="MIT",
                timestamp=datetime(2026, 1, 12, 4, 2, 15, tzinfo=UTC),
                commits_analyzed=100,
                feat=25,
                fix=18,
                docs=15,
                chore=8,
                ci=5,
                build=12,
                test=4,
                refactor=7,
                style=2,
                perf=3,
                revert=1,
            )
            storage.save_repo_record(record)

            # Retrieve repos for the run
            repos = storage.get_repos_for_run("run_2026-01-12T04:00:00Z")
            assert len(repos) == 1
            assert repos[0].repo == "facebook/react"
            assert repos[0].feat == 25

    def test_progress_checkpoint(self, tmp_db_path: Path) -> None:
        """Save and restore progress for resume capability."""
        with Storage(tmp_db_path) as storage:
            # Save progress
            storage.save_progress("run_id", "run_2026-01-12T04:00:00Z")
            storage.save_progress("last_repo", "facebook/react")

            # Restore progress
            run_id = storage.get_progress("run_id")
            last_repo = storage.get_progress("last_repo")

            assert run_id == "run_2026-01-12T04:00:00Z"
            assert last_repo == "facebook/react"


class TestPydanticModels:
    """Basic examples of Pydantic model validation."""

    def test_run_id_format_validation(self) -> None:
        """Run IDs must follow the pattern run_YYYY-MM-DDTHH:MM:SSZ."""
        # Valid run ID
        run = Run(
            run_id="run_2026-01-12T04:00:00Z",
            started_at=datetime(2026, 1, 12, 4, 0, 0, tzinfo=UTC),
            status=RunStatus.RUNNING,
        )
        assert run.run_id == "run_2026-01-12T04:00:00Z"

        # Invalid run ID raises ValidationError
        with pytest.raises(ValidationError):
            Run(
                run_id="invalid-run-id",
                started_at=datetime(2026, 1, 12, 4, 0, 0, tzinfo=UTC),
                status=RunStatus.RUNNING,
            )

    def test_repo_name_format_validation(self) -> None:
        """Repository names must be in owner/repo format."""
        record = RepoRecord(
            run_id="run_2026-01-12T04:00:00Z",
            repo="facebook/react",
            default_branch="main",
            head_commit="abc123def",
            stars=100,
            created_at=datetime(2013, 5, 24, tzinfo=UTC),
            timestamp=datetime(2026, 1, 12, tzinfo=UTC),
            commits_analyzed=0,
        )
        assert record.repo == "facebook/react"

        # Invalid repo name raises ValidationError
        with pytest.raises(ValidationError):
            RepoRecord(
                run_id="run_2026-01-12T04:00:00Z",
                repo="invalid-repo-name",  # Missing owner/
                default_branch="main",
                head_commit="abc123def",
                stars=100,
                created_at=datetime(2013, 5, 24, tzinfo=UTC),
                timestamp=datetime(2026, 1, 12, tzinfo=UTC),
                commits_analyzed=0,
            )


# =============================================================================
# COMPREHENSIVE MODEL TESTS
# =============================================================================


class TestRunModel:
    """Test Run model validation and constraints."""

    def test_run_with_all_fields(self) -> None:
        """Run with all fields populated."""
        run = Run(
            run_id="run_2026-01-12T04:00:00Z",
            started_at=datetime(2026, 1, 12, 4, 0, 0, tzinfo=UTC),
            completed_at=datetime(2026, 1, 12, 5, 15, 0, tzinfo=UTC),
            status=RunStatus.COMPLETED,
            repos_processed=1000,
            repos_qualified=847,
            total_commits_analyzed=84700,
        )
        assert run.repos_processed == 1000
        assert run.total_commits_analyzed == 84700

    def test_run_default_values(self) -> None:
        """Run with default values for optional fields."""
        run = Run(
            run_id="run_2026-01-12T04:00:00Z",
            started_at=datetime(2026, 1, 12, 4, 0, 0, tzinfo=UTC),
            status=RunStatus.RUNNING,
        )
        assert run.completed_at is None
        assert run.repos_processed == 0
        assert run.repos_qualified == 0
        assert run.total_commits_analyzed == 0

    @pytest.mark.parametrize(
        "status",
        [RunStatus.RUNNING, RunStatus.COMPLETED, RunStatus.FAILED],
    )
    def test_all_run_statuses(self, status: RunStatus) -> None:
        """All run statuses should be valid."""
        run = Run(
            run_id="run_2026-01-12T04:00:00Z",
            started_at=datetime(2026, 1, 12, 4, 0, 0, tzinfo=UTC),
            status=status,
        )
        assert run.status == status

    def test_negative_counts_rejected(self) -> None:
        """Negative counts should be rejected."""
        with pytest.raises(ValidationError):
            Run(
                run_id="run_2026-01-12T04:00:00Z",
                started_at=datetime(2026, 1, 12, 4, 0, 0, tzinfo=UTC),
                status=RunStatus.RUNNING,
                repos_processed=-1,
            )


class TestRepoRecordModel:
    """Test RepoRecord model validation and constraints."""

    def test_commit_counts_default_to_zero(self) -> None:
        """All commit type counts should default to zero."""
        record = RepoRecord(
            run_id="run_2026-01-12T04:00:00Z",
            repo="owner/repo",
            default_branch="main",
            head_commit="abc123def",
            stars=100,
            created_at=datetime(2013, 5, 24, tzinfo=UTC),
            timestamp=datetime(2026, 1, 12, tzinfo=UTC),
            commits_analyzed=0,
        )
        assert record.feat == 0
        assert record.fix == 0
        assert record.docs == 0
        assert record.build == 0
        assert record.chore == 0
        assert record.ci == 0
        assert record.perf == 0
        assert record.refactor == 0
        assert record.revert == 0
        assert record.style == 0
        assert record.test == 0

    def test_minimum_stars_validation(self) -> None:
        """Stars must be at least 3 (filter threshold)."""
        # Valid: exactly 3 stars
        record = RepoRecord(
            run_id="run_2026-01-12T04:00:00Z",
            repo="owner/repo",
            default_branch="main",
            head_commit="abc123def",
            stars=3,
            created_at=datetime(2013, 5, 24, tzinfo=UTC),
            timestamp=datetime(2026, 1, 12, tzinfo=UTC),
            commits_analyzed=0,
        )
        assert record.stars == 3

        # Invalid: less than 3 stars
        with pytest.raises(ValidationError):
            RepoRecord(
                run_id="run_2026-01-12T04:00:00Z",
                repo="owner/repo",
                default_branch="main",
                head_commit="abc123def",
                stars=2,
                created_at=datetime(2013, 5, 24, tzinfo=UTC),
                timestamp=datetime(2026, 1, 12, tzinfo=UTC),
                commits_analyzed=0,
            )

    def test_head_commit_sha_length(self) -> None:
        """Head commit SHA must be between 7 and 40 characters."""
        # Valid: 7 characters
        record = RepoRecord(
            run_id="run_2026-01-12T04:00:00Z",
            repo="owner/repo",
            default_branch="main",
            head_commit="abc1234",
            stars=100,
            created_at=datetime(2013, 5, 24, tzinfo=UTC),
            timestamp=datetime(2026, 1, 12, tzinfo=UTC),
            commits_analyzed=0,
        )
        assert len(record.head_commit) == 7

        # Invalid: too short
        with pytest.raises(ValidationError):
            RepoRecord(
                run_id="run_2026-01-12T04:00:00Z",
                repo="owner/repo",
                default_branch="main",
                head_commit="abc",
                stars=100,
                created_at=datetime(2013, 5, 24, tzinfo=UTC),
                timestamp=datetime(2026, 1, 12, tzinfo=UTC),
                commits_analyzed=0,
            )


class TestProgressModel:
    """Test Progress model for checkpointing."""

    def test_simple_string_progress(self) -> None:
        """Progress with a simple string value."""
        progress = Progress(
            key="last_repo",
            value="facebook/react",
            updated_at=datetime(2026, 1, 12, 4, 45, 0, tzinfo=UTC),
        )
        assert progress.key == "last_repo"
        assert progress.value == "facebook/react"

    def test_search_cursor_progress(self) -> None:
        """Progress with a SearchCursor value."""
        cursor = SearchCursor(stars_range="500..1000", page=3)
        progress = Progress(
            key="search_cursor",
            value=cursor,
            updated_at=datetime(2026, 1, 12, 4, 15, 0, tzinfo=UTC),
        )
        assert progress.key == "search_cursor"
        assert isinstance(progress.value, SearchCursor)
        assert progress.value.page == 3


class TestExportDataModel:
    """Test ExportData model for visualization JSON."""

    def test_complete_export_data(self) -> None:
        """ExportData with all required fields."""
        export = ExportData(
            run_id="run_2026-01-12T04:00:00Z",
            generated_at=datetime(2026, 1, 12, 5, 20, 0, tzinfo=UTC),
            total_repos=847,
            total_commits=84700,
            counts=CommitTypeCounts(
                feat=25000,
                fix=20000,
                docs=12000,
                chore=10000,
                refactor=8000,
                test=5000,
                ci=2000,
                build=1500,
                style=800,
                perf=300,
                revert=100,
            ),
            methodology=Methodology(
                min_stars=3,
                max_commits_per_repo=100,
                time_window_days=365,
                excluded=[
                    "merge commits",
                    "bot authors",
                    "non-conventional messages",
                ],
            ),
        )
        assert export.total_repos == 847
        assert export.counts.feat == 25000
        assert export.methodology.min_stars == 3


# =============================================================================
# STORAGE OPERATIONS TESTS
# =============================================================================


class TestStorageOperations:
    """Test Storage class CRUD operations."""

    def test_list_all_runs(self, tmp_db_path: Path) -> None:
        """List all runs in storage."""
        with Storage(tmp_db_path) as storage:
            # Create multiple runs
            for i in range(3):
                run = Run(
                    run_id=f"run_2026-01-{10 + i:02d}T04:00:00Z",
                    started_at=datetime(2026, 1, 10 + i, 4, 0, 0, tzinfo=UTC),
                    status=RunStatus.COMPLETED,
                )
                storage.save_run(run)

            runs = storage.list_runs()
            assert len(runs) == 3

    def test_update_run_status(self, tmp_db_path: Path) -> None:
        """Update a run's status."""
        with Storage(tmp_db_path) as storage:
            # Create a running run
            run = Run(
                run_id="run_2026-01-12T04:00:00Z",
                started_at=datetime(2026, 1, 12, 4, 0, 0, tzinfo=UTC),
                status=RunStatus.RUNNING,
            )
            storage.save_run(run)

            # Update to completed
            run.status = RunStatus.COMPLETED
            run.completed_at = datetime(2026, 1, 12, 5, 15, 0, tzinfo=UTC)
            run.repos_processed = 1000
            run.repos_qualified = 847
            storage.save_run(run)

            # Verify update
            updated = storage.get_run("run_2026-01-12T04:00:00Z")
            assert updated is not None
            assert updated.status == RunStatus.COMPLETED
            assert updated.repos_processed == 1000

    def test_delete_run_and_repos(self, tmp_db_path: Path) -> None:
        """Delete a run and its associated repo records."""
        with Storage(tmp_db_path) as storage:
            # Create a run with repos
            run = Run(
                run_id="run_2026-01-12T04:00:00Z",
                started_at=datetime(2026, 1, 12, 4, 0, 0, tzinfo=UTC),
                status=RunStatus.COMPLETED,
            )
            storage.save_run(run)

            record = RepoRecord(
                run_id="run_2026-01-12T04:00:00Z",
                repo="owner/repo",
                default_branch="main",
                head_commit="abc123def",
                stars=100,
                created_at=datetime(2013, 5, 24, tzinfo=UTC),
                timestamp=datetime(2026, 1, 12, tzinfo=UTC),
                commits_analyzed=10,
            )
            storage.save_repo_record(record)

            # Delete run
            storage.delete_run("run_2026-01-12T04:00:00Z")

            # Verify deletion
            assert storage.get_run("run_2026-01-12T04:00:00Z") is None
            assert len(storage.get_repos_for_run("run_2026-01-12T04:00:00Z")) == 0

    def test_get_nonexistent_run(self, tmp_db_path: Path) -> None:
        """Getting a nonexistent run returns None."""
        with Storage(tmp_db_path) as storage:
            assert storage.get_run("nonexistent-run") is None

    def test_get_nonexistent_progress(self, tmp_db_path: Path) -> None:
        """Getting nonexistent progress returns None."""
        with Storage(tmp_db_path) as storage:
            assert storage.get_progress("nonexistent-key") is None

    def test_clear_progress(self, tmp_db_path: Path) -> None:
        """Clear all progress data."""
        with Storage(tmp_db_path) as storage:
            storage.save_progress("run_id", "run_2026-01-12T04:00:00Z")
            storage.save_progress("last_repo", "owner/repo")

            storage.clear_progress()

            assert storage.get_progress("run_id") is None
            assert storage.get_progress("last_repo") is None


class TestStorageRetention:
    """Test retention policy enforcement."""

    def test_get_latest_completed_run(self, tmp_db_path: Path) -> None:
        """Get the most recent completed run."""
        with Storage(tmp_db_path) as storage:
            # Create multiple runs
            for i in range(3):
                run = Run(
                    run_id=f"run_2026-01-{10 + i:02d}T04:00:00Z",
                    started_at=datetime(2026, 1, 10 + i, 4, 0, 0, tzinfo=UTC),
                    status=RunStatus.COMPLETED,
                )
                storage.save_run(run)

            latest = storage.get_latest_completed_run()
            assert latest is not None
            assert latest.run_id == "run_2026-01-12T04:00:00Z"

    def test_get_latest_completed_run_ignores_running(
        self, tmp_db_path: Path
    ) -> None:
        """Latest completed run should ignore running runs."""
        with Storage(tmp_db_path) as storage:
            # Create a completed run
            completed = Run(
                run_id="run_2026-01-10T04:00:00Z",
                started_at=datetime(2026, 1, 10, 4, 0, 0, tzinfo=UTC),
                status=RunStatus.COMPLETED,
            )
            storage.save_run(completed)

            # Create a running run (more recent)
            running = Run(
                run_id="run_2026-01-12T04:00:00Z",
                started_at=datetime(2026, 1, 12, 4, 0, 0, tzinfo=UTC),
                status=RunStatus.RUNNING,
            )
            storage.save_run(running)

            latest = storage.get_latest_completed_run()
            assert latest is not None
            assert latest.run_id == "run_2026-01-10T04:00:00Z"

    def test_prune_old_runs(self, tmp_db_path: Path) -> None:
        """Prune runs beyond retention limit."""
        with Storage(tmp_db_path) as storage:
            # Create 5 completed runs
            for i in range(5):
                run = Run(
                    run_id=f"run_2026-01-{10 + i:02d}T04:00:00Z",
                    started_at=datetime(2026, 1, 10 + i, 4, 0, 0, tzinfo=UTC),
                    status=RunStatus.COMPLETED,
                )
                storage.save_run(run)

                # Add a repo record to each run
                record = RepoRecord(
                    run_id=f"run_2026-01-{10 + i:02d}T04:00:00Z",
                    repo=f"owner/repo{i}",
                    default_branch="main",
                    head_commit="abc123def",
                    stars=100,
                    created_at=datetime(2013, 5, 24, tzinfo=UTC),
                    timestamp=datetime(2026, 1, 10 + i, tzinfo=UTC),
                    commits_analyzed=10,
                )
                storage.save_repo_record(record)

            # Prune to keep only 3
            pruned = storage.prune_old_runs(keep=3)
            assert pruned == 2

            # Verify only 3 runs remain (most recent)
            runs = storage.list_runs()
            assert len(runs) == 3
            assert all(
                r.run_id
                in [
                    "run_2026-01-12T04:00:00Z",
                    "run_2026-01-13T04:00:00Z",
                    "run_2026-01-14T04:00:00Z",
                ]
                for r in runs
            )


class TestStorageAtomicity:
    """Test atomic operations and data integrity."""

    def test_save_checkpoint_is_atomic(self, tmp_db_path: Path) -> None:
        """Checkpoint saves should be atomic."""
        with Storage(tmp_db_path) as storage:
            # Create a run
            run = Run(
                run_id="run_2026-01-12T04:00:00Z",
                started_at=datetime(2026, 1, 12, 4, 0, 0, tzinfo=UTC),
                status=RunStatus.RUNNING,
            )
            storage.save_run(run)

            # Save a checkpoint (run + repo + progress atomically)
            record = RepoRecord(
                run_id="run_2026-01-12T04:00:00Z",
                repo="owner/repo",
                default_branch="main",
                head_commit="abc123def",
                stars=100,
                created_at=datetime(2013, 5, 24, tzinfo=UTC),
                timestamp=datetime(2026, 1, 12, tzinfo=UTC),
                commits_analyzed=10,
            )

            storage.save_checkpoint(
                run=run,
                record=record,
                last_repo="owner/repo",
            )

            # Verify all data saved
            assert storage.get_run("run_2026-01-12T04:00:00Z") is not None
            assert (
                len(storage.get_repos_for_run("run_2026-01-12T04:00:00Z")) == 1
            )
            assert storage.get_progress("last_repo") == "owner/repo"


class TestStoragePersistence:
    """Test that data persists across Storage instances."""

    def test_data_persists_after_close(self, tmp_db_path: Path) -> None:
        """Data should persist after closing and reopening storage."""
        # First instance: create data
        with Storage(tmp_db_path) as storage1:
            run = Run(
                run_id="run_2026-01-12T04:00:00Z",
                started_at=datetime(2026, 1, 12, 4, 0, 0, tzinfo=UTC),
                status=RunStatus.COMPLETED,
            )
            storage1.save_run(run)

        # Second instance: verify data
        with Storage(tmp_db_path) as storage2:
            retrieved = storage2.get_run("run_2026-01-12T04:00:00Z")
            assert retrieved is not None
            assert retrieved.status == RunStatus.COMPLETED

    def test_creates_directory_if_missing(self, tmp_path: Path) -> None:
        """Storage should create the data directory if it doesn't exist."""
        db_path = tmp_path / "nested" / "data" / "dir"
        with Storage(db_path) as storage:
            # Should not raise, should create the directory
            run = Run(
                run_id="run_2026-01-12T04:00:00Z",
                started_at=datetime(2026, 1, 12, 4, 0, 0, tzinfo=UTC),
                status=RunStatus.RUNNING,
            )
            storage.save_run(run)

            assert db_path.exists()
