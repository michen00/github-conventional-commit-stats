"""Tests for the parsing module - commit type extraction and bot detection.

This module tests the pure functions in conv_commit_stats.parsing:
- is_conventional_commit()
- parse_commit_type()
- is_bot()

Tests are organized as:
1. Executable Documentation (above the fold) - DAMP style
2. Coverage tests - comprehensive parametrized tests
"""

import pytest

from conv_commit_stats.parsing import (
    CommitType,
    is_bot,
    is_conventional_commit,
    parse_commit_type,
)


# =============================================================================
# EXECUTABLE DOCUMENTATION - Read these first to understand the API
# =============================================================================


class TestConventionalCommitBasics:
    """Basic examples showing how conventional commit parsing works."""

    def test_simple_feat_commit(self) -> None:
        """A basic feature commit follows the pattern: type: description."""
        message = "feat: add user authentication"

        assert is_conventional_commit(message) is True
        assert parse_commit_type(message) == CommitType.FEAT

    def test_commit_with_scope(self) -> None:
        """Commits can have an optional scope in parentheses."""
        message = "fix(auth): resolve token expiry bug"

        assert is_conventional_commit(message) is True
        assert parse_commit_type(message) == CommitType.FIX

    def test_breaking_change_indicator(self) -> None:
        """Breaking changes are indicated with ! before the colon."""
        message = "feat!: remove deprecated API endpoints"

        assert is_conventional_commit(message) is True
        assert parse_commit_type(message) == CommitType.FEAT

    def test_non_conventional_commit(self) -> None:
        """Non-conventional commits return None for type extraction."""
        message = "Update README with new instructions"

        assert is_conventional_commit(message) is False
        assert parse_commit_type(message) is None

    def test_merge_commit_is_not_conventional(self) -> None:
        """Merge commits should not be treated as conventional commits."""
        message = "Merge branch 'feature' into main"

        assert is_conventional_commit(message) is False


class TestBotDetectionBasics:
    """Basic examples showing how bot detection works."""

    def test_dependabot_is_detected(self) -> None:
        """Dependabot should be detected as a bot."""
        assert is_bot("dependabot[bot]") is True

    def test_renovate_is_detected(self) -> None:
        """Renovate bot should be detected."""
        assert is_bot("renovate[bot]") is True

    def test_human_developer(self) -> None:
        """Regular developer names should not be detected as bots."""
        assert is_bot("john-doe") is False


# =============================================================================
# COMPREHENSIVE COVERAGE TESTS
# =============================================================================


class TestAllCommitTypes:
    """Test that all 11 conventional commit types are recognized."""

    @pytest.mark.parametrize(
        ("message", "expected_type"),
        [
            ("build: update webpack config", CommitType.BUILD),
            ("chore: clean up unused files", CommitType.CHORE),
            ("ci: add GitHub Actions workflow", CommitType.CI),
            ("docs: update API documentation", CommitType.DOCS),
            ("feat: add new feature", CommitType.FEAT),
            ("fix: resolve null pointer exception", CommitType.FIX),
            ("perf: improve query performance", CommitType.PERF),
            ("refactor: simplify authentication logic", CommitType.REFACTOR),
            ("revert: revert previous commit", CommitType.REVERT),
            ("style: format code with prettier", CommitType.STYLE),
            ("test: add unit tests for parser", CommitType.TEST),
        ],
    )
    def test_commit_type_extraction(
        self, message: str, expected_type: CommitType
    ) -> None:
        """Each conventional commit type should be correctly extracted."""
        assert is_conventional_commit(message) is True
        assert parse_commit_type(message) == expected_type


class TestCommitTypeWithScopes:
    """Test commit types with various scope formats."""

    @pytest.mark.parametrize(
        "message",
        [
            "feat(api): add new endpoint",
            "fix(ui): correct button alignment",
            "docs(readme): update installation steps",
            "refactor(auth): simplify token handling",
            "test(integration): add e2e tests",
        ],
    )
    def test_scoped_commits_are_valid(self, message: str) -> None:
        """Commits with scopes should be recognized as conventional."""
        assert is_conventional_commit(message) is True

    @pytest.mark.parametrize(
        ("message", "expected_type"),
        [
            ("feat(api): add endpoint", CommitType.FEAT),
            ("fix(ui-components): fix alignment", CommitType.FIX),
            ("docs(getting-started): add guide", CommitType.DOCS),
        ],
    )
    def test_scope_does_not_affect_type(
        self, message: str, expected_type: CommitType
    ) -> None:
        """The scope should not affect the extracted type."""
        assert parse_commit_type(message) == expected_type


class TestBreakingChanges:
    """Test breaking change indicator handling."""

    @pytest.mark.parametrize(
        ("message", "expected_type"),
        [
            ("feat!: breaking feature change", CommitType.FEAT),
            ("fix!: breaking fix", CommitType.FIX),
            ("refactor!: breaking refactor", CommitType.REFACTOR),
            ("feat(api)!: breaking API change", CommitType.FEAT),
        ],
    )
    def test_breaking_change_commits(
        self, message: str, expected_type: CommitType
    ) -> None:
        """Breaking change indicator (!) should be handled correctly."""
        assert is_conventional_commit(message) is True
        assert parse_commit_type(message) == expected_type


