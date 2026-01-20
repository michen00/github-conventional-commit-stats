"""Shared pytest fixtures for conv_commit_stats tests.

Provides:
- tmp_db_path: Temporary directory for TinyDB storage tests
- mock_github_responses: Pre-configured respx mocks for GitHub API
- sample_commit_messages: Test data for parsing tests
- Common test data fixtures: run_id, datetimes, repo names, etc.
- Factory fixtures: run, repo_record
"""

from collections.abc import Callable, Generator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from conv_commit_stats.storage import RepoRecord, Run, RunStatus, Storage


@pytest.fixture
def tmp_db_path(tmp_path: Path) -> Path:
    """Provide a temporary directory for TinyDB storage tests.

    Creates the standard TinyDB file structure:
    - runs.json
    - repos.json
    - progress.json
    """
    return tmp_path


@pytest.fixture
def storage(tmp_path: Path) -> Generator['Storage', None, None]:
    """Provide a Storage instance that auto-closes after test.

    Usage:
        def test_something(storage: Storage):
            storage.save_run(run)
    """
    with Storage(tmp_path) as store:
        yield store


@pytest.fixture
def sample_commit_messages() -> dict[str, list[str]]:
    """Provide sample commit messages categorized by type.

    Returns a dict mapping commit types to lists of valid messages.
    """
    return {
        'feat': [
            'feat: add user authentication',
            'feat(auth): implement OAuth2 login',
            'feat!: breaking change to API',
            'feat(api)!: remove deprecated endpoints',
        ],
        'fix': [
            'fix: resolve memory leak in parser',
            'fix(ui): correct button alignment',
            'fix!: breaking fix for security issue',
        ],
        'docs': [
            'docs: update README',
            'docs(api): add endpoint documentation',
        ],
        'style': [
            'style: format code with black',
            'style(tests): fix linting errors',
        ],
        'refactor': [
            'refactor: simplify authentication logic',
            'refactor(db): optimize query performance',
        ],
        'perf': [
            'perf: improve startup time',
            'perf(search): add caching layer',
        ],
        'test': [
            'test: add unit tests for parser',
            'test(integration): add e2e tests',
        ],
        'build': [
            'build: update dependencies',
            'build(docker): optimize image size',
        ],
        'ci': [
            'ci: add GitHub Actions workflow',
            'ci(release): automate version bumping',
        ],
        'chore': [
            'chore: clean up unused files',
            'chore(deps): bump version of httpx',
        ],
        'revert': [
            'revert: revert previous commit',
            'revert: revert "feat: add feature"',
        ],
    }


@pytest.fixture
def invalid_commit_messages() -> list[str]:
    """Provide commit messages that are NOT conventional commits."""
    return [
        'Update README',
        'Fix bug',
        'WIP',
        "Merge branch 'main' into feature",
        'initial commit',
        'v1.0.0',
        '',
        '   ',
        'FEAT: uppercase type',
        'feat:missing space',
        'Feat: capitalized type',
        'feature: wrong type name',
        'feat - wrong separator',
        'feat() empty scope',
    ]


@pytest.fixture
def bot_authors() -> list[str]:
    """Provide author names that should be detected as bots."""
    return [
        'dependabot[bot]',
        'renovate[bot]',
        'github-actions[bot]',
        'pre-commit-ci[bot]',
        'semantic-release-bot',
        'snyk-bot',
        'greenkeeper[bot]',
        'imgbot[bot]',
        'allcontributors[bot]',
        'mergify[bot]',
        'codecov[bot]',
        'depfu[bot]',
        'whitesource-bolt-for-github[bot]',
        'mend-bolt-for-github[bot]',
        'restyled-io[bot]',
        'github-learning-lab[bot]',
        'release-please[bot]',
    ]


@pytest.fixture
def human_authors() -> list[str]:
    """Provide author names that should NOT be detected as bots."""
    return [
        'john-doe',
        'jane_smith',
        'developer123',
        'the-real-bot-master',  # Contains "bot" but is a human
        'robotics-enthusiast',  # Contains "bot" but is a human
    ]


@pytest.fixture
def sample_github_repo() -> dict[str, Any]:
    """Provide a sample GitHub repository API response."""
    return {
        'id': 10270250,
        'name': 'react',
        'full_name': 'facebook/react',
        'owner': {'login': 'facebook'},
        'html_url': 'https://github.com/facebook/react',
        'description': 'The library for web and native user interfaces',
        'fork': False,
        'created_at': '2013-05-24T16:15:54Z',
        'updated_at': '2026-01-12T12:00:00Z',
        'pushed_at': '2026-01-12T10:30:00Z',
        'stargazers_count': 220000,
        'language': 'JavaScript',
        'default_branch': 'main',
        'archived': False,
        'license': {'spdx_id': 'MIT'},
    }


