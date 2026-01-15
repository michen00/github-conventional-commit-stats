"""Tests for the collector module - orchestration of GitHub API and data collection.

This module tests the Collector class:
- Repository discovery flow
- Commit parsing orchestration
- Checkpoint save/resume
- SIGINT/SIGTERM handling
"""

import signal
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from conv_commit_stats.collector import Collector
from conv_commit_stats.github_client import RateLimitExceededError
from conv_commit_stats.storage import Run, RunStatus, Storage

# =============================================================================
# EXECUTABLE DOCUMENTATION - Read these first to understand the API
# =============================================================================


class TestCollectorBasics:
    """Basic examples showing how Collector works."""

    @pytest.fixture
    def mock_github_client(self) -> MagicMock:
        """Mock GitHubClient for testing."""
        client = MagicMock()
        client.search_repositories.return_value = [
            {
                'full_name': 'facebook/react',
                'stargazers_count': 220000,
                'default_branch': 'main',
                'pushed_at': '2026-01-12T10:30:00Z',
                'created_at': '2013-05-24T16:15:54Z',
                'language': 'JavaScript',
                'license': {'spdx_id': 'MIT'},
            }
        ]
        client.get_commits.return_value = [
            {
                'sha': 'abc123',
                'commit': {
                    'message': 'feat: add new feature',
                    'author': {'date': '2026-01-12T10:30:00Z'},
                },
                'author': {'login': 'johndoe'},
                'parents': [{'sha': 'parent1'}],
            }
        ]
        return client

    def test_collector_initialization(
        self, tmp_db_path: Path, mock_github_client: MagicMock
    ) -> None:
        """Collector can be initialized with storage and GitHub client."""
        storage = Storage(tmp_db_path)
        collector = Collector(
            storage=storage,
            github_client=mock_github_client,
            max_repos=100,
            min_stars=3,
        )
        assert collector.max_repos == 100
        assert collector.min_stars == 3
        storage.close()

    def test_discover_repositories(
        self, tmp_db_path: Path, mock_github_client: MagicMock
    ) -> None:
        """Collector can discover repositories using GitHub search."""
        with Storage(tmp_db_path) as storage:
            collector = Collector(
                storage=storage,
                github_client=mock_github_client,
                max_repos=10,
                min_stars=3,
            )

            repos = collector.discover_repositories()

            assert len(repos) == 1
            assert repos[0]['full_name'] == 'facebook/react'
            mock_github_client.search_repositories.assert_called()

    def test_process_repository(
        self, tmp_db_path: Path, mock_github_client: MagicMock
    ) -> None:
        """Collector can process a single repository and parse commits."""
        with Storage(tmp_db_path) as storage:
            # Create a run first
            run = Run(
                run_id='run_2026-01-12T04:00:00Z',
                started_at=datetime(2026, 1, 12, 4, 0, 0, tzinfo=UTC),
                status=RunStatus.RUNNING,
            )
            storage.save_run(run)

            collector = Collector(
                storage=storage,
                github_client=mock_github_client,
                max_repos=10,
                min_stars=3,
            )

            repo_data = {
                'full_name': 'facebook/react',
                'default_branch': 'main',
                'stargazers_count': 220000,
                'language': 'JavaScript',
                'created_at': '2013-05-24T16:15:54Z',
                'license': {'spdx_id': 'MIT'},
            }

            record = collector.process_repository(
                run_id=run.run_id,
                repo_data=repo_data,
            )

            assert record is not None
            assert record.repo == 'facebook/react'
            assert record.feat == 1  # One feat commit

    def test_process_repository_tracks_breaking_scope_combinations(
        self, tmp_db_path: Path, mock_github_client: MagicMock
    ) -> None:
        """Collector tracks all four breaking/scope combinations correctly."""
        with Storage(tmp_db_path) as storage:
            # Create a run first
            run = Run(
                run_id='run_2026-01-12T04:00:00Z',
                started_at=datetime(2026, 1, 12, 4, 0, 0, tzinfo=UTC),
                status=RunStatus.RUNNING,
            )
            storage.save_run(run)

            # Mock commits with all four combinations
            mock_github_client.get_commits.return_value = [
                {
                    'sha': 'abc123',
                    'commit': {
                        'message': 'feat(api)!: breaking change with scope',
                        'author': {'date': '2026-01-12T10:30:00Z'},
                    },
                    'author': {'login': 'johndoe'},
                    'parents': [{'sha': 'parent1'}],
                },
                {
                    'sha': 'def456',
                    'commit': {
                        'message': 'feat!: breaking change without scope',
                        'author': {'date': '2026-01-12T10:29:00Z'},
                    },
                    'author': {'login': 'johndoe'},
                    'parents': [{'sha': 'parent2'}],
                },
                {
                    'sha': 'ghi789',
                    'commit': {
                        'message': 'fix(ui): non-breaking with scope',
                        'author': {'date': '2026-01-12T10:28:00Z'},
                    },
                    'author': {'login': 'johndoe'},
                    'parents': [{'sha': 'parent3'}],
                },
                {
                    'sha': 'jkl012',
                    'commit': {
                        'message': 'docs: non-breaking without scope',
                        'author': {'date': '2026-01-12T10:27:00Z'},
                    },
                    'author': {'login': 'johndoe'},
                    'parents': [{'sha': 'parent4'}],
                },
            ]

            collector = Collector(
                storage=storage,
                github_client=mock_github_client,
                max_repos=10,
                min_stars=3,
            )

            repo_data = {
                'full_name': 'test/repo',
                'default_branch': 'main',
                'stargazers_count': 100,
                'language': 'Python',
                'created_at': '2020-01-01T00:00:00Z',
                'license': {'spdx_id': 'MIT'},
            }

            record = collector.process_repository(
                run_id=run.run_id,
                repo_data=repo_data,
            )

            assert record is not None
            assert record.commits_analyzed == 4
            # Verify all four combinations are tracked
            assert record.breaking_scoped == 1  # feat(api)!
            assert record.breaking_unscoped == 1  # feat!
            assert record.nonbreaking_scoped == 1  # fix(ui)
            assert record.nonbreaking_unscoped == 1  # docs
            # Verify they sum to commits_analyzed
            assert (
                record.breaking_scoped
                + record.breaking_unscoped
                + record.nonbreaking_scoped
                + record.nonbreaking_unscoped
                == record.commits_analyzed
            )


