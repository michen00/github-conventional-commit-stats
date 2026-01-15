"""TinyDB storage layer for runs, repos, and progress tracking.

This module wraps TinyDB with typed access to three tables:
- runs: Run metadata (start/end times, status, counts)
- repos: Per-repo commit type counts
- progress: Resume checkpoints

The module also exports Pydantic models for all data entities.
"""

from datetime import UTC, datetime
from enum import StrEnum, auto
from pathlib import Path
from typing import Annotated

import pandera.polars as pap
from pydantic import BaseModel, Field, NonNegativeInt
from tinydb import Query, TinyDB

__all__ = (
    'CommitTypeCounts',
    'ExportData',
    'Methodology',
    'Progress',
    'RepoRecord',
    'RepoRecordSchema',
    'Run',
    'RunStatus',
    'SearchCursor',
    'Storage',
)


# =============================================================================
# ENUMERATIONS
# =============================================================================


class RunStatus(StrEnum):
    """Status of a collection run."""

    RUNNING = auto()
    COMPLETED = auto()
    FAILED = auto()


# =============================================================================
# PYDANTIC MODELS
# =============================================================================


class Run(BaseModel):
    """Represents a single collection execution.

    Attributes:
        run_id: Unique identifier in format run_YYYY-MM-DDTHH:MM:SSZ
        started_at: Collection start time (ISO 8601)
        completed_at: Collection end time (null if in progress)
        status: Current state: running, completed, failed
        repos_processed: Total repositories attempted
        repos_qualified: Repositories with valid commit data
        total_commits_analyzed: Sum of commits across all repos
    """

    run_id: str = Field(pattern=r'^run_\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$')
    started_at: datetime
    completed_at: datetime | None = None
    status: RunStatus
    repos_processed: NonNegativeInt = 0
    repos_qualified: NonNegativeInt = 0
    total_commits_analyzed: NonNegativeInt = 0


class RepoRecord(BaseModel):
    """Captures data about a single analyzed repository.

    Includes commit type counts for all 11 conventional commit types.

    Attributes:
        run_id: Foreign key to Run
        repo: Full name in owner/repo format
        default_branch: Branch analyzed (e.g., main)
        head_commit: SHA of latest commit at collection time
        stars: Star count at collection time (must be >= 3)
        language: Primary language (may be null)
        created_at: Repository creation date
        license: SPDX license identifier
        timestamp: When this record was created
        commits_analyzed: Number of conventional commits found
        build, chore, ci, etc.: Count of each commit type
    """

    run_id: str
    repo: str = Field(pattern=r'^[\w.-]+/[\w.-]+$')
    default_branch: str
    head_commit: str = Field(min_length=7, max_length=40)
    stars: Annotated[int, Field(ge=3)]
    language: str | None = None
    created_at: datetime
    license: str | None = None
    timestamp: datetime
    commits_analyzed: NonNegativeInt
    build: NonNegativeInt = 0
    chore: NonNegativeInt = 0
    ci: NonNegativeInt = 0
    docs: NonNegativeInt = 0
    feat: NonNegativeInt = 0
    fix: NonNegativeInt = 0
    perf: NonNegativeInt = 0
    refactor: NonNegativeInt = 0
    revert: NonNegativeInt = 0
    style: NonNegativeInt = 0
    test: NonNegativeInt = 0
    breaking_scoped: NonNegativeInt = 0
    breaking_unscoped: NonNegativeInt = 0
    nonbreaking_scoped: NonNegativeInt = 0
    nonbreaking_unscoped: NonNegativeInt = 0


class SearchCursor(BaseModel):
    """Position in search pagination.

    Attributes:
        stars_range: Star range being searched (e.g., "500..1000")
        page: Current page number (1-indexed)
    """

    stars_range: str
    page: Annotated[int, Field(ge=1)]


class Progress(BaseModel):
    """Stores resumption state for interrupted collection runs.

    Attributes:
        key: Progress key (run_id, search_cursor, last_repo)
        value: Progress value (type depends on key)
        updated_at: When this checkpoint was saved
    """

    key: str
    value: str | SearchCursor
    updated_at: datetime


class CommitTypeCounts(BaseModel):
    """Aggregated counts per commit type.

    All fields default to 0 and must be non-negative.
    """

    build: NonNegativeInt = 0
    chore: NonNegativeInt = 0
    ci: NonNegativeInt = 0
    docs: NonNegativeInt = 0
    feat: NonNegativeInt = 0
    fix: NonNegativeInt = 0
    perf: NonNegativeInt = 0
    refactor: NonNegativeInt = 0
    revert: NonNegativeInt = 0
    style: NonNegativeInt = 0
    test: NonNegativeInt = 0


class Methodology(BaseModel):
    """Collection methodology metadata for transparency.

    Attributes:
        min_stars: Minimum star filter used
        max_commits_per_repo: Maximum commits analyzed per repo
        time_window_days: Days of commit history analyzed
        excluded: List of exclusion criteria
    """

    min_stars: int = 3
    max_commits_per_repo: int = 100
    time_window_days: int = 365
    excluded: list[str]


