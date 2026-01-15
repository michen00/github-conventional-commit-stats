"""CLI entry point for conv-commit-stats.

Provides commands for collecting, exporting, validating, and managing
conventional commit statistics.
"""

import json
import os
from pathlib import Path

import pandera.errors
import polars as pl
import structlog
import typer
from rich.console import Console

from conv_commit_stats.collector import Collector
from conv_commit_stats.github_client import GitHubClient, RateLimitExceededError
from conv_commit_stats.storage import (
    CommitTypeCounts,
    ExportData,
    Methodology,
    RepoRecord,
    RepoRecordSchema,
    RunStatus,
    SearchCursor,
    Storage,
)

logger = structlog.get_logger(__name__)
console = Console()

app = typer.Typer(
    name='conv-commit-stats',
    help='Conventional Commit Census — Analyze commit type frequencies across GitHub.',
    no_args_is_help=True,
)


def get_db_path(db_path: str | None) -> Path:
    """Get the database path, using default if not provided."""
    if db_path:
        return Path(db_path)
    return Path('data')


def get_storage(db_path: Path) -> Storage:
    """Create and return a Storage instance."""
    return Storage(db_path)


def get_github_token() -> str:
    """Get GitHub token from environment."""
    token = os.environ.get('GITHUB_TOKEN')
    if not token:
        console.print('[red]Error: GITHUB_TOKEN environment variable not set[/red]')
        console.print('[yellow]Set it with: export GITHUB_TOKEN=your_token[/yellow]')
        raise typer.Exit(1) from None
    return token


@app.command()
def collect(
    max_repos: int = typer.Option(1000, help='Maximum repositories to analyze'),
    min_stars: int = typer.Option(3, help='Minimum star count filter'),
    resume: bool = typer.Option(default=False, help='Resume from last checkpoint'),  # noqa: FBT001
    db_path: str | None = typer.Option(
        None,
        help='Override data directory path (default: ./data)',
        envvar='CCC_DB_PATH',
    ),
) -> None:
    """Collect conventional commit statistics from GitHub repositories."""
    db = get_db_path(db_path)
    token = get_github_token()

    try:
        with get_storage(db) as storage, GitHubClient(token=token) as github_client:
            collector = Collector(
                storage=storage,
                github_client=github_client,
                max_repos=max_repos,
                min_stars=min_stars,
            )

            console.print('[green]Starting collection...[/green]')
            run_id = collector.run(resume=resume)
            console.print(f'[green]Collection completed: {run_id}[/green]')

    except RateLimitExceededError as e:
        console.print('[red]Rate limit exceeded[/red]')
        if e.reset_at:
            console.print(f'Reset at: {e.reset_at}')
        raise typer.Exit(1) from None
    except KeyboardInterrupt:
        console.print('\n[yellow]Collection interrupted[/yellow]')
        raise typer.Exit(0) from None
    except Exception as e:
        logger.exception('Collection failed', error=str(e))
        console.print(f'[red]Collection failed: {e}[/red]')
        raise typer.Exit(1) from None


def aggregate_run_data(
    repos: list[RepoRecord],
) -> tuple[CommitTypeCounts, int, int, int, int, int]:
    """Aggregate repository commit type counts and breaking/scope counts using Polars.

    Args:
        repos: List of RepoRecord instances to aggregate

    Returns:
        Tuple of (CommitTypeCounts, total_commits, breaking_scoped, breaking_unscoped,
        nonbreaking_scoped, nonbreaking_unscoped)

    Raises:
        pandera.errors.SchemaError: If DataFrame doesn't match RepoRecordSchema
    """
    if not repos:
        # Return zeros for empty list
        counts = CommitTypeCounts()
        return counts, 0, 0, 0, 0, 0

    # Convert to DataFrame
    # model_dump(mode='json') serializes datetime to ISO 8601 strings
    repo_dicts = [repo.model_dump(mode='json') for repo in repos]
    repo_df = pl.DataFrame(repo_dicts)

    # Handle nullable columns: convert None to empty string for string columns
    # This ensures Polars creates String type columns instead of Null type
    nullable_string_cols = ['language', 'license']
    for col in nullable_string_cols:
        if col in repo_df.columns:
            repo_df = repo_df.with_columns(
                pl.when(pl.col(col).is_null())
                .then(pl.lit(''))
                .otherwise(pl.col(col))
                .alias(col)
            )

    # Validate schema with Pandera (ensures all fields present, correct types)
    # This catches missing fields, wrong types, or constraint violations
    RepoRecordSchema.validate(repo_df)

    # Get commit type columns (all fields in CommitTypeCounts)
    # This ensures we aggregate all 11 types automatically
    commit_type_cols = list(CommitTypeCounts.model_fields.keys())

    # Breaking/scope columns to aggregate
    breaking_scope_cols = [
        'breaking_scoped',
        'breaking_unscoped',
        'nonbreaking_scoped',
        'nonbreaking_unscoped',
    ]

    # Aggregate using Polars vectorized sum (faster than Python loops)
    aggregated = repo_df.select(
        [pl.sum(col).alias(col) for col in commit_type_cols + breaking_scope_cols]
    ).to_dicts()[0]

    # Create CommitTypeCounts from aggregated dict
    # Pydantic validates NonNegativeInt constraints here
    counts = CommitTypeCounts(
        **{k: v for k, v in aggregated.items() if k in commit_type_cols}
    )

    # Calculate total_commits (type-safe: sum of NonNegativeInt fields)
    # Pydantic will validate this is non-negative when creating ExportData
    total_commits = sum(counts.model_dump().values())

    # Extract breaking/scope counts
    breaking_scoped = aggregated['breaking_scoped']
    breaking_unscoped = aggregated['breaking_unscoped']
    nonbreaking_scoped = aggregated['nonbreaking_scoped']
    nonbreaking_unscoped = aggregated['nonbreaking_unscoped']

    return (
        counts,
        total_commits,
        breaking_scoped,
        breaking_unscoped,
        nonbreaking_scoped,
        nonbreaking_unscoped,
    )


