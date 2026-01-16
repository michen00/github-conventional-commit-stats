# Conventional Commit Census

A self-updating GitHub Pages site that visualizes the frequency of conventional commit types across popular public repositories.

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Code style: ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Tests](https://github.com/michen00/github-conventional-commit-stats/actions/workflows/CI.yml/badge.svg)](https://github.com/michen00/github-conventional-commit-stats/actions/workflows/CI.yml)

## Features

- 📊 **Interactive Visualization**: Horizontal bar chart showing commit type frequencies
- 🔄 **Automated Collection**: Monthly CI/CD pipeline collects data from ~1000 repositories
- ♿ **Accessible**: WCAG AA compliant with keyboard navigation and screen reader support
- 🔍 **Transparent**: Methodology disclosure on every visualization
- 🛠️ **CLI Tool**: Collect, export, validate, and manage commit statistics

## Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/michen00/github-conventional-commit-stats.git
cd github-conventional-commit-stats

# Install dependencies
make develop

# Verify installation
uv run conv-commit-stats --help
```

### Configuration

1. **Get a GitHub Personal Access Token:**

   - Go to <https://github.com/settings/tokens>
   - Click "Generate new token" → "Generate new token (classic)"
   - Select scope: `public_repo` (read access to public repositories)
   - Generate and copy the token

2. **Set environment variable:**

   **Option A: Using .env file (recommended for local development)**

   ```bash
   cp .env.example .env
   # Edit .env and add your token: GITHUB_TOKEN=ghp_your_token_here
   ```

   **Option B: Using environment variable (recommended for CI)**

   ```bash
   export GITHUB_TOKEN="ghp_your_token_here"
   ```

### Usage

```bash
# Collect statistics from GitHub repositories
uv run conv-commit-stats collect --max-repos 1000 --min-stars 3

# Export data for visualization
uv run conv-commit-stats export --output docs/data.json

# Validate data integrity
uv run conv-commit-stats validate

# Check collection status
uv run conv-commit-stats status

# Prune old runs (keep only 3 most recent)
uv run conv-commit-stats prune --keep 3
```

## Commands

| Command    | Description                                        |
| ---------- | -------------------------------------------------- |
| `collect`  | Collect commit statistics from GitHub repositories |
| `export`   | Export aggregated data to JSON for visualization   |
| `validate` | Verify data integrity of stored runs               |
| `status`   | Show current collection progress and statistics    |
| `prune`    | Remove old runs, keeping only N most recent        |

See `uv run conv-commit-stats <command> --help` for detailed options.

## Development

```bash
# Install development dependencies
make develop

# Run tests
make test

# Run linting and formatting
make format

# Run all checks (linting, type checking, tests)
make check
```

## Project Structure

```tree
.
├── src/conv_commit_stats/    # Python package
│   ├── cli.py                 # CLI commands
│   ├── collector.py          # Collection orchestration
│   ├── github_client.py      # GitHub API client
│   ├── parsing.py            # Commit parsing
│   └── storage.py            # Data persistence
├── tests/                     # Test suite
├── docs/                      # Visualization (GitHub Pages)
│   ├── index.html            # Main visualization page
│   └── data.json             # Exported data
└── data/                      # Collected data (TinyDB JSON files)
```

## Documentation

- [Feature Specification](specs/001-initial-implementation/spec.md)
- [Implementation Plan](specs/001-initial-implementation/plan.md)
- [Quickstart Guide](specs/001-initial-implementation/quickstart.md)
- [Data Model](specs/001-initial-implementation/data-model.md)

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Contributing

Contributions welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/michen00/github-conventional-commit-stats)
