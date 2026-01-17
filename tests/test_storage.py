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

from collections.abc import Callable
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

    def test_create_and_retrieve_run(
        self, tmp_db_path: Path, run_factory: Callable[..., Run], run_id: str
    ) -> None:
        """Create a new run and retrieve it by ID."""
        with Storage(tmp_db_path) as storage:
            # Create a new run
            run = run_factory()
            storage.save_run(run)

            # Retrieve it
            retrieved = storage.get_run(run_id)
            assert retrieved is not None
            assert retrieved.run_id == run_id
            assert retrieved.status == RunStatus.RUNNING

    def test_save_repo_record(
        self,
        tmp_db_path: Path,
        run_factory: Callable[..., Run],
        repo_record_factory: Callable[..., RepoRecord],
        react_repo_name: str,
        run_id: str,
    ) -> None:
        """Save a repository record with commit type counts."""
        with Storage(tmp_db_path) as storage:
            # First create a run
            run = run_factory()
            storage.save_run(run)

            # Save a repo record
            record = repo_record_factory(
                repo=react_repo_name,
                stars=220000,
                language='JavaScript',
                license='MIT',
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
                head_commit='abc123def',
            )
            storage.save_repo_record(record)

            # Retrieve repos for the run
            repos = storage.get_repos_for_run(run_id)
            assert len(repos) == 1
            assert repos[0].repo == react_repo_name
            assert repos[0].feat == 25

    def test_progress_checkpoint(
        self, tmp_db_path: Path, run_id: str, react_repo_name: str
    ) -> None:
        """Save and restore progress for resume capability."""
        with Storage(tmp_db_path) as storage:
            # Save progress
            storage.save_progress('run_id', run_id)
            storage.save_progress('last_repo', react_repo_name)

            # Restore progress
            retrieved_run_id = storage.get_progress('run_id')
            last_repo = storage.get_progress('last_repo')

            assert retrieved_run_id == run_id
            assert last_repo == react_repo_name


class TestPydanticModels:
    """Basic examples of Pydantic model validation."""

    def test_run_id_format_validation(
        self,
        run_factory: Callable[..., Run],
        started_at_datetime: datetime,
        run_id: str,
    ) -> None:
        """Run IDs must follow the pattern run_YYYY-MM-DDTHH:MM:SSZ."""
        # Valid run ID
        run = run_factory()
        assert run.run_id == run_id

        # Invalid run ID raises ValidationError
        with pytest.raises(ValidationError):
            Run(
                run_id='invalid-run-id',
                started_at=started_at_datetime,
                status=RunStatus.RUNNING,
                config_metadata={
                    'max_repos': 1000,
                    'min_stars': 3,
                    'max_commits_per_repo': 100,
                    'time_window_days': 365,
                },
            )

    def test_repo_name_format_validation(
        self,
        repo_record_factory: Callable[..., RepoRecord],
        react_repo_name: str,
    ) -> None:
        """Repository names must be in owner/repo format."""
        record = repo_record_factory(repo=react_repo_name)
        assert record.repo == react_repo_name

        # Invalid repo name raises ValidationError
        with pytest.raises(ValidationError):
            repo_record_factory(repo='invalid-repo-name')  # Missing owner/


# =============================================================================
# COMPREHENSIVE MODEL TESTS
# =============================================================================


