"""HTTP client for GitHub API with rate limiting and retry logic.

This module handles:
- Rate limit header parsing and proactive sleeping
- Exponential backoff with jitter for retries
- Pagination for search and commits endpoints

See §2 of the spec for rate limit handling.
"""

__all__ = ('GitHubClient',)


class GitHubClient:
    """GitHub API client with rate limiting."""

    raise NotImplementedError