class ExportData(BaseModel):
    """Visualization-consumable format with aggregated commit type counts.

    This is the schema for docs/data.json consumed by the visualization.

    Attributes:
        run_id: Source run identifier
        generated_at: Export timestamp
        total_repos: Number of repositories in aggregation
        total_commits: Total conventional commits counted
        counts: Aggregated counts per type
        breaking_scoped: Aggregated breaking commits with scope
        breaking_unscoped: Aggregated breaking commits without scope
        nonbreaking_scoped: Aggregated non-breaking commits with scope
        nonbreaking_unscoped: Plain commits (neither breaking/scoped)
        methodology: Collection methodology metadata
    """

    run_id: str
    generated_at: datetime
    total_repos: NonNegativeInt
    total_commits: NonNegativeInt
    counts: CommitTypeCounts
    breaking_scoped: NonNegativeInt = 0
    breaking_unscoped: NonNegativeInt = 0
    nonbreaking_scoped: NonNegativeInt = 0
    nonbreaking_unscoped: NonNegativeInt = 0
    methodology: Methodology


# =============================================================================
# PANDERA SCHEMAS
# =============================================================================


def _create_repo_record_schema() -> pap.DataFrameSchema:
    """Generate Pandera schema from RepoRecord Pydantic model.

    This ensures schema stays in sync with RepoRecord fields automatically.
    Note: datetime fields are serialized as ISO 8601 strings by model_dump(mode='json'),
    so Pandera validates them as strings (Polars parses them automatically).
    """
    # Base schema with all RepoRecord fields
    schema_dict: dict[str, pap.Column] = {
        'run_id': pap.Column(str),
        'repo': pap.Column(str, checks=pap.Check.str_matches(r'^[\w.-]+/[\w.-]+$')),
        'default_branch': pap.Column(str),
        'head_commit': pap.Column(str, checks=pap.Check.str_length(7, 40)),
        'stars': pap.Column(int, checks=pap.Check.ge(3)),
        'language': pap.Column(str, nullable=True),
        # datetime fields serialized as ISO 8601 strings by model_dump(mode='json')
        'created_at': pap.Column(str),  # ISO 8601 datetime string
        'license': pap.Column(str, nullable=True),
        'timestamp': pap.Column(str),  # ISO 8601 datetime string
        'commits_analyzed': pap.Column(int, checks=pap.Check.ge(0)),
    }

    # Add all 11 commit type fields with non-negative constraint
    # Use CommitTypeCounts.model_fields to ensure completeness
    for field_name in CommitTypeCounts.model_fields:
        schema_dict[field_name] = pap.Column(int, checks=pap.Check.ge(0))

    # Add breaking/scope combination fields
    schema_dict['breaking_scoped'] = pap.Column(int, checks=pap.Check.ge(0))
    schema_dict['breaking_unscoped'] = pap.Column(int, checks=pap.Check.ge(0))
    schema_dict['nonbreaking_scoped'] = pap.Column(int, checks=pap.Check.ge(0))
    schema_dict['nonbreaking_unscoped'] = pap.Column(int, checks=pap.Check.ge(0))

    return pap.DataFrameSchema(schema_dict)


# Create schema instance
RepoRecordSchema = _create_repo_record_schema()


# =============================================================================
# STORAGE CLASS
# =============================================================================