class TestRunModel:
    """Test Run model validation and constraints."""

    def test_run_with_all_fields(
        self, run_factory: Callable[..., Run], completed_at_datetime: datetime
    ) -> None:
        """Run with all fields populated."""
        run = run_factory(
            completed_at=completed_at_datetime,
            status=RunStatus.COMPLETED,
            repos_processed=1000,
            repos_qualified=847,
            total_commits_analyzed=84700,
        )
        assert run.repos_processed == 1000
        assert run.total_commits_analyzed == 84700

    def test_run_default_values(self, run_factory: Callable[..., Run]) -> None:
        """Run with default values for optional fields."""
        run = run_factory()
        assert run.completed_at is None
        assert run.repos_processed == 0
        assert run.repos_qualified == 0
        assert run.total_commits_analyzed == 0

    @pytest.mark.parametrize(
        'status',
        [RunStatus.RUNNING, RunStatus.COMPLETED, RunStatus.FAILED],
    )
    def test_all_run_statuses(
        self, status: RunStatus, run_factory: Callable[..., Run]
    ) -> None:
        """All run statuses should be valid."""
        run = run_factory(status=status)
        assert run.status == status

    def test_negative_counts_rejected(self, run_factory: Callable[..., Run]) -> None:
        """Negative counts should be rejected."""
        with pytest.raises(ValidationError):
            run_factory(repos_processed=-1)


class TestRepoRecordModel:
    """Test RepoRecord model validation and constraints."""

    def test_commit_counts_default_to_zero(
        self, repo_record_factory: Callable[..., RepoRecord]
    ) -> None:
        """All commit type counts should default to zero."""
        record = repo_record_factory()
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

    def test_minimum_stars_validation(
        self, repo_record_factory: Callable[..., RepoRecord]
    ) -> None:
        """Stars must be at least 3 (filter threshold)."""
        # Valid: exactly 3 stars
        record = repo_record_factory(stars=3)
        assert record.stars == 3

        # Invalid: less than 3 stars
        with pytest.raises(ValidationError):
            repo_record_factory(stars=2)

    def test_head_commit_sha_length(
        self, repo_record_factory: Callable[..., RepoRecord]
    ) -> None:
        """Head commit SHA must be between 7 and 40 characters."""
        # Valid: 7 characters
        record = repo_record_factory(head_commit='abc1234')
        assert len(record.head_commit) == 7

        # Invalid: too short
        with pytest.raises(ValidationError):
            repo_record_factory(head_commit='abc')

    def test_breaking_scope_fields_default_to_zero(
        self, repo_record_factory: Callable[..., RepoRecord]
    ) -> None:
        """All breaking/scope count fields should default to zero."""
        record = repo_record_factory()
        assert record.breaking_scoped == 0
        assert record.breaking_unscoped == 0
        assert record.nonbreaking_scoped == 0
        assert record.nonbreaking_unscoped == 0

    def test_breaking_scope_fields_can_be_set(
        self, repo_record_factory: Callable[..., RepoRecord]
    ) -> None:
        """Breaking/scope fields can be set to non-zero values."""
        record = repo_record_factory(
            commits_analyzed=100,
            breaking_scoped=5,
            breaking_unscoped=3,
            nonbreaking_scoped=25,
            nonbreaking_unscoped=67,
        )
        assert record.breaking_scoped == 5
        assert record.breaking_unscoped == 3
        assert record.nonbreaking_scoped == 25
        assert record.nonbreaking_unscoped == 67
        # Verify they sum to commits_analyzed
        assert (
            record.breaking_scoped
            + record.breaking_unscoped
            + record.nonbreaking_scoped
            + record.nonbreaking_unscoped
            == record.commits_analyzed
        )

    def test_breaking_scope_fields_must_be_non_negative(
        self, repo_record_factory: Callable[..., RepoRecord]
    ) -> None:
        """Breaking/scope fields must be non-negative."""
        with pytest.raises(ValidationError):
            repo_record_factory(commits_analyzed=100, breaking_scoped=-1)


class TestProgressModel:
    """Test Progress model for checkpointing."""

    def test_simple_string_progress(self) -> None:
        """Progress with a simple string value."""
        progress = Progress(
            key='last_repo',
            value='facebook/react',
            updated_at=datetime(2026, 1, 12, 4, 45, 0, tzinfo=UTC),
        )
        assert progress.key == 'last_repo'
        assert progress.value == 'facebook/react'

    def test_search_cursor_progress(self) -> None:
        """Progress with a SearchCursor value."""
        cursor = SearchCursor(stars_range='500..1000', page=3)
        progress = Progress(
            key='search_cursor',
            value=cursor,
            updated_at=datetime(2026, 1, 12, 4, 15, 0, tzinfo=UTC),
        )
        assert progress.key == 'search_cursor'
        assert isinstance(progress.value, SearchCursor)
        assert progress.value.page == 3