class TestInvalidCommitFormats:
    """Test that invalid formats are rejected."""

    @pytest.mark.parametrize(
        "message",
        [
            "Update README",  # No type prefix
            "Fix bug",  # Capitalized, no colon
            "WIP",  # Work in progress
            "initial commit",  # Common but not conventional
            "v1.0.0",  # Version tag
            "",  # Empty
            "   ",  # Whitespace only
            "FEAT: uppercase type",  # Must be lowercase
            "feat:missing space",  # Space after colon required
            "Feat: capitalized type",  # Must be lowercase
            "feature: wrong type name",  # 'feature' is not valid
            "feat - wrong separator",  # Must use colon
            "feat() empty scope",  # Empty scope is invalid
        ],
    )
    def test_invalid_commits_rejected(self, message: str) -> None:
        """Invalid commit formats should not be recognized as conventional."""
        assert is_conventional_commit(message) is False
        assert parse_commit_type(message) is None


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_multiline_commit_uses_first_line(self) -> None:
        """Only the first line of a multiline commit should be parsed."""
        message = "feat: add new feature\n\nThis is the body of the commit."
        assert is_conventional_commit(message) is True
        assert parse_commit_type(message) == CommitType.FEAT

    def test_commit_with_special_characters_in_description(self) -> None:
        """Special characters in description should be allowed."""
        message = "fix: resolve bug in `parse_commit_type()` function"
        assert is_conventional_commit(message) is True

    def test_commit_with_unicode_in_description(self) -> None:
        """Unicode characters in description should be allowed."""
        message = "docs: update README with emoji 🚀"
        assert is_conventional_commit(message) is True

    def test_long_scope(self) -> None:
        """Long scopes should be accepted."""
        message = "feat(very-long-module-name-here): add feature"
        assert is_conventional_commit(message) is True

    def test_scope_with_numbers(self) -> None:
        """Scopes can contain numbers."""
        message = "fix(issue-123): resolve reported bug"
        assert is_conventional_commit(message) is True


class TestBotDetectionPatterns:
    """Test bot detection against known bot patterns."""

    @pytest.mark.parametrize(
        "author",
        [
            "dependabot[bot]",
            "renovate[bot]",
            "github-actions[bot]",
            "pre-commit-ci[bot]",
            "semantic-release-bot",
            "snyk-bot",
            "greenkeeper[bot]",
            "imgbot[bot]",
            "allcontributors[bot]",
            "mergify[bot]",
            "codecov[bot]",
            "depfu[bot]",
            "whitesource-bolt-for-github[bot]",
            "mend-bolt-for-github[bot]",
            "restyled-io[bot]",
            "github-learning-lab[bot]",
            "release-please[bot]",
        ],
    )
    def test_known_bots_detected(self, author: str) -> None:
        """Known bot patterns should be detected."""
        assert is_bot(author) is True

    @pytest.mark.parametrize(
        "author",
        [
            "john-doe",
            "jane_smith",
            "developer123",
            "alice.wonderland",
            "bob",
        ],
    )
    def test_human_authors_not_detected(self, author: str) -> None:
        """Human author names should not be detected as bots."""
        assert is_bot(author) is False

    def test_case_insensitive_bot_detection(self) -> None:
        """Bot detection should be case-insensitive."""
        assert is_bot("Dependabot[bot]") is True
        assert is_bot("DEPENDABOT[BOT]") is True
        assert is_bot("DePeNdAbOt[BoT]") is True

    def test_partial_bot_name_in_human(self) -> None:
        """Names containing 'bot' as part of a word should not match."""
        # These are edge cases - humans with 'bot' in their name
        assert is_bot("robotics-fan") is False
        assert is_bot("the-bot-whisperer") is False


class TestCommitTypeEnum:
    """Test the CommitType enum."""

    def test_all_types_are_lowercase(self) -> None:
        """All commit type values should be lowercase."""
        for commit_type in CommitType:
            assert commit_type.value == commit_type.value.lower()

    def test_enum_has_11_types(self) -> None:
        """There should be exactly 11 conventional commit types."""
        assert len(CommitType) == 11

    def test_enum_values_match_names(self) -> None:
        """Enum values should match their lowercase names."""
        for commit_type in CommitType:
            assert commit_type.value == commit_type.name.lower()


# =============================================================================
# FIXTURE-BASED TESTS
# =============================================================================


class TestWithFixtures:
    """Tests using conftest.py fixtures for comprehensive coverage."""

    def test_all_sample_messages_are_valid(
        self, sample_commit_messages: dict[str, list[str]]
    ) -> None:
        """All sample commit messages should be recognized as conventional."""
        for commit_type, messages in sample_commit_messages.items():
            for message in messages:
                assert is_conventional_commit(message) is True, (
                    f"Expected valid: {message}"
                )
                parsed_type = parse_commit_type(message)
                assert parsed_type is not None
                assert parsed_type.value == commit_type

    def test_all_invalid_messages_rejected(
        self, invalid_commit_messages: list[str]
    ) -> None:
        """All invalid commit messages should be rejected."""
        for message in invalid_commit_messages:
            assert is_conventional_commit(message) is False, (
                f"Expected invalid: {message}"
            )

    def test_all_bot_authors_detected(self, bot_authors: list[str]) -> None:
        """All bot author fixtures should be detected."""
        for author in bot_authors:
            assert is_bot(author) is True, f"Expected bot: {author}"

    def test_all_human_authors_not_detected(
        self, human_authors: list[str]
    ) -> None:
        """All human author fixtures should not be detected as bots."""
        for author in human_authors:
            assert is_bot(author) is False, f"Expected human: {author}"
