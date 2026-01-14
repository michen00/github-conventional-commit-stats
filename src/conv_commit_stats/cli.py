"""CLI entry point for conv-commit-stats.

Provides commands for collecting, exporting, validating, and managing
conventional commit statistics.
"""

import json
import os
import sys
from pathlib import Path

import structlog
import typer
from pydantic import ValidationError
from rich.console import Console
from rich.table import Table

from conv_commit_stats.collector import Collector
from conv_commit_stats.github_client import GitHubClient, RateLimitExceeded
from conv_commit_stats.storage import (
    CommitTypeCounts,
    ExportData,
    Methodology,
    RunStatus,
    SearchCursor,
    Storage,
)

logger = structlog.get_logger(__name__)
console = Console()

app = typer.Typer(
    name="conv-commit-stats",
    help="Conventional Commit Census — Analyze commit type frequencies across GitHub.",
    no_args_is_help=True,
)



def get_db_path(db_path: str | None) -> Path:
    """Get the database path, using default if not provided."""
    if db_path:
        return Path(db_path)
    return Path("data")


def get_storage(db_path: Path) -> Storage:
    """Create and return a Storage instance."""
    return Storage(db_path)


def get_github_token() -> str:
    """Get GitHub token from environment."""
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        console.print("[red]Error: GITHUB_TOKEN environment variable not set[/red]")
        console.print(
            "[yellow]Set it with: export GITHUB_TOKEN=your_token[/yellow]"
        )
        raise typer.Exit(1)
    return token