class TestExportDataModel:
    """Test ExportData model for visualization JSON."""

    def test_complete_export_data(
        self, run_id: str, completed_at_datetime: datetime
    ) -> None:
        """ExportData with all required fields."""
        export = ExportData(
            run_id=run_id,
            generated_at=completed_at_datetime,
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
                    'merge commits',
                    'bot authors',
                    'non-conventional messages',
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

    def test_list_all_runs(
        self, tmp_db_path: Path, run_factory: Callable[..., Run]
    ) -> None:
        """List all runs in storage."""
        with Storage(tmp_db_path) as storage:
            # Create multiple runs
            for i in range(3):
                run = run_factory(
                    run_id=f'run_2026-01-{10 + i:02d}T04:00:00Z',
                    started_at=datetime(2026, 1, 10 + i, 4, 0, 0, tzinfo=UTC),
                    status=RunStatus.COMPLETED,
                )
                storage.save_run(run)

            runs = storage.list_runs()
            assert len(runs) == 3

    def test_update_run_status(
        self,
        tmp_db_path: Path,
        run_factory: Callable[..., Run],
        run_id: str,
        completed_at_datetime: datetime,
    ) -> None:
        """Update a run's status."""
        with Storage(tmp_db_path) as storage:
            # Create a running run
            run = run_factory()
            storage.save_run(run)

            # Update to completed
            run.status = RunStatus.COMPLETED
            run.completed_at = completed_at_datetime
            run.repos_processed = 1000
            run.repos_qualified = 847
            storage.save_run(run)

            # Verify update
            updated = storage.get_run(run_id)
            assert updated is not None
            assert updated.status == RunStatus.COMPLETED
            assert updated.repos_processed == 1000

    def test_delete_run_and_repos(
        self,
        tmp_db_path: Path,
        run_factory: Callable[..., Run],
        repo_record_factory: Callable[..., RepoRecord],
        run_id: str,
    ) -> None:
        """Delete a run and its associated repo records."""
        with Storage(tmp_db_path) as storage:
            # Create a run with repos
            run = run_factory(status=RunStatus.COMPLETED)
            storage.save_run(run)

            record = repo_record_factory(commits_analyzed=10)
            storage.save_repo_record(record)

            # Delete run
            storage.delete_run(run_id)

            # Verify deletion
            assert storage.get_run(run_id) is None
            assert len(storage.get_repos_for_run(run_id)) == 0

    def test_get_nonexistent_run(self, tmp_db_path: Path) -> None:
        """Getting a nonexistent run returns None."""
        with Storage(tmp_db_path) as storage:
            assert storage.get_run('nonexistent-run') is None

    def test_get_nonexistent_progress(self, tmp_db_path: Path) -> None:
        """Getting nonexistent progress returns None."""
        with Storage(tmp_db_path) as storage:
            assert storage.get_progress('nonexistent-key') is None

    def test_clear_progress(
        self, tmp_db_path: Path, run_id: str, repo_name: str
    ) -> None:
        """Clear all progress data."""
        with Storage(tmp_db_path) as storage:
            storage.save_progress('run_id', run_id)
            storage.save_progress('last_repo', repo_name)

            storage.clear_progress()

            assert storage.get_progress('run_id') is None
            assert storage.get_progress('last_repo') is None


class TestStorageRetention:
    """Test retention policy enforcement."""

    def test_get_latest_completed_run(
        self, tmp_db_path: Path, run_factory: Callable[..., Run]
    ) -> None:
        """Get the most recent completed run."""
        with Storage(tmp_db_path) as storage:
            # Create multiple runs
            for i in range(3):
                run = run_factory(
                    run_id=f'run_2026-01-{10 + i:02d}T04:00:00Z',
                    started_at=datetime(2026, 1, 10 + i, 4, 0, 0, tzinfo=UTC),
                    status=RunStatus.COMPLETED,
                )
                storage.save_run(run)

            latest = storage.get_latest_completed_run()
            assert latest is not None
            assert latest.run_id == 'run_2026-01-12T04:00:00Z'  # Most recent of the 3

    def test_get_latest_completed_run_ignores_running(
        self, tmp_db_path: Path, run_factory: Callable[..., Run]
    ) -> None:
        """Latest completed run should ignore running runs."""
        with Storage(tmp_db_path) as storage:
            # Create a completed run
            completed = run_factory(
                run_id='run_2026-01-10T04:00:00Z',
                started_at=datetime(2026, 1, 10, 4, 0, 0, tzinfo=UTC),
                status=RunStatus.COMPLETED,
            )
            storage.save_run(completed)

            # Create a running run (more recent)
            running = run_factory()
            storage.save_run(running)

            latest = storage.get_latest_completed_run()
            assert latest is not None
            assert latest.run_id == 'run_2026-01-10T04:00:00Z'

    def test_prune_old_runs(
        self,
        tmp_db_path: Path,
        run_factory: Callable[..., Run],
        repo_record_factory: Callable[..., RepoRecord],
    ) -> None:
        """Prune runs beyond retention limit."""
        with Storage(tmp_db_path) as storage:
            # Create 5 completed runs
            for i in range(5):
                run = run_factory(
                    run_id=f'run_2026-01-{10 + i:02d}T04:00:00Z',
                    started_at=datetime(2026, 1, 10 + i, 4, 0, 0, tzinfo=UTC),
                    status=RunStatus.COMPLETED,
                )
                storage.save_run(run)

                # Add a repo record to each run
                record = repo_record_factory(
                    run_id=f'run_2026-01-{10 + i:02d}T04:00:00Z',
                    repo=f'owner/repo{i}',
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
                    'run_2026-01-12T04:00:00Z',
                    'run_2026-01-13T04:00:00Z',
                    'run_2026-01-14T04:00:00Z',
                ]
                for r in runs
            )


