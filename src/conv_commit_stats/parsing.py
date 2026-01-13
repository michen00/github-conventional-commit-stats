"""Pure functions for parsing conventional commits and detecting bots.

This module contains stateless functions with no side effects:
- is_conventional_commit(message) -> bool
- extract_type(message) -> str | None
- is_bot(author) -> bool

See §1.3 and §1.4 of the spec for patterns and test cases.
"""

__all__ = (
    "is_conventional_commit",
    "extract_type",
    "is_bot",
)


def is_conventional_commit(message: str) -> bool:
    """Check if a commit message follows conventional commit format."""
    raise NotImplementedError


def extract_type(message: str) -> str | None:
    """Extract the commit type (feat, fix, etc.) from a conventional commit."""
    raise NotImplementedError


def is_bot(author: str) -> bool:
    """Check if an author name/login matches known bot patterns."""
    raise NotImplementedError