# =============================================================================
# COMPREHENSIVE TESTS
# =============================================================================


class TestRepositoryDiscovery:
    """Test repository discovery with various scenarios."""

    @pytest.fixture
    def mock_github_client(self) -> MagicMock:
        """Mock GitHubClient with configurable responses."""
        return MagicMock()

    def test_star_range_bucketing(
        self, tmp_db_path: Path, mock_github_client: MagicMock
    ) -> None:
        """Collector uses star-range bucketing for search pagination."""
        with Storage(tmp_db_path) as storage:
            # Mock responses for different star ranges
            call_count = 0

            def search_side_effect(*_args: Any, **kwargs: Any) -> list[dict[str, Any]]:  # noqa: ANN401
                nonlocal call_count
                call_count += 1
                query = kwargs.get('query', '')
                if 'stars:10000' in query:
                    return [
                        {'full_name': f'repo-{i}', 'stargazers_count': 15000}
                        for i in range(5)
                    ]
                if 'stars:5000' in query:
                    return [
                        {'full_name': f'repo-{i}', 'stargazers_count': 7500}
                        for i in range(5, 10)
                    ]
                return []

            mock_github_client.search_repositories.side_effect = search_side_effect

            collector = Collector(
                storage=storage,
                github_client=mock_github_client,
                max_repos=10,
                min_stars=3,
            )

            collector.discover_repositories()

            # Should have called search with different star ranges
            assert call_count > 0

    def test_respects_max_repos_limit(
        self, tmp_db_path: Path, mock_github_client: MagicMock
    ) -> None:
        """Collector stops after reaching max_repos limit."""
        with Storage(tmp_db_path) as storage:
            # Return many repos
            mock_github_client.search_repositories.return_value = [
                {'full_name': f'repo-{i}', 'stargazers_count': 100} for i in range(100)
            ]

            collector = Collector(
                storage=storage,
                github_client=mock_github_client,
                max_repos=10,
                min_stars=3,
            )

            repos = collector.discover_repositories()

            assert len(repos) <= 10

    def test_filters_by_min_stars(
        self, tmp_db_path: Path, mock_github_client: MagicMock
    ) -> None:
        """Collector filters repositories by minimum star count."""
        with Storage(tmp_db_path) as storage:
            mock_github_client.search_repositories.return_value = [
                {'full_name': 'repo-high', 'stargazers_count': 1000},
                {'full_name': 'repo-low', 'stargazers_count': 2},  # Below min
            ]

            collector = Collector(
                storage=storage,
                github_client=mock_github_client,
                max_repos=10,
                min_stars=3,
            )

            repos = collector.discover_repositories()

            # Should filter out repos with < 3 stars
            assert all(repo['stargazers_count'] >= 3 for repo in repos)