class TestStorageAtomicity:
    """Test atomic operations and data integrity."""

    def test_save_checkpoint_is_atomic(
        self,
        tmp_db_path: Path,
        run_factory: Callable[..., Run],
        repo_record_factory: Callable[..., RepoRecord],
        run_id: str,
        repo_name: str,
    ) -> None:
        """Checkpoint saves should be atomic."""
        with Storage(tmp_db_path) as storage:
            # Create a run
            run = run_factory()
            storage.save_run(run)

            # Save a checkpoint (run + repo + progress atomically)
            record = repo_record_factory(commits_analyzed=10)

            storage.save_checkpoint(
                run=run,
                record=record,
                last_repo=repo_name,
            )

            # Verify all data saved
            assert storage.get_run(run_id) is not None
            assert len(storage.get_repos_for_run(run_id)) == 1
            assert storage.get_progress('last_repo') == repo_name


class TestStoragePersistence:
    """Test that data persists across Storage instances."""

    def test_data_persists_after_close(
        self, tmp_db_path: Path, run_factory: Callable[..., Run], run_id: str
    ) -> None:
        """Data should persist after closing and reopening storage."""
        # First instance: create data
        with Storage(tmp_db_path) as storage1:
            run = run_factory(status=RunStatus.COMPLETED)
            storage1.save_run(run)

        # Second instance: verify data
        with Storage(tmp_db_path) as storage2:
            retrieved = storage2.get_run(run_id)
            assert retrieved is not None
            assert retrieved.status == RunStatus.COMPLETED

    def test_creates_directory_if_missing(
        self, tmp_path: Path, run_factory: Callable[..., Run]
    ) -> None:
        """Storage should create the data directory if it doesn't exist."""
        db_path = tmp_path / 'nested' / 'data' / 'dir'
        with Storage(db_path) as storage:
            # Should not raise, should create the directory
            run = run_factory()
            storage.save_run(run)

            assert db_path.exists()
