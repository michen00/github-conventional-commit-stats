# Quickstart: Conventional Commit Census

**Branch**: `001-initial-implementation` | **Date**: 2026-01-12

## Prerequisites

- Python ≥3.12
- [uv](https://docs.astral.sh/uv/) (package manager)
- GitHub Personal Access Token (PAT) with `public_repo` scope

---

## Installation

```bash
# Clone the repository
git clone https://github.com/michen00/github-conventional-commit-stats.git
cd github-conventional-commit-stats

# Install dependencies
make develop

# Verify installation
uv run conv-commit-stats --help
```

---

## Configuration

Set your GitHub token:

```bash
# Option 1: Environment variable (recommended for CI)
export GITHUB_TOKEN="ghp_your_token_here"

# Option 2: .env file (for local development)
echo "GITHUB_TOKEN=ghp_your_token_here" > .env
```

---

## Quick Run (10 repos)

Test the system with a small sample:

```bash
# Collect data from 10 high-star repos
uv run conv-commit-stats collect --max-repos 10 --min-stars 10000

# Check status
uv run conv-commit-stats status

# Export for visualization
uv run conv-commit-stats export --output docs/data.json

# Validate data integrity
uv run conv-commit-stats validate
```

---

## Full Collection (~1000 repos)

Run a complete data collection:

```bash
# Start collection (may take 1-6 hours depending on rate limits)
uv run conv-commit-stats collect --max-repos 1000 --min-stars 3

# If interrupted, resume from checkpoint
uv run conv-commit-stats collect --resume

# Export and validate
uv run conv-commit-stats export
uv run conv-commit-stats validate
```

---

## View Visualization

Open the visualization locally:

```bash
# Using Python's built-in server
cd docs && python -m http.server 8000

# Then open http://localhost:8000 in your browser
```

Or deploy to GitHub Pages (automatic via CI).

---

## Development Workflow

### Running Tests

```bash
# Run all tests with coverage
make test

# Run specific test file
uv run pytest tests/test_parsing.py -v

# Run with verbose output
uv run pytest -v --tb=short
```

### Code Quality

```bash
# Run all checks (lint, type check, tests)
make check

# Format code
make format

# Lint only
make lint
```

### TDD Workflow

Per Constitution Principle I, tests must be written before implementation:

```bash
# 1. Create test file
touch tests/test_new_feature.py

# 2. Write failing tests
# 3. Run tests (should fail)
uv run pytest tests/test_new_feature.py -v

# 4. Implement feature
# 5. Run tests (should pass)
uv run pytest tests/test_new_feature.py -v

# 6. Verify all checks pass
make check
```

---

## Data Files

After collection, data is stored in:

```
data/
├── runs.json       # Run metadata
├── repos.json      # Per-repo commit counts
└── progress.json   # Resume checkpoints

docs/
├── index.html      # Visualization page
└── data.json       # Exported data for frontend
```

---

## CLI Reference

| Command | Description |
|---------|-------------|
| `collect` | Discover repos and gather commit statistics |
| `export` | Generate visualization-ready JSON |
| `validate` | Verify data integrity |
| `status` | Show current progress/statistics |
| `prune` | Clean up old runs |

See `uv run conv-commit-stats COMMAND --help` for detailed options.

---

## Troubleshooting

### "GITHUB_TOKEN not set"

```bash
# Set your token
export GITHUB_TOKEN="ghp_your_token_here"

# Verify it's set
echo $GITHUB_TOKEN
```

### "Rate limit exceeded"

```bash
# Check when rate limit resets
curl -s -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/rate_limit | jq '.rate'

# Resume after rate limit resets
uv run conv-commit-stats collect --resume
```

### "No completed runs found"

```bash
# Run collection first
uv run conv-commit-stats collect --max-repos 10

# Then export
uv run conv-commit-stats export
```

### Tests Failing

```bash
# Ensure dependencies are installed
make develop

# Run with verbose output
uv run pytest -v --tb=long

# Check for type errors
uv run mypy src/
```

---

## Next Steps

1. Review the [CLI Contract](contracts/cli.md) for detailed command specifications
2. Review the [Data Model](data-model.md) for entity schemas
3. Run `/speckit.tasks` to generate implementation tasks
4. Start with `tests/test_parsing.py` (TDD: pure functions first)