class TestCommitProcessing:
    """Test commit fetching and parsing."""

    @pytest.fixture
    def mock_github_client(self) -> MagicMock:
        """Mock GitHubClient with commit data."""
        client = MagicMock()
        client.get_commits.return_value = [
            {
                'sha': 'sha1',
                'commit': {
                    'message': 'feat: add feature',
                    'author': {'date': '2026-01-12T10:30:00Z'},
                },
                'author': {'login': 'johndoe'},
                'parents': [{'sha': 'parent1'}],
            },
            {
                'sha': 'sha2',
                'commit': {
                    'message': 'fix: resolve bug',
                    'author': {'date': '2026-01-12T10:29:00Z'},
                },
                'author': {'login': 'johndoe'},
                'parents': [{'sha': 'parent2'}],
            },
            {
                'sha': 'sha3',
                'commit': {
                    'message': "Merge branch 'feature'",
                    'author': {'date': '2026-01-12T10:28:00Z'},
                },
                'author': {'login': 'johndoe'},
                'parents': [{'sha': 'parent3'}, {'sha': 'parent4'}],  # Merge commit
            },
        ]
        return client

    def test_parses_conventional_commits(
        self, tmp_db_path: Path, mock_github_client: MagicMock
    ) -> None:
        """Collector correctly parses conventional commit types."""
        with Storage(tmp_db_path) as storage:
            run = Run(
                run_id='run_2026-01-12T04:00:00Z',
                started_at=datetime(2026, 1, 12, 4, 0, 0, tzinfo=UTC),
                status=RunStatus.RUNNING,
            )
            storage.save_run(run)

            collector = Collector(
                storage=storage,
                github_client=mock_github_client,
                max_repos=10,
                min_stars=3,
            )

            repo_data = {
                'full_name': 'owner/repo',
                'default_branch': 'main',
                'stargazers_count': 100,
                'language': 'Python',
                'created_at': '2020-01-01T00:00:00Z',
                'license': {'spdx_id': 'MIT'},
            }

            record = collector.process_repository(
                run_id=run.run_id,
                repo_data=repo_data,
            )

            assert record.feat == 1
            assert record.fix == 1
            assert record.commits_analyzed == 2  # Merge commit excluded

    def test_excludes_merge_commits(
        self, tmp_db_path: Path, mock_github_client: MagicMock
    ) -> None:
        """Collector excludes merge commits (2+ parents)."""
        with Storage(tmp_db_path) as storage:
            run = Run(
                run_id='run_2026-01-12T04:00:00Z',
                started_at=datetime(2026, 1, 12, 4, 0, 0, tzinfo=UTC),
                status=RunStatus.RUNNING,
            )
            storage.save_run(run)

            collector = Collector(
                storage=storage,
                github_client=mock_github_client,
                max_repos=10,
                min_stars=3,
            )

            repo_data = {
                'full_name': 'owner/repo',
                'default_branch': 'main',
                'stargazers_count': 100,
                'language': 'Python',
                'created_at': '2020-01-01T00:00:00Z',
                'license': {'spdx_id': 'MIT'},
            }

            record = collector.process_repository(
                run_id=run.run_id,
                repo_data=repo_data,
            )

            # Should have 2 commits (feat + fix), merge commit excluded
            assert record.commits_analyzed == 2

    def test_excludes_bot_commits(self, tmp_db_path: Path) -> None:
        """Collector excludes commits from bot authors."""
        mock_client = MagicMock()
        mock_client.get_commits.return_value = [
            {
                'sha': 'sha1',
                'commit': {
                    'message': 'feat: add feature',
                    'author': {'date': '2026-01-12T10:30:00Z'},
                },
                'author': {'login': 'dependabot[bot]'},  # Bot
                'parents': [{'sha': 'parent1'}],
            },
            {
                'sha': 'sha2',
                'commit': {
                    'message': 'fix: resolve bug',
                    'author': {'date': '2026-01-12T10:29:00Z'},
                },
                'author': {'login': 'johndoe'},  # Human
                'parents': [{'sha': 'parent2'}],
            },
        ]

        with Storage(tmp_db_path) as storage:
            run = Run(
                run_id='run_2026-01-12T04:00:00Z',
                started_at=datetime(2026, 1, 12, 4, 0, 0, tzinfo=UTC),
                status=RunStatus.RUNNING,
            )
            storage.save_run(run)

            collector = Collector(
                storage=storage,
                github_client=mock_client,
                max_repos=10,
                min_stars=3,
            )

            repo_data = {
                'full_name': 'owner/repo',
                'default_branch': 'main',
                'stargazers_count': 100,
                'language': 'Python',
                'created_at': '2020-01-01T00:00:00Z',
                'license': {'spdx_id': 'MIT'},
            }

            record = collector.process_repository(
                run_id=run.run_id,
                repo_data=repo_data,
            )

            # Should have 1 commit (fix), bot commit excluded
            assert record.commits_analyzed == 1
            assert record.fix == 1

    def test_respects_max_commits_per_repo(
        self, tmp_db_path: Path, mock_github_client: MagicMock
    ) -> None:
        """Collector limits commits per repository."""
        # Return 200 commits
        mock_github_client.get_commits.return_value = [
            {
                'sha': f'sha{i}',
                'commit': {
                    'message': f'feat: commit {i}',
                    'author': {'date': '2026-01-12T10:30:00Z'},
                },
                'author': {'login': 'johndoe'},
                'parents': [{'sha': f'parent{i}'}],
            }
            for i in range(200)
        ]

        with Storage(tmp_db_path) as storage:
            run = Run(
                run_id='run_2026-01-12T04:00:00Z',
                started_at=datetime(2026, 1, 12, 4, 0, 0, tzinfo=UTC),
                status=RunStatus.RUNNING,
            )
            storage.save_run(run)

            collector = Collector(
                storage=storage,
                github_client=mock_github_client,
                max_repos=10,
                min_stars=3,
                max_commits_per_repo=100,
            )

            repo_data = {
                'full_name': 'owner/repo',
                'default_branch': 'main',
                'stargazers_count': 100,
                'language': 'Python',
                'created_at': '2020-01-01T00:00:00Z',
                'license': {'spdx_id': 'MIT'},
            }

            record = collector.process_repository(
                run_id=run.run_id,
                repo_data=repo_data,
            )

            # Should have max 100 commits
            assert record.commits_analyzed <= 100


