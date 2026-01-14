"""Pure functions for parsing conventional commits and detecting bots.

This module contains stateless functions with no side effects:
- is_conventional_commit(message) -> bool
- parse_commit_type(message) -> CommitType | None
- is_bot(author) -> bool

The conventional commit format follows the specification at:
https://www.conventionalcommits.org/

Pattern: type(scope)!: description
- type: One of the 11 allowed types (lowercase)
- scope: Optional, in parentheses
- !: Optional breaking change indicator
- description: Required, after colon and space
"""

import re
from enum import StrEnum, auto

__all__ = (
    'BOT_PATTERNS',
    'CONVENTIONAL_COMMIT_PATTERN',
    'CommitType',
    'is_bot',
    'is_conventional_commit',
    'parse_commit_type',
)


class CommitType(StrEnum):
    """Enumeration of the 11 conventional commit types."""

    BUILD = auto()
    CHORE = auto()
    CI = auto()
    DOCS = auto()
    FEAT = auto()
    FIX = auto()
    PERF = auto()
    REFACTOR = auto()
    REVERT = auto()
    STYLE = auto()
    TEST = auto()


# Regex pattern for conventional commits
# - Type must be lowercase and one of the 11 allowed types
# - Scope is optional, in parentheses (no nested parens)
# - Breaking change indicator (!) is optional
# - Colon followed by space and description is required
CONVENTIONAL_COMMIT_PATTERN = re.compile(
    r'^(build|chore|ci|docs|feat|fix|perf|refactor|revert|style|test)'
    r'(\([^)]+\))?'  # Optional scope (non-empty)
    r'!?'  # Optional breaking change indicator
    r': '  # Colon followed by space
    r'.+'  # Description (at least one character)
    r'$',
    re.MULTILINE,
)

# Type extraction pattern (just captures the type)
TYPE_EXTRACTION_PATTERN = re.compile(
    r'^(build|chore|ci|docs|feat|fix|perf|refactor|revert|style|test)'
    r'(?:\([^)]+\))?'
    r'!?'
    r': ',
)

# Bot detection patterns (case-insensitive)
# These patterns match known bot usernames and service accounts
BOT_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r'\[bot\]', re.IGNORECASE),  # Contains [bot] anywhere
    re.compile(r'^dependabot', re.IGNORECASE),  # dependabot
    re.compile(r'^renovate', re.IGNORECASE),  # renovate
    re.compile(r'^github-actions', re.IGNORECASE),  # github-actions
    re.compile(r'^pre-commit-ci', re.IGNORECASE),  # pre-commit-ci
    re.compile(r'^semantic-release', re.IGNORECASE),  # semantic-release
    re.compile(r'^snyk-', re.IGNORECASE),  # snyk-bot
    re.compile(r'^greenkeeper', re.IGNORECASE),  # greenkeeper
    re.compile(r'^imgbot', re.IGNORECASE),  # imgbot
    re.compile(r'^allcontributors', re.IGNORECASE),  # allcontributors
    re.compile(r'^mergify', re.IGNORECASE),  # mergify
    re.compile(r'^codecov', re.IGNORECASE),  # codecov
    re.compile(r'^depfu', re.IGNORECASE),  # depfu
    re.compile(r'^whitesource-bolt', re.IGNORECASE),  # whitesource
    re.compile(r'^mend-bolt', re.IGNORECASE),  # mend (formerly whitesource)
    re.compile(r'^restyled-io', re.IGNORECASE),  # restyled
    re.compile(r'^github-learning-lab', re.IGNORECASE),  # learning lab
    re.compile(r'^release-please', re.IGNORECASE),  # release-please
)


def is_conventional_commit(message: str) -> bool:
    """Check if a commit message follows conventional commit format.

    The message must:
    - Start with a valid type (build, chore, ci, docs, feat, fix, perf,
      refactor, revert, style, test)
    - Optionally have a scope in parentheses
    - Optionally have a breaking change indicator (!)
    - Have a colon followed by a space
    - Have a non-empty description

    Only the first line of the message is checked.
    """
    if not message or not message.strip():
        return False

    # Only check the first line for multiline messages
    first_line = message.split('\n')[0]

    return CONVENTIONAL_COMMIT_PATTERN.match(first_line) is not None


def parse_commit_type(message: str) -> CommitType | None:
    """Extract the commit type from a conventional commit message.

    Returns the CommitType enum value if the message is a valid conventional
    commit, or None if it's not.

    Only the first line of the message is parsed.
    """
    if not message or not message.strip():
        return None

    # Only check the first line for multiline messages
    first_line = message.split('\n')[0]

    match = TYPE_EXTRACTION_PATTERN.match(first_line)
    if match is None:
        return None

    type_str = match.group(1)
    try:
        return CommitType(type_str)
    except ValueError:
        return None


def is_bot(author: str) -> bool:
    """Check if an author name/login matches known bot patterns.

    Detection is case-insensitive and matches against a curated list
    of known bot patterns including:
    - dependabot, renovate, github-actions
    - pre-commit-ci, semantic-release
    - Various security and utility bots

    Names containing '[bot]' anywhere are always detected as bots.
    """
    if not author:
        return False

    return any(pattern.search(author) for pattern in BOT_PATTERNS)