@app.command()
def export(
    output: str = typer.Option('docs/data.json', help='Output file path'),
    run: str = typer.Option('latest', help="Run ID or 'latest'"),
    db_path: str | None = typer.Option(
        None,
        help='Override data directory path (default: ./data)',
        envvar='CCC_DB_PATH',
    ),
) -> None:
    """Export aggregated data for visualization."""
    db = get_db_path(db_path)
    output_path = Path(output)

    try:
        with get_storage(db) as storage:
            # Get the run to export
            if run == 'latest':
                run_obj = storage.get_latest_completed_run()
                if run_obj is None:
                    console.print('[red]No completed runs found[/red]')
                    raise typer.Exit(1) from None  # noqa: TRY301
                run_id = run_obj.run_id
            else:
                run_obj = storage.get_run(run)
                if run_obj is None:
                    console.print(f'[red]Run not found: {run}[/red]')
                    raise typer.Exit(1) from None  # noqa: TRY301
                run_id = run

            # Get all repos for the run
            repos = storage.get_repos_for_run(run_id)

            if not repos:
                console.print(
                    f'[yellow]No repositories found for run {run_id}[/yellow]'
                )
                raise typer.Exit(1) from None  # noqa: TRY301

            # Aggregate commit counts using Polars + Pandera
            try:
                (
                    counts,
                    total_commits,
                    breaking_scoped,
                    breaking_unscoped,
                    nonbreaking_scoped,
                    nonbreaking_unscoped,
                ) = aggregate_run_data(repos)
            except pandera.errors.SchemaError as e:
                logger.exception('Schema validation failed', error=str(e))
                console.print(f'[red]Data validation failed: {e}[/red]')
                raise typer.Exit(1) from None

            # Create export data
            export_data = ExportData(
                run_id=run_id,
                generated_at=run_obj.completed_at or run_obj.started_at,
                total_repos=len(repos),
                total_commits=total_commits,
                counts=counts,
                breaking_scoped=breaking_scoped,
                breaking_unscoped=breaking_unscoped,
                nonbreaking_scoped=nonbreaking_scoped,
                nonbreaking_unscoped=nonbreaking_unscoped,
                methodology=Methodology(
                    # Standard methodology parameters per spec.md FR-001, FR-002
                    min_stars=3,
                    max_commits_per_repo=100,
                    time_window_days=365,
                    excluded=[
                        'merge commits',
                        'bot authors',
                        'non-conventional messages',
                        'archived repositories',
                        'forks',
                    ],
                ),
            )

            # Write JSON
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with output_path.open('w') as f:
                json.dump(
                    export_data.model_dump(mode='json'),
                    f,
                    indent=2,
                    default=str,
                )

            console.print(f'[green]Exported to: {output_path}[/green]')
            console.print(f'  Run: {run_id}')
            console.print(f'  Repositories: {len(repos)}')
            console.print(f'  Commits: {total_commits}')

    except Exception as e:
        logger.exception('Export failed', error=str(e))
        console.print(f'[red]Export failed: {e}[/red]')
        raise typer.Exit(1) from None