class TestCheckpointing:
    """Test checkpoint save and resume functionality."""

    def test_saves_checkpoint_after_each_repo(self, tmp_db_path: Path) -> None:
        """Collector saves checkpoint after processing each repository."""
        mock_client = MagicMock()
        mock_client.search_repositories.return_value = [
            {
                'full_name': 'owner/repo1',
                'stargazers_count': 100,
                'default_branch': 'main',
                'language': 'Python',
                'created_at': '2020-01-01T00:00:00Z',
                'license': {'spdx_id': 'MIT'},
            }
        ]
        mock_client.get_commits.return_value = []

        with Storage(tmp_db_path) as storage:
            collector = Collector(
                storage=storage,
                github_client=mock_client,
                max_repos=1,
                min_stars=3,
            )

            # Run collection
            run_id = collector.run()

            # Verify checkpoint was saved
            last_repo = storage.get_progress('last_repo')
            assert last_repo == 'owner/repo1'

            collector.complete_collection(run_id)

    def test_can_resume_from_checkpoint(self, tmp_db_path: Path) -> None:
        """Collector can resume from a saved checkpoint."""
        mock_client = MagicMock()
        mock_client.search_repositories.return_value = [
            {
                'full_name': 'owner/repo2',
                'stargazers_count': 100,
                'default_branch': 'main',
                'language': 'Python',
                'created_at': '2020-01-01T00:00:00Z',
                'license': {'spdx_id': 'MIT'},
            }
        ]
        mock_client.get_commits.return_value = []

        with Storage(tmp_db_path) as storage:
            # Create a run and checkpoint
            run = Run(
                run_id='run_2026-01-12T04:00:00Z',
                started_at=datetime(2026, 1, 12, 4, 0, 0, tzinfo=UTC),
                status=RunStatus.RUNNING,
            )
            storage.save_run(run)
            storage.save_progress('last_repo', 'owner/repo1')

            collector = Collector(
                storage=storage,
                github_client=mock_client,
                max_repos=10,
                min_stars=3,
            )

            # Resume should skip repo1 and start from repo2
            collector.resume_collection(run.run_id)

            # Verify repo1 was skipped
            repos = storage.get_repos_for_run(run.run_id)
            repo_names = [r.repo for r in repos]
            assert 'owner/repo1' not in repo_names


