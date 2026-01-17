"""Smoke tests for CLI commands - end-to-end validation.

These tests verify that CLI commands can be invoked and produce expected output.
They use CliRunner from Typer for testing.
"""

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from conv_commit_stats.cli import app
from conv_commit_stats.storage import Run, RunStatus, Storage

runner = CliRunner()


# =============================================================================
# EXECUTABLE DOCUMENTATION - Read these first to understand the CLI
# =============================================================================


class TestCLIBasics:
    """Basic examples showing how the CLI works."""

    def test_help_command(self) -> None:
        """The --help flag shows usage information."""
        result = runner.invoke(app, ['--help'])
        assert result.exit_code == 0
        assert 'Conventional Commit Census' in result.stdout
        assert 'collect' in result.stdout
        assert 'export' in result.stdout

    def test_collect_command_help(self) -> None:
        """The collect command has its own help."""
        result = runner.invoke(app, ['collect', '--help'])
        assert result.exit_code == 0
        assert 'collect' in result.stdout.lower()
        assert '--max-repos' in result.stdout
        assert '--min-stars' in result.stdout

    def test_collect_requires_github_token(
        self, tmp_db_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Collect command requires GITHUB_TOKEN environment variable."""
        # Remove GITHUB_TOKEN if it exists
        monkeypatch.delenv('GITHUB_TOKEN', raising=False)
        result = runner.invoke(
            app,
            ['collect', '--max-repos', '1', '--db-path', str(tmp_db_path)],
        )
        assert result.exit_code != 0
        assert 'GITHUB_TOKEN' in result.stdout or 'token' in result.stdout.lower()


class TestCollectCommand:
    """Test the collect command."""

    @patch('conv_commit_stats.cli.Collector')
    def test_collect_command_basic(
        self,
        mock_collector_class: MagicMock,
        tmp_db_path: Path,
        github_token_env: None,  # noqa: ARG002
        run_id: str,
    ) -> None:
        """Collect command runs successfully with valid token."""
        # Mock the collector
        mock_collector = MagicMock()
        mock_collector.run.return_value = run_id
        mock_collector_class.return_value = mock_collector

        result = runner.invoke(
            app,
            [
                'collect',
                '--max-repos',
                '10',
                '--min-stars',
                '3',
                '--db-path',
                str(tmp_db_path),
            ],
        )

        assert result.exit_code == 0
        mock_collector.run.assert_called_once()

    @patch('conv_commit_stats.cli.Collector')
    def test_collect_with_resume(
        self,
        mock_collector_class: MagicMock,
        tmp_db_path: Path,
        github_token_env: None,  # noqa: ARG002
        run_id: str,
    ) -> None:
        """Collect command supports --resume flag."""
        mock_collector = MagicMock()
        mock_collector.run.return_value = run_id
        mock_collector_class.return_value = mock_collector

        result = runner.invoke(
            app,
            [
                'collect',
                '--resume',
                '--db-path',
                str(tmp_db_path),
            ],
        )

        assert result.exit_code == 0
        mock_collector.run.assert_called_once_with(resume=True)


class TestExportCommand:
    """Test the export command."""

    def test_export_command_basic(
        self,
        tmp_db_path: Path,
        run_factory: Callable[..., Run],
        repo_record_factory: Callable[..., object],
        completed_at_datetime: datetime,
    ) -> None:
        """Export command exports data to JSON."""
        # Create a completed run with data
        with Storage(tmp_db_path) as storage:
            run = run_factory(
                completed_at=completed_at_datetime,
                status=RunStatus.COMPLETED,
                repos_processed=10,
                repos_qualified=8,
                total_commits_analyzed=100,
            )
            storage.save_run(run)

            # Add a repo record
            repo = repo_record_factory(
                created_at=datetime(2020, 1, 1, tzinfo=UTC),
                commits_analyzed=10,
                feat=5,
                fix=3,
                docs=2,
            )
            storage.save_repo_record(repo)

        result = runner.invoke(
            app,
            [
                'export',
                '--output',
                str(tmp_db_path / 'export.json'),
                '--db-path',
                str(tmp_db_path),
            ],
        )

        assert result.exit_code == 0
        assert (tmp_db_path / 'export.json').exists()


class TestStatusCommand:
    """Test the status command."""

    def test_status_shows_running_run(
        self, tmp_db_path: Path, run_factory: Callable[..., Run], run_id: str
    ) -> None:
        """Status command shows current running run."""
        with Storage(tmp_db_path) as storage:
            run = run_factory(
                repos_processed=5,
                repos_qualified=4,
                total_commits_analyzed=50,
            )
            storage.save_run(run)

        result = runner.invoke(
            app,
            ['status', '--db-path', str(tmp_db_path)],
        )

        assert result.exit_code == 0
        assert 'running' in result.stdout.lower()
        assert run_id in result.stdout

    def test_status_shows_no_runs(self, tmp_db_path: Path) -> None:
        """Status command handles case with no runs."""
        result = runner.invoke(
            app,
            ['status', '--db-path', str(tmp_db_path)],
        )

        assert result.exit_code == 0
        assert 'no runs' in result.stdout.lower() or 'no data' in result.stdout.lower()


class TestValidateCommand:
    """Test the validate command."""

    def test_validate_passes_with_valid_data(
        self,
        tmp_db_path: Path,
        run_factory: Callable[..., Run],
        repo_record_factory: Callable[..., object],
        completed_at_datetime: datetime,
    ) -> None:
        """Validate command passes with valid data."""
        with Storage(tmp_db_path) as storage:
            run = run_factory(
                completed_at=completed_at_datetime,
                status=RunStatus.COMPLETED,
                repos_processed=10,
                repos_qualified=8,
                total_commits_analyzed=100,
            )
            storage.save_run(run)

            # Add a repo record with valid counts
            repo = repo_record_factory(
                created_at=datetime(2020, 1, 1, tzinfo=UTC),
                commits_analyzed=10,
                feat=5,
                fix=3,
                docs=2,
            )
            storage.save_repo_record(repo)

        result = runner.invoke(
            app,
            ['validate', '--db-path', str(tmp_db_path)],
        )

        assert result.exit_code == 0
        assert 'ok' in result.stdout.lower() or 'valid' in result.stdout.lower()

    def test_validate_with_no_data(self, tmp_db_path: Path) -> None:
        """Validate command handles empty database."""
        result = runner.invoke(
            app,
            ['validate', '--db-path', str(tmp_db_path)],
        )

        # Should pass (empty is valid)
        assert result.exit_code == 0


class TestExportErrorPaths:
    """Test export command error handling."""

    def test_export_with_no_completed_runs(self, tmp_db_path: Path) -> None:
        """Export fails gracefully when no completed runs exist."""
        result = runner.invoke(
            app,
            [
                'export',
                '--output',
                str(tmp_db_path / 'export.json'),
                '--db-path',
                str(tmp_db_path),
            ],
        )

        assert result.exit_code == 1
        assert 'No completed runs found' in result.stdout

    def test_export_with_invalid_run_id(self, tmp_db_path: Path) -> None:
        """Export fails gracefully with invalid run ID."""
        result = runner.invoke(
            app,
            ['export', '--run', 'invalid-run-id', '--db-path', str(tmp_db_path)],
        )

        assert result.exit_code == 1
        assert 'Run not found' in result.stdout

    def test_export_with_no_repos(
        self,
        tmp_db_path: Path,
        run_factory: Callable[..., Run],
        completed_at_datetime: datetime,
    ) -> None:
        """Export fails gracefully when run has no repos."""
        with Storage(tmp_db_path) as storage:
            run = run_factory(
                completed_at=completed_at_datetime,
                status=RunStatus.COMPLETED,
                repos_processed=0,
                repos_qualified=0,
                total_commits_analyzed=0,
            )
            storage.save_run(run)

        result = runner.invoke(
            app,
            [
                'export',
                '--output',
                str(tmp_db_path / 'export.json'),
                '--db-path',
                str(tmp_db_path),
            ],
        )

        assert result.exit_code == 1
        assert 'No repositories found' in result.stdout


class TestValidateErrorPaths:
    """Test validate command error handling."""

    def test_validate_with_invalid_run_id(self, tmp_db_path: Path) -> None:
        """Validate fails gracefully with invalid run ID."""
        result = runner.invoke(
            app,
            ['validate', '--run', 'invalid-run-id', '--db-path', str(tmp_db_path)],
        )

        assert result.exit_code == 1
        assert 'Run not found' in result.stdout

    def test_validate_detects_data_integrity_issues(
        self,
        tmp_db_path: Path,
        run_factory: Callable[..., Run],
        repo_record_factory: Callable[..., object],
        completed_at_datetime: datetime,
        run_id: str,
    ) -> None:
        """Validate detects when commit counts don't sum correctly."""
        with Storage(tmp_db_path) as storage:
            run = run_factory(
                completed_at=completed_at_datetime,
                status=RunStatus.COMPLETED,
                repos_processed=1,
                repos_qualified=1,
                total_commits_analyzed=10,
            )
            storage.save_run(run)

            # Create repo with mismatched counts (commits_analyzed=10 but sum=5)
            repo = repo_record_factory(
                created_at=datetime(2020, 1, 1, tzinfo=UTC),
                commits_analyzed=10,  # Says 10 commits
                feat=3,
                fix=2,
                # Sum is only 5, not 10
            )
            storage.save_repo_record(repo)

        result = runner.invoke(
            app,
            [
                'validate',
                '--run',
                run_id,
                '--db-path',
                str(tmp_db_path),
            ],
        )

        assert result.exit_code == 1
        assert 'mismatch' in result.stdout.lower() or 'failed' in result.stdout.lower()


class TestCollectErrorPaths:
    """Test collect command error handling."""

    def test_collect_with_concurrent_run(
        self,
        tmp_db_path: Path,
        run_factory: Callable[..., Run],
        github_token_env: None,  # noqa: ARG002
    ) -> None:
        """Collect fails when another run is already in progress."""
        # Create a running run
        with Storage(tmp_db_path) as storage:
            run = run_factory()
            storage.save_run(run)

        # Attempting to start a new collection should fail
        result = runner.invoke(
            app,
            ['collect', '--max-repos', '10', '--db-path', str(tmp_db_path)],
        )

        assert result.exit_code != 0
        assert (
            'in progress' in result.stdout.lower() or 'error' in result.stdout.lower()
        )


class TestPruneCommand:
    """Test the prune command."""

    def test_prune_removes_old_runs(
        self, tmp_db_path: Path, run_factory: Callable[..., Run]
    ) -> None:
        """Prune command removes runs beyond retention limit."""
        with Storage(tmp_db_path) as storage:
            # Create 5 completed runs
            for i in range(5):
                run = run_factory(
                    run_id=f'run_2026-01-{10 + i:02d}T04:00:00Z',
                    started_at=datetime(2026, 1, 10 + i, 4, 0, 0, tzinfo=UTC),
                    completed_at=datetime(2026, 1, 10 + i, 5, 0, 0, tzinfo=UTC),
                    status=RunStatus.COMPLETED,
                    repos_processed=10,
                    repos_qualified=8,
                    total_commits_analyzed=100,
                )
                storage.save_run(run)

        result = runner.invoke(
            app,
            ['prune', '--keep', '3', '--db-path', str(tmp_db_path)],
        )

        assert result.exit_code == 0

        # Verify only 3 runs remain
        with Storage(tmp_db_path) as storage:
            runs = storage.list_runs()
            completed = [r for r in runs if r.status == RunStatus.COMPLETED]
            assert len(completed) == 3

    def test_prune_dry_run(
        self, tmp_db_path: Path, run_factory: Callable[..., Run]
    ) -> None:
        """Prune command with --dry-run doesn't delete anything."""
        with Storage(tmp_db_path) as storage:
            # Create 5 completed runs
            for i in range(5):
                run = run_factory(
                    run_id=f'run_2026-01-{10 + i:02d}T04:00:00Z',
                    started_at=datetime(2026, 1, 10 + i, 4, 0, 0, tzinfo=UTC),
                    completed_at=datetime(2026, 1, 10 + i, 5, 0, 0, tzinfo=UTC),
                    status=RunStatus.COMPLETED,
                    repos_processed=10,
                    repos_qualified=8,
                    total_commits_analyzed=100,
                )
                storage.save_run(run)

        result = runner.invoke(
            app,
            ['prune', '--keep', '3', '--dry-run', '--db-path', str(tmp_db_path)],
        )

        assert result.exit_code == 0

        # Verify all 5 runs still exist
        with Storage(tmp_db_path) as storage:
            runs = storage.list_runs()
            completed = [r for r in runs if r.status == RunStatus.COMPLETED]
            assert len(completed) == 5