@pytest.fixture
def sample_github_commit() -> dict[str, Any]:
    """Provide a sample GitHub commit API response."""
    return {
        'sha': 'abc123def456789',
        'commit': {
            'author': {
                'name': 'John Doe',
                'email': 'john@example.com',
                'date': '2026-01-12T10:30:00Z',
            },
            'committer': {
                'name': 'John Doe',
                'email': 'john@example.com',
                'date': '2026-01-12T10:30:00Z',
            },
            'message': 'feat(api): add new endpoint for user data',
        },
        'author': {'login': 'johndoe'},
        'committer': {'login': 'johndoe'},
        'parents': [{'sha': 'parent123'}],
    }


@pytest.fixture
def default_config_metadata() -> dict[str, int]:
    """Provide standard config metadata for test runs.

    Returns a dict with default collection configuration parameters.
    """
    return {
        'max_repos': 1000,
        'min_stars': 3,
        'max_commits_per_repo': 100,
        'time_window_days': 365,
    }


# =============================================================================
# COMMON TEST DATA FIXTURES
# =============================================================================


@pytest.fixture
def run_id() -> str:
    """Provide a standard test run ID."""
    return 'run_2026-01-12T04:00:00Z'


@pytest.fixture
def started_at_datetime() -> datetime:
    """Provide a standard test datetime for started_at."""
    return datetime(2026, 1, 12, 4, 0, 0, tzinfo=UTC)


@pytest.fixture
def completed_at_datetime() -> datetime:
    """Provide a standard test datetime for completed_at."""
    return datetime(2026, 1, 12, 5, 15, 0, tzinfo=UTC)


@pytest.fixture
def repo_created_at() -> datetime:
    """Provide a standard test datetime for repository created_at."""
    return datetime(2013, 5, 24, 16, 15, 54, tzinfo=UTC)


@pytest.fixture
def repo_name() -> str:
    """Provide a standard test repository name."""
    return 'owner/repo'


@pytest.fixture
def react_repo_name() -> str:
    """Provide the facebook/react repository name for tests."""
    return 'facebook/react'


@pytest.fixture
def head_commit() -> str:
    """Provide a standard test head commit SHA."""
    return 'abc123def456'


@pytest.fixture
def default_branch() -> str:
    """Provide a standard test default branch name."""
    return 'main'


# =============================================================================
# FACTORY FIXTURES
# =============================================================================


@pytest.fixture
def run_factory(
    run_id: str,
    started_at_datetime: datetime,
    default_config_metadata: dict[str, int],
) -> Callable[..., Run]:
    """Factory fixture that creates Run objects with sensible defaults.

    Returns a function that accepts kwargs to override defaults.

    Usage:
        def test_something(run_factory):
            run = run_factory(status=RunStatus.COMPLETED)

    Args:
        run_id: Standard run ID fixture
        started_at_datetime: Standard started_at datetime fixture
        default_config_metadata: Standard config metadata fixture

    Returns:
        Function that creates Run objects with defaults, overridden by kwargs
    """

    def _create_run(**kwargs: Any) -> Run:  # noqa: ANN401
        defaults: dict[str, Any] = {
            'run_id': run_id,
            'started_at': started_at_datetime,
            'status': RunStatus.RUNNING,
            'config_metadata': default_config_metadata,
        }
        defaults.update(kwargs)
        return Run(**defaults)

    return _create_run


@pytest.fixture
def repo_record_factory(  # noqa: PLR0913
    run_id: str,
    repo_name: str,
    default_branch: str,
    head_commit: str,
    started_at_datetime: datetime,
    repo_created_at: datetime,
) -> Callable[..., RepoRecord]:
    """Factory fixture that creates RepoRecord objects with sensible defaults.

    Returns a function that accepts kwargs to override defaults.

    Usage:
        def test_something(repo_record_factory):
            record = repo_record_factory(repo='custom/repo', stars=500)

    Args:
        run_id: Standard run ID fixture
        repo_name: Standard repository name fixture
        default_branch: Standard default branch fixture
        head_commit: Standard head commit SHA fixture
        started_at_datetime: Standard timestamp datetime fixture
        repo_created_at: Standard repository created_at datetime fixture

    Returns:
        Function that creates RepoRecord objects with defaults, overridden by kwargs
    """

    def _create_repo_record(**kwargs: Any) -> RepoRecord:  # noqa: ANN401
        defaults: dict[str, Any] = {
            'run_id': run_id,
            'repo': repo_name,
            'default_branch': default_branch,
            'head_commit': head_commit,
            'stars': 100,
            'created_at': repo_created_at,
            'timestamp': started_at_datetime,
            'commits_analyzed': 0,
        }
        defaults.update(kwargs)
        return RepoRecord(**defaults)

    return _create_repo_record


# =============================================================================
# ENVIRONMENT FIXTURES
# =============================================================================


@pytest.fixture
def github_token_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set GITHUB_TOKEN environment variable for tests.

    Uses pytest's monkeypatch fixture to set the environment variable.
    Automatically cleaned up after the test.

    Args:
        monkeypatch: Pytest's monkeypatch fixture
    """
    monkeypatch.setenv('GITHUB_TOKEN', 'test-token')
