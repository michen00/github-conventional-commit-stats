"""CLI entry point for conv-commit-stats.

This is a placeholder. Implementation will follow TDD:
1. Write tests/test_cli_smoke.py first
2. Then implement the actual commands
"""

import typer

app = typer.Typer(
    name='conv-commit-stats',
    help='Conventional Commit Census — Analyze commit type frequencies across GitHub.',
    no_args_is_help=True,
)


@app.command()
def collect(
    max_repos: int = typer.Option(1000, help='Maximum repositories to analyze'),
    min_stars: int = typer.Option(3, help='Minimum star count filter'),
    resume: bool = typer.Option(False, help='Resume from last checkpoint'),
) -> None:
    """Collect conventional commit statistics from GitHub repositories."""
    raise NotImplementedError('TODO: Implement after writing tests')


@app.command()
def export(
    output: str = typer.Option('docs/data.json', help='Output file path'),
    run: str = typer.Option('latest', help="Run ID or 'latest'"),
) -> None:
    """Export aggregated data for visualization."""
    raise NotImplementedError('TODO: Implement after writing tests')


@app.command()
def prune(
    keep: int = typer.Option(3, help='Number of recent runs to keep'),
) -> None:
    """Remove old runs, keeping only the N most recent."""
    raise NotImplementedError('TODO: Implement after writing tests')


@app.command()
def validate() -> None:
    """Validate data integrity of stored results."""
    raise NotImplementedError('TODO: Implement after writing tests')


@app.command()
def status() -> None:
    """Show current collection progress and statistics."""
    raise NotImplementedError('TODO: Implement after writing tests')


if __name__ == '__main__':
    app()