class TestSignalHandling:
    """Test graceful shutdown on SIGINT/SIGTERM."""

    def test_handles_sigint_gracefully(self, tmp_db_path: Path) -> None:
        """Collector saves progress and exits gracefully on SIGINT."""
        mock_client = MagicMock()
        mock_client.search_repositories.return_value = [
            {
                'full_name': 'owner/repo1',
                'stargazers_count': 100,
                'default_branch': 'main',
                'language': 'Python',
                'created_at': '2020-01-01T00:00:00Z',
                'license': {'spdx_id': 'MIT'},
            }
        ]
        mock_client.get_commits.return_value = []

        with Storage(tmp_db_path) as storage:
            collector = Collector(
                storage=storage,
                github_client=mock_client,
                max_repos=10,
                min_stars=3,
            )

            run_id = collector.start_collection()

            # Simulate SIGINT
            # Accessing private method for testing signal handling
            collector._handle_signal(signal.SIGINT, None)  # noqa: SLF001

            # Verify run is still in running state (resumable)
            run = storage.get_run(run_id)
            assert run.status == RunStatus.RUNNING

            collector.complete_collection(run_id)

    def test_handles_sigterm_gracefully(self, tmp_db_path: Path) -> None:
        """Collector saves progress and exits gracefully on SIGTERM."""
        mock_client = MagicMock()
        mock_client.search_repositories.return_value = []
        mock_client.get_commits.return_value = []

        with Storage(tmp_db_path) as storage:
            collector = Collector(
                storage=storage,
                github_client=mock_client,
                max_repos=10,
                min_stars=3,
            )

            run_id = collector.start_collection()

            # Simulate SIGTERM
            # Accessing private method for testing signal handling
            collector._handle_signal(signal.SIGTERM, None)  # noqa: SLF001

            # Verify run is still in running state (resumable)
            run = storage.get_run(run_id)
            assert run.status == RunStatus.RUNNING

            collector.complete_collection(run_id)


class TestErrorHandling:
    """Test error handling during collection."""

    def test_continues_on_individual_repo_failure(self, tmp_db_path: Path) -> None:
        """Collector continues processing if one repo fails."""
        mock_client = MagicMock()
        mock_client.search_repositories.return_value = [
            {
                'full_name': 'owner/repo-good',
                'stargazers_count': 100,
                'default_branch': 'main',
                'language': 'Python',
                'created_at': '2020-01-01T00:00:00Z',
                'license': {'spdx_id': 'MIT'},
            },
            {
                'full_name': 'owner/repo-bad',
                'stargazers_count': 100,
                'default_branch': 'main',
                'language': 'Python',
                'created_at': '2020-01-01T00:00:00Z',
                'license': {'spdx_id': 'MIT'},
            },
        ]

        # First repo succeeds, second fails
        call_count = 0

        def commits_side_effect(
            *_args: object, **_kwargs: object
        ) -> list[dict[str, Any]]:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return []  # repo-good succeeds
            msg = 'API error'
            raise RuntimeError(msg)  # repo-bad fails

        mock_client.get_commits.side_effect = commits_side_effect

        with Storage(tmp_db_path) as storage:
            collector = Collector(
                storage=storage,
                github_client=mock_client,
                max_repos=10,
                min_stars=3,
            )

            run_id = collector.run()

            # Should complete with at least one repo processed
            repos = storage.get_repos_for_run(run_id)
            assert len(repos) >= 1

            collector.complete_collection(run_id)

    def test_handles_rate_limit_errors(self, tmp_db_path: Path) -> None:
        """Collector handles rate limit errors gracefully."""
        mock_client = MagicMock()
        mock_client.search_repositories.side_effect = RateLimitExceededError(
            'Rate limit exceeded',
            reset_at=datetime.now(UTC),
            remaining=0,
        )

        with Storage(tmp_db_path) as storage:
            collector = Collector(
                storage=storage,
                github_client=mock_client,
                max_repos=10,
                min_stars=3,
            )

            # Should raise RateLimitExceededError when discovering repos
            with pytest.raises(RateLimitExceededError):
                collector.run()
