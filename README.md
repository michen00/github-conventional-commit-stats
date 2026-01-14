# github-conventional-commit-stats

description

## Usage

...

## Setup

### Prerequisites

- Python ≥3.12
- [uv](https://docs.astral.sh/uv/) (package manager)
- GitHub Personal Access Token (PAT) with `public_repo` scope

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
   - Name it (e.g., "conv-commit-stats")
   - Select scope: `public_repo` (read access to public repositories)
   - Generate and copy the token (starts with `ghp_`)

2. **Set up environment variables:**

   **Option A: Using .env file (recommended for local development)**

   ```bash
   # Copy the example file
   cp .env.example .env

   # Edit .env and add your token
   # GITHUB_TOKEN=ghp_your_token_here
   ```

   **Option B: Using environment variable (recommended for CI)**

   ```bash
   export GITHUB_TOKEN="ghp_your_token_here"
   ```

3. **Verify your token:**

   ```bash
   # Check if token is set
   echo $GITHUB_TOKEN

   # Test token with GitHub API
   curl -s -H "Authorization: Bearer $GITHUB_TOKEN" \
     https://api.github.com/rate_limit | python -m json.tool
   ```

See [quickstart.md](specs/001-initial-implementation/quickstart.md) for more detailed setup instructions.

## Documentation

[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/michen00/github-conventional-commit-stats)