@app.command()
def validate(
    run: str = typer.Option('all', help="Run ID to validate (or 'all')"),
    db_path: str | None = typer.Option(
        None,
        help='Override data directory path (default: ./data)',
        envvar='CCC_DB_PATH',
    ),
) -> None:
    """Verify data integrity of stored runs and repositories."""
    db = get_db_path(db_path)

    try:
        with get_storage(db) as storage:
            if run == 'all':
                runs = storage.list_runs()
            else:
                run_obj = storage.get_run(run)
                if run_obj is None:
                    console.print(f'[red]Run not found: {run}[/red]')
                    raise typer.Exit(1) from None  # noqa: TRY301
                runs = [run_obj]

            if not runs:
                console.print('[yellow]No runs to validate[/yellow]')
                raise typer.Exit(0) from None  # noqa: TRY301

            all_valid = True
            for run_obj in runs:
                console.print(f'Validating run: {run_obj.run_id}')

                # Check repos for this run
                repos = storage.get_repos_for_run(run_obj.run_id)
                for repo in repos:
                    # Validate commit counts sum correctly
                    expected_sum = (
                        repo.feat
                        + repo.fix
                        + repo.docs
                        + repo.chore
                        + repo.refactor
                        + repo.test
                        + repo.ci
                        + repo.build
                        + repo.style
                        + repo.perf
                        + repo.revert
                    )
                    if repo.commits_analyzed != expected_sum:
                        console.print(
                            f'[red]  ✗ Repo {repo.repo}: '
                            f'commits_analyzed mismatch[/red]'
                        )
                        all_valid = False

                console.print(f'[green]  ✓ Run {run_obj.run_id}: OK[/green]')

            if all_valid:
                console.print('[green]All checks passed[/green]')
                raise typer.Exit(0) from None  # noqa: TRY301
            console.print('[red]Some checks failed[/red]')
            raise typer.Exit(1) from None  # noqa: TRY301

    except typer.Exit:
        raise  # Re-raise typer.Exit to preserve exit code
    except Exception as e:
        logger.exception('Validation failed', error=str(e))
        console.print(f'[red]Validation failed: {e}[/red]')
        raise typer.Exit(1) from None


@app.command()
def status(
    db_path: str | None = typer.Option(
        None,
        help='Override data directory path (default: ./data)',
        envvar='CCC_DB_PATH',
    ),
) -> None:
    """Show current collection progress and statistics."""
    db = get_db_path(db_path)

    try:
        with get_storage(db) as storage:
            # Get current running run
            running_run = storage.get_running_run()

            if running_run:
                console.print(
                    f'[yellow]Current Run: {running_run.run_id} (running)[/yellow]'
                )
                console.print(
                    f'  Progress: {running_run.repos_processed} repos processed'
                )
                console.print(f'  Qualified: {running_run.repos_qualified} repos')
                console.print(f'  Commits: {running_run.total_commits_analyzed}')

                # Get progress
                last_repo = storage.get_progress('last_repo')
                if last_repo:
                    console.print(f'  Last repo: {last_repo}')

                search_cursor = storage.get_progress('search_cursor')
                if search_cursor:
                    if isinstance(search_cursor, dict):
                        cursor = SearchCursor(**search_cursor)
                    else:
                        cursor = search_cursor
                    console.print(
                        f'  Search cursor: {cursor.stars_range}, page {cursor.page}'
                    )

            # Get most recent completed run
            latest_completed = storage.get_latest_completed_run()
            if latest_completed:
                duration = ''
                if latest_completed.completed_at:
                    delta = latest_completed.completed_at - latest_completed.started_at
                    hours = int(delta.total_seconds() // 3600)
                    minutes = int((delta.total_seconds() % 3600) // 60)
                    duration = f'{hours}h {minutes}m'

                console.print(
                    f'\n[green]Most Recent Completed: {latest_completed.run_id}[/green]'
                )
                console.print(
                    f'  Repos: {latest_completed.repos_qualified} qualified / '
                    f'{latest_completed.repos_processed} processed'
                )
                console.print(
                    f'  Commits: {latest_completed.total_commits_analyzed} analyzed'
                )
                if duration:
                    console.print(f'  Duration: {duration}')

            if not running_run and not latest_completed:
                console.print('[yellow]No runs found[/yellow]')

    except Exception as e:
        logger.exception('Status check failed', error=str(e))
        console.print(f'[red]Status check failed: {e}[/red]')
        raise typer.Exit(1) from None


@app.command()
def prune(
    keep: int = typer.Option(3, help='Number of recent runs to keep'),
    dry_run: bool = typer.Option(False, '--dry-run', help='Show what would be deleted'),  # noqa: FBT001, FBT003
    db_path: str | None = typer.Option(
        None,
        help='Override data directory path (default: ./data)',
        envvar='CCC_DB_PATH',
    ),
) -> None:
    """Remove old runs, keeping only the N most recent."""
    db = get_db_path(db_path)

    try:
        with get_storage(db) as storage:
            if dry_run:
                console.print(
                    f'[yellow]Dry run: Would keep {keep} most recent runs[/yellow]'
                )
                runs = storage.list_runs()
                completed = [r for r in runs if r.status == RunStatus.COMPLETED]
                completed.sort(key=lambda r: r.started_at, reverse=True)

                if len(completed) > keep:
                    to_delete = completed[keep:]
                    console.print(f'\nWould delete {len(to_delete)} runs:')
                    for run in to_delete:
                        repo_count = storage.count_repos_for_run(run.run_id)
                        console.print(f'  - {run.run_id} ({repo_count} repos)')
                else:
                    console.print('No runs to delete')
            else:
                deleted = storage.prune_old_runs(keep=keep)
                if deleted > 0:
                    console.print(f'[green]Pruned {deleted} runs[/green]')
                else:
                    console.print('[yellow]No runs to prune[/yellow]')

    except Exception as e:
        logger.exception('Prune failed', error=str(e))
        console.print(f'[red]Prune failed: {e}[/red]')
        raise typer.Exit(1) from None


if __name__ == '__main__':
    app()
