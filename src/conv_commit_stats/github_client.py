"""HTTP client for GitHub API with rate limiting and retry logic.

This module handles:
- Rate limit header parsing and proactive sleeping
- Exponential backoff with jitter for retries
- Pagination for search and commits endpoints

The client respects GitHub API rate limits:
- Search API: 30 requests/minute
- Core API (PAT): 5000 requests/hour
- Core API (GITHUB_TOKEN): 1000 requests/hour
"""

import random
from datetime import UTC, datetime
from typing import Any

import httpx

__all__ = (
    'GitHubClient',
    'RateLimitExceeded',
    'calculate_backoff_with_jitter',
)


class RateLimitExceeded(Exception):
    """Raised when GitHub API rate limit is exceeded."""

    def __init__(
        self,
        message: str,
        reset_at: datetime | None = None,
        remaining: int = 0,
    ) -> None:
        super().__init__(message)
        self.reset_at = reset_at
        self.remaining = remaining


def calculate_backoff_with_jitter(
    attempt: int,
    base: float = 1.0,
    max_delay: float = 60.0,
) -> float:
    """Calculate exponential backoff with random jitter.

    Args:
        attempt: The current retry attempt number (1-indexed)
        base: Base delay in seconds
        max_delay: Maximum delay cap in seconds

    Returns:
        Delay in seconds with jitter applied
    """
    # Exponential backoff: base * 2^(attempt-1)
    delay = base * (2 ** (attempt - 1))

    # Add random jitter (±25%)
    jitter = delay * 0.25 * (2 * random.random() - 1)
    delay = delay + jitter

    # Cap at max_delay
    return min(delay, max_delay)


class GitHubClient:
    """GitHub API client with rate limiting.

    Provides methods for searching repositories, fetching commits,
    and getting repository metadata. Automatically tracks rate limit
    headers and can be configured for proactive sleeping.

    Can be used as a context manager:
        with GitHubClient(token="...") as client:
            repos = client.search_repositories(query="...")
    """

    BASE_URL = 'https://api.github.com'

    def __init__(
        self,
        token: str,
        timeout: float = 30.0,
        rate_limit_threshold: int = 10,
    ) -> None:
        """Initialize the GitHub client.

        Args:
            token: GitHub personal access token or GITHUB_TOKEN
            timeout: Request timeout in seconds
            rate_limit_threshold: Remaining requests threshold for warnings
        """
        self._token = token
        self._timeout = timeout
        self._rate_limit_threshold = rate_limit_threshold

        # Rate limit tracking
        self.rate_limit_remaining: int | None = None
        self.rate_limit_reset_at: datetime | None = None

        # Initialize httpx client
        self._client = httpx.Client(
            base_url=self.BASE_URL,
            headers={
                'Accept': 'application/vnd.github+json',
                'Authorization': f'Bearer {token}',
                'X-GitHub-Api-Version': '2022-11-28',
            },
            timeout=timeout,
        )

    def __enter__(self) -> 'GitHubClient':
        """Enter context manager."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        """Exit context manager, closing the client."""
        self.close()

    def close(self) -> None:
        """Close the httpx client."""
        self._client.close()

    def _update_rate_limits(self, response: httpx.Response) -> None:
        """Update rate limit tracking from response headers."""
        remaining = response.headers.get('X-RateLimit-Remaining')
        reset_time = response.headers.get('X-RateLimit-Reset')

        if remaining is not None:
            self.rate_limit_remaining = int(remaining)

        if reset_time is not None:
            self.rate_limit_reset_at = datetime.fromtimestamp(int(reset_time), tz=UTC)

    def _check_rate_limit_response(self, response: httpx.Response) -> None:
        """Check for rate limit errors in response."""
        if response.status_code == 403:
            try:
                data = response.json()
                if 'rate limit' in data.get('message', '').lower():
                    raise RateLimitExceeded(
                        message=data.get('message', 'Rate limit exceeded'),
                        reset_at=self.rate_limit_reset_at,
                        remaining=self.rate_limit_remaining or 0,
                    )
            except (ValueError, KeyError):
                pass

        # Raise for other HTTP errors
        response.raise_for_status()

    def _request(
        self,
        method: str,
        url: str,
        params: dict[str, Any] | None = None,
    ) -> httpx.Response:
        """Make an HTTP request and update rate limits.

        Args:
            method: HTTP method (GET, POST, etc.)
            url: URL path (relative to BASE_URL)
            params: Query parameters

        Returns:
            The HTTP response

        Raises:
            RateLimitExceeded: If rate limit is exceeded
            httpx.HTTPStatusError: For other HTTP errors
        """
        response = self._client.request(method, url, params=params)
        self._update_rate_limits(response)
        self._check_rate_limit_response(response)
        return response

    def search_repositories(
        self,
        query: str,
        per_page: int = 30,
        page: int = 1,
    ) -> list[dict[str, Any]]:
        """Search for repositories using GitHub Search API.

        Args:
            query: Search query (e.g., "stars:>=100 pushed:>2025-01-01")
            per_page: Results per page (max 100)
            page: Page number (1-indexed)

        Returns:
            List of repository objects from the API

        Raises:
            RateLimitExceeded: If search rate limit is exceeded
        """
        response = self._request(
            'GET',
            '/search/repositories',
            params={
                'q': query,
                'per_page': per_page,
                'page': page,
                'sort': 'stars',
                'order': 'desc',
            },
        )

        data = response.json()
        return data.get('items', [])

    def get_repository(self, repo: str) -> dict[str, Any]:
        """Get repository metadata.

        Args:
            repo: Repository full name (owner/repo)

        Returns:
            Repository object from the API

        Raises:
            httpx.HTTPStatusError: If repository not found
        """
        response = self._request('GET', f'/repos/{repo}')
        return response.json()

    def get_commits(
        self,
        repo: str,
        sha: str | None = None,
        since: datetime | None = None,
        per_page: int = 100,
    ) -> list[dict[str, Any]]:
        """Get commits from a repository.

        Args:
            repo: Repository full name (owner/repo)
            sha: Branch name or commit SHA to start from
            since: Only commits after this date
            per_page: Commits per page (max 100)

        Returns:
            List of commit objects from the API
        """
        params: dict[str, Any] = {'per_page': per_page}

        if sha:
            params['sha'] = sha

        if since:
            params['since'] = since.isoformat()

        response = self._request('GET', f'/repos/{repo}/commits', params=params)
        return response.json()

    def should_sleep_for_rate_limit(self) -> bool:
        """Check if we should sleep due to low rate limit.

        Returns:
            True if remaining requests are below threshold
        """
        if self.rate_limit_remaining is None:
            return False
        return self.rate_limit_remaining < self._rate_limit_threshold

    def get_sleep_duration(self) -> float:
        """Calculate how long to sleep until rate limit resets.

        Returns:
            Seconds to sleep, or 0 if no sleep needed
        """
        if self.rate_limit_reset_at is None:
            return 0.0

        now = datetime.now(UTC)
        if self.rate_limit_reset_at <= now:
            return 0.0

        return (self.rate_limit_reset_at - now).total_seconds()
