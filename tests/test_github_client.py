"""Tests for the GitHub client module - HTTP client with rate limiting.

This module tests the GitHubClient class:
- Rate limit header parsing and proactive sleeping
- Exponential backoff with jitter for retries
- Pagination for search and commits endpoints

Tests use respx to mock HTTP responses.
"""

import time
from datetime import UTC, datetime

import httpx
import pytest
import respx

from conv_commit_stats.github_client import (
    GitHubClient,
    RateLimitExceeded,
    calculate_backoff_with_jitter,
)

# =============================================================================
# EXECUTABLE DOCUMENTATION - Read these first to understand the API
# =============================================================================


class TestGitHubClientBasics:
    """Basic examples showing how GitHubClient works."""

    @respx.mock
    def test_search_repositories(self) -> None:
        """Search for repositories using the GitHub Search API."""
        # Mock the search response
        respx.get('https://api.github.com/search/repositories').mock(
            return_value=httpx.Response(
                200,
                json={
                    'total_count': 1,
                    'incomplete_results': False,
                    'items': [
                        {
                            'id': 10270250,
                            'full_name': 'facebook/react',
                            'stargazers_count': 220000,
                            'default_branch': 'main',
                            'archived': False,
                            'fork': False,
                            'license': {'spdx_id': 'MIT'},
                            'pushed_at': '2026-01-12T10:30:00Z',
                            'created_at': '2013-05-24T16:15:54Z',
                            'language': 'JavaScript',
                        }
                    ],
                },
                headers={
                    'X-RateLimit-Remaining': '29',
                    'X-RateLimit-Reset': str(int(time.time()) + 60),
                },
            )
        )

        client = GitHubClient(token='test-token')
        repos = client.search_repositories(query='stars:>=100', per_page=10, page=1)

        assert len(repos) == 1
        assert repos[0]['full_name'] == 'facebook/react'

    @respx.mock
    def test_get_commits(self) -> None:
        """Get commits from a repository."""
        # Mock the commits response
        respx.get('https://api.github.com/repos/facebook/react/commits').mock(
            return_value=httpx.Response(
                200,
                json=[
                    {
                        'sha': 'abc123',
                        'commit': {
                            'message': 'feat: add new feature',
                            'author': {'date': '2026-01-12T10:30:00Z'},
                        },
                        'author': {'login': 'johndoe'},
                        'parents': [{'sha': 'parent1'}],
                    }
                ],
                headers={
                    'X-RateLimit-Remaining': '4999',
                    'X-RateLimit-Reset': str(int(time.time()) + 3600),
                },
            )
        )

        client = GitHubClient(token='test-token')
        commits = client.get_commits('facebook/react', per_page=100)

        assert len(commits) == 1
        assert commits[0]['sha'] == 'abc123'


class TestRateLimitHandling:
    """Test rate limit detection and handling."""

    @respx.mock
    def test_detects_low_rate_limit(self) -> None:
        """Client detects when rate limit is low."""
        reset_time = int(time.time()) + 60
        respx.get('https://api.github.com/search/repositories').mock(
            return_value=httpx.Response(
                200,
                json={'total_count': 0, 'items': []},
                headers={
                    'X-RateLimit-Remaining': '5',
                    'X-RateLimit-Reset': str(reset_time),
                },
            )
        )

        client = GitHubClient(token='test-token')
        client.search_repositories(query='test', per_page=10, page=1)

        # Should have recorded low rate limit
        assert client.rate_limit_remaining is not None
        assert client.rate_limit_remaining <= 10

    @respx.mock
    def test_raises_on_rate_limit_exceeded(self) -> None:
        """Client raises RateLimitExceeded on 403 with rate limit message."""
        reset_time = int(time.time()) + 60
        respx.get('https://api.github.com/search/repositories').mock(
            return_value=httpx.Response(
                403,
                json={
                    'message': 'API rate limit exceeded',
                    'documentation_url': 'https://docs.github.com/...',
                },
                headers={
                    'X-RateLimit-Remaining': '0',
                    'X-RateLimit-Reset': str(reset_time),
                },
            )
        )

        client = GitHubClient(token='test-token')
        with pytest.raises(RateLimitExceeded) as exc_info:
            client.search_repositories(query='test', per_page=10, page=1)

        assert exc_info.value.reset_at is not None


# =============================================================================
# COMPREHENSIVE TESTS
# =============================================================================


