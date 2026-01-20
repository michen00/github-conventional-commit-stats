"""Orchestration layer for collecting conventional commit statistics.

This module coordinates:
- Repository discovery via GitHub Search API
- Commit fetching and filtering
- Progress checkpointing for resume
- Graceful signal handling (SIGINT/SIGTERM)
"""

import signal
import sys
from datetime import UTC, datetime, timedelta
from typing import Any, ClassVar, cast

import structlog

from conv_commit_stats.github_client import GitHubClient, RateLimitExceededError
from conv_commit_stats.parsing import (
    CommitType,
    is_bot,
    is_conventional_commit,
    parse_breaking,
    parse_commit_type,
    parse_has_scope,
)
from conv_commit_stats.storage import (
    RepoRecord,
    Run,
    RunStatus,
    SearchCursor,
    Storage,
)

logger = structlog.get_logger(__name__)

__all__ = ('Collector',)


class Collector:
    """Orchestrates the collection of conventional commit statistics.

    Coordinates repository discovery, commit fetching, parsing, and storage.
    Supports resumability through checkpointing and graceful signal handling.
    """

    # Star ranges for search pagination (bypasses 1000-result limit)
    STAR_RANGES: ClassVar[list[str]] = [
        'stars:10000..*',
        'stars:5000..10000',
        'stars:1000..5000',
        'stars:500..1000',
        'stars:100..500',
        'stars:3..100',
    ]

    def __init__(  # noqa: PLR0913
        self,
        storage: Storage,
        github_client: GitHubClient,
        max_repos: int = 1000,
        min_stars: int = 3,
        max_commits_per_repo: int = 100,
        time_window_days: int = 365,
    ) -> None:
        """Initialize the collector.

        Args:
            storage: Storage instance for persisting data
            github_client: GitHubClient for API access
            max_repos: Maximum repositories to process
            min_stars: Minimum star count filter
            max_commits_per_repo: Maximum commits to analyze per repo
            time_window_days: Days of commit history to analyze
        """
        self._storage = storage
        self._github_client = github_client
        self.max_repos = max_repos
        self.min_stars = min_stars
        self.max_commits_per_repo = max_commits_per_repo
        self.time_window_days = time_window_days

        self._interrupted = False
        self._current_run_id: str | None = None

        # Register signal handlers only if not in test environment
        # (pytest sets SIGINT handler, so we check if it's already set)
        if signal.getsignal(signal.SIGINT) != signal.SIG_DFL:
            # In test environment, don't override signal handlers
            pass
        else:
            signal.signal(signal.SIGINT, lambda s, f: self._handle_signal(s, f))
            signal.signal(signal.SIGTERM, lambda s, _f: self._handle_signal(s, _f))

    def _handle_signal(self, signum: int, frame: object) -> None:  # noqa: ARG002
        """Handle SIGINT/SIGTERM gracefully.

        Sets interruption flag so the collector can finish current repo
        and save progress before exiting.
        """
        logger.info('Received signal', signal=signum)
        self._interrupted = True

    def start_collection(self) -> str:
        """Start a new collection run.

        Returns:
            Run ID for the new collection

        Raises:
            RuntimeError: If another run is already in progress
        """
        # Check for concurrent runs
        # Note: This check is not atomic with the save operation below. In theory,
        # two processes could both pass this check and create duplicate runs.
        # However, this is acceptable for single-machine use (the typical case).
        # True atomicity would require file locking or database-level constraints.
        running_run = self._storage.get_running_run()
        if running_run is not None:
            msg = (
                f'Another collection is in progress ({running_run.run_id}). '
                'Use --resume to continue or wait for it to complete.'
            )
            raise RuntimeError(msg)

        # Create new run with config metadata
        run_id = f'run_{datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")}'
        config_metadata = {
            'max_repos': self.max_repos,
            'min_stars': self.min_stars,
            'max_commits_per_repo': self.max_commits_per_repo,
            'time_window_days': self.time_window_days,
        }
        run = Run(
            run_id=run_id,
            started_at=datetime.now(UTC),
            status=RunStatus.RUNNING,
            config_metadata=config_metadata,
        )
        self._storage.save_run(run)
        self._current_run_id = run_id

        logger.info('Started collection run', run_id=run_id)
        return run_id

    def resume_collection(self, run_id: str) -> None:
        """Resume an interrupted collection run.

        Args:
            run_id: The run ID to resume

        Raises:
            ValueError: If run not found or not resumable
        """
        run = self._storage.get_run(run_id)
        if run is None:
            msg = f'Run not found: {run_id}'
            raise ValueError(msg)

        if run.status != RunStatus.RUNNING:
            msg = f'Run {run_id} is not resumable (status: {run.status})'
            raise ValueError(msg)

        self._current_run_id = run_id
        logger.info('Resuming collection run', run_id=run_id)

    def discover_repositories(self) -> list[dict[str, Any]]:  # noqa: C901, PLR0912, PLR0915
        """Discover repositories using GitHub Search API.

        Uses star-range bucketing to bypass the 1000-result limit.

        Returns:
            List of repository data dictionaries

        Raises:
            RateLimitExceededError: If rate limit is exceeded
        """
        repos: list[dict[str, Any]] = []
        processed_repos: set[str] = set()

        # Get last processed repo for resume
        last_repo = self._storage.get_progress('last_repo')
        if isinstance(last_repo, str):
            processed_repos.add(last_repo)

        # Get search cursor for resume
        search_cursor_value = self._storage.get_progress('search_cursor')
        start_range_idx = 0
        start_page = 1

        if search_cursor_value is not None:
            # Handle both SearchCursor object and dict (from JSON)
            if isinstance(search_cursor_value, SearchCursor):
                search_cursor = search_cursor_value
            else:
                # When deserialized from JSON, SearchCursor becomes a dict
                # Type narrowing: if not (None or SearchCursor), it's a dict from JSON
                search_cursor_dict = cast('dict[str, Any]', search_cursor_value)
                try:
                    search_cursor = SearchCursor(**search_cursor_dict)
                except (TypeError, ValueError):
                    search_cursor = None

            if search_cursor:
                # Find the star range index
                for idx, star_range in enumerate(self.STAR_RANGES):
                    if star_range == search_cursor.stars_range:
                        start_range_idx = idx
                        start_page = search_cursor.page + 1  # Start from next page
                        break

        # Iterate through star ranges
        for range_idx, star_range in enumerate(
            self.STAR_RANGES[start_range_idx:], start=start_range_idx
        ):
            if len(repos) >= self.max_repos:
                break

            # Skip ranges before resume point
            if range_idx < start_range_idx:
                continue

            # Search with filters
            query_parts = [
                star_range,
                f'pushed:>{self._get_time_window_start().isoformat()}',
                'is:public',
                'is:not-archived',
                'is:not-fork',
                'license:>0',  # Has license
            ]
            query = ' '.join(query_parts)

            # Paginate through results
            # GitHub Search API limit: 1000 results = ~34 pages (30 per page)
            max_pages_per_range = 34
            page = start_page if range_idx == start_range_idx else 1
            repos_before_page = len(repos)

            while len(repos) < self.max_repos and page <= max_pages_per_range:
                try:
                    results = self._github_client.search_repositories(
                        query=query,
                        per_page=30,
                        page=page,
                    )

                    if not results:
                        break  # No more results in this range

                    repos_before_page = len(repos)
                    for repo in results:
                        repo_name = repo['full_name']
                        if repo_name in processed_repos:
                            continue  # Skip already processed

                        if repo['stargazers_count'] < self.min_stars:
                            continue  # Filter by min stars

                        repos.append(repo)
                        processed_repos.add(repo_name)

                        if len(repos) >= self.max_repos:
                            break

                    # If no new repos were added, break to avoid infinite loop
                    if len(repos) == repos_before_page:
                        break

                    # Save search cursor
                    self._storage.save_progress(
                        'search_cursor',
                        SearchCursor(stars_range=star_range, page=page),
                    )

                    page += 1

                    # Check for interruption
                    if self._interrupted:
                        logger.info('Collection interrupted during discovery')
                        return repos

                except RateLimitExceededError as e:
                    logger.exception(
                        'Rate limit exceeded during discovery', error=str(e)
                    )
                    raise

        return repos

    def _get_time_window_start(self) -> datetime:
        """Get the start of the time window for commit filtering."""
        return datetime.now(UTC) - timedelta(days=self.time_window_days)

    def process_repository(
        self,
        run_id: str,
        repo_data: dict[str, Any],
    ) -> RepoRecord | None:
        """Process a single repository and parse its commits.

        Args:
            run_id: The run ID this repo belongs to
            repo_data: Repository data from GitHub API

        Returns:
            RepoRecord if processing succeeded, None if skipped/failed
        """
        repo_name = repo_data['full_name']
        logger.info('Processing repository', repo=repo_name)

        try:
            # Fetch commits
            since = self._get_time_window_start()
            commits = self._github_client.get_commits(
                repo=repo_name,
                sha=repo_data.get('default_branch', 'main'),
                since=since,
                per_page=self.max_commits_per_repo,
            )

            # Parse commits
            type_counts: dict[str, int] = {ct.value: 0 for ct in CommitType}
            commits_analyzed = 0
            breaking_scoped = 0
            breaking_unscoped = 0
            nonbreaking_scoped = 0
            nonbreaking_unscoped = 0

            for commit in commits[: self.max_commits_per_repo]:
                # Skip merge commits (2+ parents)
                if len(commit.get('parents', [])) >= 2:
                    continue

                # Skip bot commits
                author_login = commit.get('author', {}).get('login', '')
                if author_login and is_bot(author_login):
                    continue

                # Parse commit message
                message = commit['commit']['message']
                if not is_conventional_commit(message):
                    continue

                commit_type = parse_commit_type(message)
                if commit_type:
                    type_counts[commit_type.value] += 1
                    commits_analyzed += 1

                    # Track breaking/scope combinations
                    is_breaking = parse_breaking(message)
                    has_scope = parse_has_scope(message)

                    if is_breaking and has_scope:
                        breaking_scoped += 1
                    elif is_breaking and not has_scope:
                        breaking_unscoped += 1
                    elif not is_breaking and has_scope:
                        nonbreaking_scoped += 1
                    else:  # not breaking and not scoped
                        nonbreaking_unscoped += 1

            # Get head commit SHA (ensure it's at least 7 characters for validation)
            if commits:
                head_sha = commits[0]['sha'][:40]
                # Pad short SHAs to meet minimum length requirement
                if len(head_sha) < 7:
                    head_sha = head_sha.ljust(7, '0')
            else:
                head_sha = '0000000'  # Placeholder for repos with no commits

            # Parse created_at with error handling
            try:
                created_at = datetime.fromisoformat(repo_data['created_at'])
            except (ValueError, KeyError) as e:
                logger.warning(
                    'Failed to parse repository created_at date, using fallback',
                    repo=repo_name,
                    date_value=repo_data.get('created_at'),
                    error=str(e),
                )
                # Use a reasonable fallback (GitHub's founding date)
                created_at = datetime(2008, 1, 1, tzinfo=UTC)

            # Create repo record
            record = RepoRecord(
                run_id=run_id,
                repo=repo_name,
                default_branch=repo_data.get('default_branch', 'main'),
                head_commit=head_sha,
                stars=repo_data['stargazers_count'],
                language=repo_data.get('language'),
                created_at=created_at,
                license=repo_data.get('license', {}).get('spdx_id'),
                timestamp=datetime.now(UTC),
                commits_analyzed=commits_analyzed,
                breaking_scoped=breaking_scoped,
                breaking_unscoped=breaking_unscoped,
                nonbreaking_scoped=nonbreaking_scoped,
                nonbreaking_unscoped=nonbreaking_unscoped,
                **type_counts,
            )

            logger.info(
                'Repository processed',
                repo=repo_name,
                commits=commits_analyzed,
            )

            return record  # noqa: TRY300
        except Exception as e:  # noqa: BLE001
            logger.warning(
                'Failed to process repository',
                repo=repo_name,
                error=str(e),
            )
            return None

    def run(self, *, resume: bool = False) -> str:
        """Run the full collection process.

        Args:
            resume: If True, resume from last checkpoint

        Returns:
            Run ID of the collection

        Raises:
            RuntimeError: If concurrent run detected
            RateLimitExceededError: If rate limit exceeded
        """
        # Start or resume collection
        if resume:
            latest_run = self._storage.get_running_run()
            if latest_run is None:
                msg = 'No running run found to resume'
                raise ValueError(msg)
            self.resume_collection(latest_run.run_id)
            run_id = latest_run.run_id
        else:
            run_id = self.start_collection()

        try:
            # Discover repositories
            repos = self.discover_repositories()
            logger.info('Discovered repositories', count=len(repos))

            # Process each repository
            repos_processed = 0
            repos_qualified = 0
            total_commits = 0

            for repo_data in repos:
                if self._interrupted:
                    logger.info('Collection interrupted, saving progress')
                    break

                # Process repository
                record = self.process_repository(run_id, repo_data)

                if record is None:
                    repos_processed += 1
                    continue  # Failed or skipped

                # Save record and checkpoint
                self._storage.save_repo_record(record)
                self._storage.save_progress('last_repo', repo_data['full_name'])

                repos_processed += 1
                repos_qualified += 1
                total_commits += record.commits_analyzed

                # Update run stats
                run = self._storage.get_run(run_id)
                if run:
                    run.repos_processed = repos_processed
                    run.repos_qualified = repos_qualified
                    run.total_commits_analyzed = total_commits
                    self._storage.save_run(run)

                logger.info(
                    'Progress',
                    processed=repos_processed,
                    qualified=repos_qualified,
                    commits=total_commits,
                )

            # Complete collection
            self.complete_collection(run_id)
            return run_id  # noqa: TRY300  # noqa: TRY300
        except KeyboardInterrupt:
            logger.info('Collection interrupted by user')
            self.complete_collection(run_id, interrupted=True)
            sys.exit(0)
        except RateLimitExceededError as e:
            logger.exception('Rate limit exceeded', error=str(e))
            self.complete_collection(run_id, failed=True)
            raise
        except Exception as e:
            logger.exception('Collection failed', error=str(e))
            self.complete_collection(run_id, failed=True)
            raise

    def complete_collection(
        self,
        run_id: str,
        *,
        interrupted: bool = False,
        failed: bool = False,
    ) -> None:
        """Mark collection as complete.

        Args:
            run_id: The run ID
            interrupted: If True, mark as interrupted (resumable)
            failed: If True, mark as failed
        """
        run = self._storage.get_run(run_id)
        if run is None:
            return

        if failed:
            run.status = RunStatus.FAILED
        elif interrupted:
            run.status = RunStatus.RUNNING  # Keep as running for resume
        else:
            run.status = RunStatus.COMPLETED

        run.completed_at = datetime.now(UTC)
        self._storage.save_run(run)

        if run.status == RunStatus.COMPLETED:
            logger.info(
                'Collection completed',
                run_id=run_id,
                repos_processed=run.repos_processed,
                repos_qualified=run.repos_qualified,
                commits=run.total_commits_analyzed,
            )
        elif run.status == RunStatus.FAILED:
            logger.error('Collection failed', run_id=run_id)
        else:
            logger.info('Collection interrupted, can be resumed', run_id=run_id)
