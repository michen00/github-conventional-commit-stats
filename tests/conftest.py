"""Shared pytest fixtures for conv_commit_stats tests.

Provides:
- tmp_db_path: Temporary directory for TinyDB storage tests
- mock_github_responses: Pre-configured respx mocks for GitHub API
- sample_commit_messages: Test data for parsing tests
"""

from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest

from conv_commit_stats.storage import Storage


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
