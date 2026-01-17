# Conventional Commit Census

A self-updating GitHub Pages site that visualizes the frequency of conventional commit types across popular public repositories.

[![Build Status](https://img.shields.io/github/actions/workflow/status/michen00/github-conventional-commit-stats/ci.yml?style=plastic)](https://github.com/michen00/github-conventional-commit-stats/actions)
[![Coverage](https://img.shields.io/codecov/c/github/michen00/github-conventional-commit-stats?style=plastic)](https://codecov.io/gh/michen00/github-conventional-commit-stats)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg?style=plastic)](CONTRIBUTING.md)
[![License](https://img.shields.io/github/license/michen00/github-conventional-commit-stats?style=plastic)](LICENSE)

---

## 🌐 [View Live Visualization →](https://michen00.github.io/github-conventional-commit-stats/)

Interactive visualization of conventional commit type frequencies across popular GitHub repositories. Updated monthly via automated CI/CD.

---

## Features

- 📊 **Interactive Visualization**: Horizontal bar chart showing commit type frequencies
- 🔄 **Automated Collection**: Monthly CI/CD pipeline collects data from ~1000 repositories
- ♿ **Accessible**: WCAG AA compliant with keyboard navigation and screen reader support
- 🔍 **Transparent**: Methodology disclosure on every visualization
- 🛠️ **CLI Tool**: Collect, export, validate, and manage commit statistics

## Quick Start

Get up and running in minutes! This guide will take you from zero to visualizing commit statistics.

### Step 1: Install

```bash
# Clone the repository
git clone https://github.com/michen00/github-conventional-commit-stats.git
cd github-conventional-commit-stats

# Install dependencies (creates virtual environment automatically)
make develop

# Verify installation
uv run conv-commit-stats --help
```

### Step 2: Configure GitHub Token

1. **Create a GitHub Personal Access Token:**
   - Visit <https://github.com/settings/tokens>
   - Click "Generate new token" → "Generate new token (classic)"
   - Name it (e.g., "conv-commit-stats")
   - Select scope: `public_repo` (read access to public repositories)
   - Generate and copy the token (starts with `ghp_`)

2. **Set the token:**

   **For local development (recommended):**

   ```bash
   cp .env.example .env
   # Edit .env and replace ghp_your_token_here with your actual token
   ```

   **For CI/CD or one-time use:**

   ```bash
   export GITHUB_TOKEN="ghp_your_token_here"
   ```

3. **Verify your token works:**

   ```bash
   # Test the token (should show rate limit info)
   curl -s -H "Authorization: Bearer $GITHUB_TOKEN" \
     https://api.github.com/rate_limit | python -m json.tool
   ```

### Step 3: Quick Test Run (10 repos)

Test the system with a small sample before running a full collection:

```bash
# Collect from 10 high-star repositories (~1-2 minutes)
uv run conv-commit-stats collect --max-repos 10 --min-stars 10000

# Check what was collected
uv run conv-commit-stats status

# Export data for visualization
uv run conv-commit-stats export --output docs/data.json

# Validate everything looks good
uv run conv-commit-stats validate
```

### Step 4: View Your Results

Open the visualization in your browser:

```bash
# Start a local server
cd docs && python -m http.server 8000

# Open http://localhost:8000 in your browser
```

You should see an interactive bar chart showing commit type frequencies!

### Step 5: Full Collection (Optional)

Ready for the full dataset? Collect from ~1000 repositories:

```bash
# Start full collection (may take 1-6 hours depending on rate limits)
uv run conv-commit-stats collect --max-repos 1000 --min-stars 3

# If interrupted, resume from checkpoint
uv run conv-commit-stats collect --resume

# Export and validate
uv run conv-commit-stats export
uv run conv-commit-stats validate
```

**💡 Tip:** The collection process automatically saves checkpoints, so you can safely interrupt and resume later.

### Troubleshooting

**Token not working?**

```bash
# Verify token is set
echo $GITHUB_TOKEN

# Test token with GitHub API
curl -s -H "Authorization: Bearer $GITHUB_TOKEN" \
  https://api.github.com/rate_limit | python -m json.tool
```

**Rate limit exceeded?**

```bash
# Check when rate limit resets
curl -s -H "Authorization: Bearer $GITHUB_TOKEN" \
  https://api.github.com/rate_limit | python -m json.tool

# Resume after rate limit resets
uv run conv-commit-stats collect --resume
```

**No data after export?**

```bash
# Make sure you've run collection first
uv run conv-commit-stats collect --max-repos 10

# Then export
uv run conv-commit-stats export
```

**Need more help?** See the [detailed Quickstart Guide](specs/001-initial-implementation/quickstart.md) for comprehensive troubleshooting and advanced usage.

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
