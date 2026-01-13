"""TinyDB storage layer for runs, repos, and progress tracking.

This module wraps TinyDB with typed access to three tables:
- runs: Run metadata (start/end times, status, counts)
- repos: Per-repo commit type counts
- progress: Resume checkpoints

See §3 of the spec for schemas.
"""

__all__ = ("Storage",)


class Storage:
    """TinyDB wrapper for conventional commit census data."""

    raise NotImplementedError