@app.command()
def collect(
    max_repos: int = typer.Option(1000, help="Maximum repositories to analyze"),
    min_stars: int = typer.Option(3, help="Minimum star count filter"),
    resume: bool = typer.Option(False, help="Resume from last checkpoint"),
    db_path: str | None = typer.Option(
        None, help="Override data directory path (default: ./data)", envvar="CCC_DB_PATH"
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

            console.print(f"[green]Starting collection...[/green]")
            run_id = collector.run(resume=resume)
            console.print(f"[green]Collection completed: {run_id}[/green]")

    except RateLimitExceeded as e:
        console.print(f"[red]Rate limit exceeded[/red]")
        if e.reset_at:
            console.print(f"Reset at: {e.reset_at}")
        raise typer.Exit(1)
    except KeyboardInterrupt:
        console.print("\n[yellow]Collection interrupted[/yellow]")
        raise typer.Exit(0)
    except Exception as e:
        logger.exception("Collection failed", error=str(e))
        console.print(f"[red]Collection failed: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def export(
    output: str = typer.Option("docs/data.json", help="Output file path"),
    run: str = typer.Option("latest", help="Run ID or 'latest'"),
    db_path: str | None = typer.Option(
        None, help="Override data directory path (default: ./data)", envvar="CCC_DB_PATH"
    ),
) -> None:
    """Export aggregated data for visualization."""
    db = get_db_path(db_path)
    output_path = Path(output)

    try:
        with get_storage(db) as storage:
            # Get the run to export
            if run == "latest":
                run_obj = storage.get_latest_completed_run()
                if run_obj is None:
                    console.print("[red]No completed runs found[/red]")
                    raise typer.Exit(1)
                run_id = run_obj.run_id
            else:
                run_obj = storage.get_run(run)
                if run_obj is None:
                    console.print(f"[red]Run not found: {run}[/red]")
                    raise typer.Exit(1)
                run_id = run

            # Get all repos for the run
            repos = storage.get_repos_for_run(run_id)

            if not repos:
                console.print(f"[yellow]No repositories found for run {run_id}[/yellow]")
                raise typer.Exit(1)

            # Aggregate commit counts
            counts = CommitTypeCounts()
            for repo in repos:
                counts.feat += repo.feat
                counts.fix += repo.fix
                counts.docs += repo.docs
                counts.chore += repo.chore
                counts.refactor += repo.refactor
                counts.test += repo.test
                counts.ci += repo.ci
                counts.build += repo.build
                counts.style += repo.style
                counts.perf += repo.perf
                counts.revert += repo.revert

            total_commits = sum(
                [
                    counts.feat,
                    counts.fix,
                    counts.docs,
                    counts.chore,
                    counts.refactor,
                    counts.test,
                    counts.ci,
                    counts.build,
                    counts.style,
                    counts.perf,
                    counts.revert,
                ]
            )

            # Create export data
            export_data = ExportData(
                run_id=run_id,
                generated_at=run_obj.completed_at or run_obj.started_at,
                total_repos=len(repos),
                total_commits=total_commits,
                counts=counts,
                methodology=Methodology(
                    min_stars=3,  # TODO: Get from collector config
                    max_commits_per_repo=100,
                    time_window_days=365,
                    excluded=[
                        "merge commits",
                        "bot authors",
                        "non-conventional messages",
                        "archived repositories",
                        "forks",
                    ],
                ),
            )

            # Write JSON
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with output_path.open("w") as f:
                json.dump(
                    export_data.model_dump(mode="json"),
                    f,
                    indent=2,
                    default=str,
                )

            console.print(f"[green]Exported to: {output_path}[/green]")
            console.print(f"  Run: {run_id}")
            console.print(f"  Repositories: {len(repos)}")
            console.print(f"  Commits: {total_commits}")

    except Exception as e:
        logger.exception("Export failed", error=str(e))
        console.print(f"[red]Export failed: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def validate(
    run: str = typer.Option("all", help="Run ID to validate (or 'all')"),
    db_path: str | None = typer.Option(
        None, help="Override data directory path (default: ./data)", envvar="CCC_DB_PATH"
    ),
) -> None:
    """Verify data integrity of stored runs and repositories."""
    db = get_db_path(db_path)

    try:
        with get_storage(db) as storage:
            if run == "all":
                runs = storage.list_runs()
            else:
                run_obj = storage.get_run(run)
                if run_obj is None:
                    console.print(f"[red]Run not found: {run}[/red]")
                    raise typer.Exit(1)
                runs = [run_obj]

            if not runs:
                console.print("[yellow]No runs to validate[/yellow]")
                raise typer.Exit(0)

            all_valid = True
            for run_obj in runs:
                console.print(f"Validating run: {run_obj.run_id}")

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
                            f"[red]  ✗ Repo {repo.repo}: commits_analyzed mismatch[/red]"
                        )
                        all_valid = False

                console.print(f"[green]  ✓ Run {run_obj.run_id}: OK[/green]")

            if all_valid:
                console.print("[green]All checks passed[/green]")
                raise typer.Exit(0)
            else:
                console.print("[red]Some checks failed[/red]")
                raise typer.Exit(1)

    except Exception as e:
        logger.exception("Validation failed", error=str(e), exc_info=True)
        console.print(f"[red]Validation failed: {e}[/red]")
        import traceback
        console.print(f"[red]{traceback.format_exc()}[/red]")
        raise typer.Exit(1)


@app.command()
def status(
    db_path: str | None = typer.Option(
        None, help="Override data directory path (default: ./data)", envvar="CCC_DB_PATH"
    ),
) -> None:
    """Show current collection progress and statistics."""
    db = get_db_path(db_path)

    try:
        with get_storage(db) as storage:
            # Get current running run
            running_run = storage.get_running_run()

            if running_run:
                console.print(f"[yellow]Current Run: {running_run.run_id} (running)[/yellow]")
                console.print(f"  Progress: {running_run.repos_processed} repos processed")
                console.print(f"  Qualified: {running_run.repos_qualified} repos")
                console.print(f"  Commits: {running_run.total_commits_analyzed}")

                # Get progress
                last_repo = storage.get_progress("last_repo")
                if last_repo:
                    console.print(f"  Last repo: {last_repo}")

                search_cursor = storage.get_progress("search_cursor")
                if search_cursor:
                    if isinstance(search_cursor, dict):
                        cursor = SearchCursor(**search_cursor)
                    else:
                        cursor = search_cursor
                    console.print(f"  Search cursor: {cursor.stars_range}, page {cursor.page}")

            # Get most recent completed run
            latest_completed = storage.get_latest_completed_run()
            if latest_completed:
                duration = ""
                if latest_completed.completed_at:
                    delta = latest_completed.completed_at - latest_completed.started_at
                    hours = int(delta.total_seconds() // 3600)
                    minutes = int((delta.total_seconds() % 3600) // 60)
                    duration = f"{hours}h {minutes}m"

                console.print(f"\n[green]Most Recent Completed: {latest_completed.run_id}[/green]")
                console.print(f"  Repos: {latest_completed.repos_qualified} qualified / {latest_completed.repos_processed} processed")
                console.print(f"  Commits: {latest_completed.total_commits_analyzed} analyzed")
                if duration:
                    console.print(f"  Duration: {duration}")

            if not running_run and not latest_completed:
                console.print("[yellow]No runs found[/yellow]")

    except Exception as e:
        logger.exception("Status check failed", error=str(e))
        console.print(f"[red]Status check failed: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def prune(
    keep: int = typer.Option(3, help="Number of recent runs to keep"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be deleted"),
    db_path: str | None = typer.Option(
        None, help="Override data directory path (default: ./data)", envvar="CCC_DB_PATH"
    ),
) -> None:
    """Remove old runs, keeping only the N most recent."""
    db = get_db_path(db_path)

    try:
        with get_storage(db) as storage:
            if dry_run:
                console.print(f"[yellow]Dry run: Would keep {keep} most recent runs[/yellow]")
                runs = storage.list_runs()
                completed = [r for r in runs if r.status == RunStatus.COMPLETED]
                completed.sort(key=lambda r: r.started_at, reverse=True)

                if len(completed) > keep:
                    to_delete = completed[keep:]
                    console.print(f"\nWould delete {len(to_delete)} runs:")
                    for run in to_delete:
                        repo_count = storage.count_repos_for_run(run.run_id)
                        console.print(f"  - {run.run_id} ({repo_count} repos)")
                else:
                    console.print("No runs to delete")
            else:
                deleted = storage.prune_old_runs(keep=keep)
                if deleted > 0:
                    console.print(f"[green]Pruned {deleted} runs[/green]")
                else:
                    console.print("[yellow]No runs to prune[/yellow]")

    except Exception as e:
        logger.exception("Prune failed", error=str(e))
        console.print(f"[red]Prune failed: {e}[/red]")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