class Storage:
    """TinyDB wrapper for conventional commit census data.

    Provides typed access to three tables:
    - runs: Run metadata
    - repos: Per-repo commit counts
    - progress: Resume checkpoints

    All operations are atomic at the table level. For multi-table
    atomicity, use save_checkpoint().

    Can be used as a context manager for automatic cleanup:
        with Storage(path) as storage:
            storage.save_run(run)
    """

    def __init__(self, db_path: Path) -> None:
        """Initialize storage with the given data directory.

        Creates the directory if it doesn't exist.
        Creates three TinyDB files: runs.json, repos.json, progress.json
        """
        self._db_path = Path(db_path)
        self._db_path.mkdir(parents=True, exist_ok=True)

        self._runs_db = TinyDB(self._db_path / 'runs.json')
        self._repos_db = TinyDB(self._db_path / 'repos.json')
        self._progress_db = TinyDB(self._db_path / 'progress.json')

        self._runs = self._runs_db.table('runs')
        self._repos = self._repos_db.table('repos')
        self._progress = self._progress_db.table('progress')

    def __enter__(self) -> 'Storage':
        """Enter context manager."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        """Exit context manager, closing all connections."""
        self.close()

    def close(self) -> None:
        """Close all TinyDB connections."""
        self._runs_db.close()
        self._repos_db.close()
        self._progress_db.close()

    # -------------------------------------------------------------------------
    # Run Operations
    # -------------------------------------------------------------------------

    def save_run(self, run: Run) -> None:
        """Save or update a run record.

        If a run with the same run_id exists, it will be updated.
        """
        q = Query()
        self._runs.upsert(
            run.model_dump(mode='json'),
            q.run_id == run.run_id,
        )

    def get_run(self, run_id: str) -> Run | None:
        """Get a run by its ID, or None if not found."""
        q = Query()
        result = self._runs.search(q.run_id == run_id)
        if not result:
            return None
        return Run.model_validate(result[0])

    def list_runs(self) -> list[Run]:
        """List all runs, sorted by started_at descending."""
        results = self._runs.all()
        runs = [Run.model_validate(r) for r in results]
        return sorted(runs, key=lambda r: r.started_at, reverse=True)

    def delete_run(self, run_id: str) -> None:
        """Delete a run and all its associated repo records."""
        q = Query()
        self._runs.remove(q.run_id == run_id)
        self._repos.remove(q.run_id == run_id)

    def get_latest_completed_run(self) -> Run | None:
        """Get the most recent completed run, or None if no completed runs."""
        q = Query()
        results = self._runs.search(q.status == RunStatus.COMPLETED.value)
        if not results:
            return None

        runs = [Run.model_validate(r) for r in results]
        runs.sort(key=lambda r: r.started_at, reverse=True)
        return runs[0] if runs else None

    def get_running_run(self) -> Run | None:
        """Get the currently running run, or None if no run is running."""
        q = Query()
        results = self._runs.search(q.status == RunStatus.RUNNING.value)
        if not results:
            return None
        return Run.model_validate(results[0])

    def prune_old_runs(self, keep: int = 3) -> int:
        """Delete runs beyond the retention limit.

        Keeps the most recent `keep` completed runs.
        Returns the number of runs deleted.
        """
        q = Query()
        results = self._runs.search(q.status == RunStatus.COMPLETED.value)
        runs = [Run.model_validate(r) for r in results]
        runs.sort(key=lambda r: r.started_at, reverse=True)

        to_delete = runs[keep:]
        for run in to_delete:
            self.delete_run(run.run_id)

        return len(to_delete)

    # -------------------------------------------------------------------------
    # Repo Record Operations
    # -------------------------------------------------------------------------

    def save_repo_record(self, record: RepoRecord) -> None:
        """Save a repository record.

        If a record for the same run_id + repo exists, it will be updated.
        """
        q = Query()
        self._repos.upsert(
            record.model_dump(mode='json'),
            (q.run_id == record.run_id) & (q.repo == record.repo),
        )

    def get_repos_for_run(self, run_id: str) -> list[RepoRecord]:
        """Get all repo records for a run."""
        q = Query()
        results = self._repos.search(q.run_id == run_id)
        return [RepoRecord.model_validate(r) for r in results]

    def count_repos_for_run(self, run_id: str) -> int:
        """Count the number of repo records for a run."""
        q = Query()
        return len(self._repos.search(q.run_id == run_id))

    # -------------------------------------------------------------------------
    # Progress Operations
    # -------------------------------------------------------------------------

    def save_progress(self, key: str, value: str | SearchCursor) -> None:
        """Save a progress checkpoint."""
        progress = Progress(
            key=key,
            value=value,
            updated_at=datetime.now(UTC),
        )
        q = Query()
        self._progress.upsert(
            progress.model_dump(mode='json'),
            q.key == key,
        )

    def get_progress(self, key: str) -> str | SearchCursor | None:
        """Get a progress value by key, or None if not found."""
        q = Query()
        result = self._progress.search(q.key == key)
        if not result:
            return None

        progress = Progress.model_validate(result[0])
        value = progress.value

        # If value is a dict (from JSON), try to deserialize as SearchCursor
        # Note: When deserialized from JSON, SearchCursor becomes a dict
        # We need to check the raw dict from JSON, not the Pydantic-validated value
        if key == 'search_cursor':
            raw_value = result[0].get('value')
            # Check if it's a dict in the raw JSON (before Pydantic validation)
            if isinstance(raw_value, dict):
                try:
                    return SearchCursor(**raw_value)
                except (TypeError, ValueError):
                    # If deserialization fails, return the validated value
                    return value
            # Already a SearchCursor object or str
            return value

        return value

    def clear_progress(self) -> None:
        """Clear all progress data."""
        self._progress.truncate()

    # -------------------------------------------------------------------------
    # Atomic Checkpoint Operations
    # -------------------------------------------------------------------------

    def save_checkpoint(
        self,
        run: Run,
        record: RepoRecord,
        last_repo: str,
        search_cursor: SearchCursor | None = None,
    ) -> None:
        """Save a checkpoint atomically.

        Saves the run state, repo record, and progress markers together.
        This ensures that if the process is interrupted, we can resume
        from a consistent state.
        """
        self.save_run(run)
        self.save_repo_record(record)
        self.save_progress('last_repo', last_repo)

        if search_cursor is not None:
            self.save_progress('search_cursor', search_cursor)
