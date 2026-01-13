"""Orchestration layer for collecting conventional commit statistics.

This module coordinates:
- Repository discovery via GitHub Search API
- Commit fetching and filtering
- Progress checkpointing for resume
- Graceful signal handling (SIGINT/SIGTERM)

See §1 of the spec for collection logic.
"""

__all__ = ("Collector",)


class Collector:
    """Orchestrates the collection of conventional commit statistics."""

    raise NotImplementedError