class TestBackoffCalculation:
    """Test exponential backoff with jitter."""

    def test_backoff_increases_exponentially(self) -> None:
        """Backoff should increase exponentially with retry count."""
        backoff_1 = calculate_backoff_with_jitter(attempt=1, base=1.0)
        backoff_2 = calculate_backoff_with_jitter(attempt=2, base=1.0)
        backoff_3 = calculate_backoff_with_jitter(attempt=3, base=1.0)

        # Base delays: 1, 2, 4 seconds (exponential)
        # With jitter, actual values will vary
        assert backoff_1 < backoff_2 < backoff_3

    def test_backoff_has_jitter(self) -> None:
        """Backoff should include random jitter."""
        # Call multiple times, should get different values
        results = [
            calculate_backoff_with_jitter(attempt=2, base=1.0) for _ in range(10)
        ]
        # Not all should be exactly the same
        assert len(set(results)) > 1

    def test_backoff_respects_max_delay(self) -> None:
        """Backoff should not exceed max delay."""
        backoff = calculate_backoff_with_jitter(attempt=10, base=1.0, max_delay=60.0)
        assert backoff <= 60.0


class TestSearchPagination:
    """Test search API pagination with star-range bucketing."""

    @respx.mock
    def test_pagination_params_passed(self) -> None:
        """Pagination parameters should be passed to the API."""
        route = respx.get('https://api.github.com/search/repositories').mock(
            return_value=httpx.Response(
                200,
                json={'total_count': 0, 'items': []},
                headers={
                    'X-RateLimit-Remaining': '29',
                    'X-RateLimit-Reset': str(int(time.time()) + 60),
                },
            )
        )

        client = GitHubClient(token='test-token')
        client.search_repositories(query='stars:100..500', per_page=30, page=2)

        # Verify the request parameters
        assert route.called
        request = route.calls.last.request
        url_str = str(request.url)
        assert 'per_page=30' in url_str
        assert 'page=2' in url_str
        # URL encodes : as %3A
        assert 'stars' in url_str
        assert '100..500' in url_str


class TestCommitsFetching:
    """Test commits API with filtering."""

    @respx.mock
    def test_commits_with_since_filter(self) -> None:
        """Commits should be filtered by since date."""
        route = respx.get('https://api.github.com/repos/owner/repo/commits').mock(
            return_value=httpx.Response(
                200,
                json=[],
                headers={
                    'X-RateLimit-Remaining': '4999',
                    'X-RateLimit-Reset': str(int(time.time()) + 3600),
                },
            )
        )

        client = GitHubClient(token='test-token')
        since = datetime(2025, 1, 1, tzinfo=UTC)
        client.get_commits('owner/repo', since=since, per_page=100)

        assert route.called
        request = route.calls.last.request
        assert 'since=' in str(request.url)

    @respx.mock
    def test_commits_excludes_merge_commits(self) -> None:
        """Merge commits should be identifiable by parents count."""
        respx.get('https://api.github.com/repos/owner/repo/commits').mock(
            return_value=httpx.Response(
                200,
                json=[
                    {
                        'sha': 'regular',
                        'commit': {'message': 'feat: add feature'},
                        'parents': [{'sha': 'p1'}],
                    },
                    {
                        'sha': 'merge',
                        'commit': {'message': "Merge branch 'feature'"},
                        'parents': [{'sha': 'p1'}, {'sha': 'p2'}],  # 2 parents
                    },
                ],
                headers={
                    'X-RateLimit-Remaining': '4999',
                    'X-RateLimit-Reset': str(int(time.time()) + 3600),
                },
            )
        )

        client = GitHubClient(token='test-token')
        commits = client.get_commits('owner/repo', per_page=100)

        # Both returned, caller filters merge commits
        assert len(commits) == 2
        # Regular commit has 1 parent
        assert len(commits[0]['parents']) == 1
        # Merge commit has 2 parents
        assert len(commits[1]['parents']) == 2


class TestClientConfiguration:
    """Test client configuration and headers."""

    @respx.mock
    def test_auth_header_sent(self) -> None:
        """Authorization header should be sent with token."""
        route = respx.get('https://api.github.com/search/repositories').mock(
            return_value=httpx.Response(
                200,
                json={'total_count': 0, 'items': []},
                headers={
                    'X-RateLimit-Remaining': '29',
                    'X-RateLimit-Reset': str(int(time.time()) + 60),
                },
            )
        )

        client = GitHubClient(token='test-token-123')
        client.search_repositories(query='test', per_page=10, page=1)

        request = route.calls.last.request
        assert request.headers.get('authorization') == 'Bearer test-token-123'

    @respx.mock
    def test_accept_header_sent(self) -> None:
        """Accept header should request JSON."""
        route = respx.get('https://api.github.com/search/repositories').mock(
            return_value=httpx.Response(
                200,
                json={'total_count': 0, 'items': []},
                headers={
                    'X-RateLimit-Remaining': '29',
                    'X-RateLimit-Reset': str(int(time.time()) + 60),
                },
            )
        )

        client = GitHubClient(token='test-token')
        client.search_repositories(query='test', per_page=10, page=1)

        request = route.calls.last.request
        assert 'application/vnd.github' in request.headers.get('accept', '')


class TestRepoMetadataFetching:
    """Test repository metadata fetching."""

    @respx.mock
    def test_get_repository(self) -> None:
        """Fetch single repository metadata."""
        respx.get('https://api.github.com/repos/facebook/react').mock(
            return_value=httpx.Response(
                200,
                json={
                    'id': 10270250,
                    'full_name': 'facebook/react',
                    'default_branch': 'main',
                    'stargazers_count': 220000,
                    'language': 'JavaScript',
                    'created_at': '2013-05-24T16:15:54Z',
                    'license': {'spdx_id': 'MIT'},
                },
                headers={
                    'X-RateLimit-Remaining': '4999',
                    'X-RateLimit-Reset': str(int(time.time()) + 3600),
                },
            )
        )

        client = GitHubClient(token='test-token')
        repo = client.get_repository('facebook/react')

        assert repo['full_name'] == 'facebook/react'
        assert repo['default_branch'] == 'main'


class TestErrorHandling:
    """Test error handling for various HTTP responses."""

    @respx.mock
    def test_handles_404(self) -> None:
        """404 should raise appropriate error."""
        respx.get('https://api.github.com/repos/nonexistent/repo').mock(
            return_value=httpx.Response(
                404,
                json={'message': 'Not Found'},
                headers={
                    'X-RateLimit-Remaining': '4999',
                    'X-RateLimit-Reset': str(int(time.time()) + 3600),
                },
            )
        )

        client = GitHubClient(token='test-token')
        with pytest.raises(httpx.HTTPStatusError):
            client.get_repository('nonexistent/repo')

    @respx.mock
    def test_handles_network_error(self) -> None:
        """Network errors should propagate."""
        respx.get('https://api.github.com/repos/owner/repo').mock(
            side_effect=httpx.ConnectError('Connection failed')
        )

        client = GitHubClient(token='test-token')
        with pytest.raises(httpx.ConnectError):
            client.get_repository('owner/repo')


class TestRateLimitParsing:
    """Test rate limit header parsing."""

    @respx.mock
    def test_parses_rate_limit_headers(self) -> None:
        """Rate limit headers should be parsed from responses."""
        reset_time = int(time.time()) + 3600
        respx.get('https://api.github.com/repos/owner/repo').mock(
            return_value=httpx.Response(
                200,
                json={'id': 1},
                headers={
                    'X-RateLimit-Remaining': '4567',
                    'X-RateLimit-Reset': str(reset_time),
                    'X-RateLimit-Limit': '5000',
                },
            )
        )

        client = GitHubClient(token='test-token')
        client.get_repository('owner/repo')

        assert client.rate_limit_remaining == 4567
        assert client.rate_limit_reset_at is not None

    @respx.mock
    def test_handles_missing_rate_limit_headers(self) -> None:
        """Should handle responses without rate limit headers."""
        respx.get('https://api.github.com/repos/owner/repo').mock(
            return_value=httpx.Response(200, json={'id': 1})
        )

        client = GitHubClient(token='test-token')
        # Should not raise
        client.get_repository('owner/repo')


class TestContextManager:
    """Test GitHubClient as context manager."""

    @respx.mock
    def test_context_manager_closes_client(self) -> None:
        """Context manager should close the httpx client."""
        respx.get('https://api.github.com/repos/owner/repo').mock(
            return_value=httpx.Response(
                200,
                json={'id': 1},
                headers={
                    'X-RateLimit-Remaining': '4999',
                    'X-RateLimit-Reset': str(int(time.time()) + 3600),
                },
            )
        )

        with GitHubClient(token='test-token') as client:
            client.get_repository('owner/repo')
            # Client should work inside context

        # Client closed after context
        assert client._client.is_closed
