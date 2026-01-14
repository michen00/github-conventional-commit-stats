# CLI Interface Contract: conv-commit-stats

**Branch**: `001-initial-implementation` | **Date**: 2026-01-12

## Overview

This document specifies the command-line interface for the `conv-commit-stats` tool. The CLI is implemented using Typer with Rich for terminal formatting.

---

## Entry Point

```bash
uv run conv-commit-stats [COMMAND] [OPTIONS]
```

**Package**: `conv_commit_stats`
**Module**: `conv_commit_stats.cli:app`
**pyproject.toml entry**:

```toml
[project.scripts]
conv-commit-stats = "conv_commit_stats.cli:app"
```

---

## Global Options

Available on all commands:

| Option      | Type   | Default  | Description                  |
| ----------- | ------ | -------- | ---------------------------- |
| `--db-path` | `PATH` | `./data` | Override data directory path |
| `--help`    | flag   |          | Show help and exit           |
| `--version` | flag   |          | Show version and exit        |

**Environment Variables**:

| Variable        | Description                                           |
| --------------- | ----------------------------------------------------- |
| `GITHUB_TOKEN`  | **Required**. GitHub API token (PAT or Actions token) |
| `CCC_DB_PATH`   | Override data directory (same as `--db-path`)         |
| `CCC_LOG_LEVEL` | Logging level: `DEBUG`, `INFO`, `WARNING`, `ERROR`    |

---

## Commands

### 1. `collect`

Discover repositories and collect conventional commit statistics.

```bash
uv run conv-commit-stats collect [OPTIONS]
```

**Options**:

| Option        | Type  | Default | Description                     |
| ------------- | ----- | ------- | ------------------------------- |
| `--max-repos` | `INT` | `1000`  | Maximum repositories to process |
| `--min-stars` | `INT` | `3`     | Minimum star count filter       |
| `--resume`    | flag  | `false` | Resume from last checkpoint     |

**Behavior**:

- **Concurrency Check**: Before starting, verify no other run has `status=running`. If a running run exists, exit with error: "Another collection is in progress (run_id). Use --resume to continue or wait for it to complete."
- Creates new run with `status=running`
- Discovers repos via GitHub Search API (star-range bucketing)
- For each repo: fetches commits, parses types, saves record
- Saves checkpoint after each repo
- On completion: marks run `completed`
- On interrupt (SIGINT/SIGTERM): saves progress, exits 0
- On error: marks run `failed`, exits 1

**Output** (stdout):

```text
Starting collection run: run_2026-01-12T04:00:00Z
[1/1000] facebook/react: 100 commits (feat: 25, fix: 18, ...)
[2/1000] microsoft/vscode: 95 commits (feat: 30, fix: 22, ...)
...
Collection complete: 847 repos qualified, 84700 commits analyzed
```

**Exit Codes**:

| Code | Meaning                                             |
| ---- | --------------------------------------------------- |
| 0    | Success or graceful interrupt                       |
| 1    | Error (rate limit exhausted, network failure, etc.) |

---

### 2. `export`

Generate visualization-ready JSON from collected data.

```bash
uv run conv-commit-stats export [OPTIONS]
```

**Options**:

| Option     | Type   | Default          | Description                    |
| ---------- | ------ | ---------------- | ------------------------------ |
| `--run`    | `TEXT` | `latest`         | Run ID to export (or `latest`) |
| `--output` | `PATH` | `docs/data.json` | Output file path               |

**Behavior**:

- Loads specified run (or most recent completed run)
- Aggregates commit counts across all repos
- Generates JSON with counts and methodology
- Writes to output path

**Output** (stdout):

```text
Exporting run: run_2026-01-12T04:00:00Z
Aggregating 847 repositories...
Written to: docs/data.json
```

**Exit Codes**:

| Code | Meaning                                  |
| ---- | ---------------------------------------- |
| 0    | Success                                  |
| 1    | No completed runs found / invalid run ID |

---

### 3. `validate`

Verify data integrity of stored runs and repositories.

```bash
uv run conv-commit-stats validate [OPTIONS]
```

**Options**:

| Option  | Type   | Default | Description                   |
| ------- | ------ | ------- | ----------------------------- |
| `--run` | `TEXT` | `all`   | Run ID to validate (or `all`) |

**Checks Performed**:

1. JSON files parse correctly
2. All repos reference existing runs (referential integrity)
3. No negative counts
4. Counts sum to `commits_analyzed`
5. Timestamps are valid ISO format
6. Run IDs are unique
7. `docs/data.json` exists and parses (if present)

**Output** (stdout):

```text
Validating run: run_2026-01-12T04:00:00Z
✓ Schema validity: OK
✓ Referential integrity: OK
✓ Data sanity: OK
✓ Export validity: OK
All checks passed.
```

**Output** (on failure):

```text
Validating run: run_2026-01-12T04:00:00Z
✓ Schema validity: OK
✗ Referential integrity: FAILED
  - Repo 'foo/bar' references non-existent run 'run_invalid'
```

**Exit Codes**:

| Code | Meaning                   |
| ---- | ------------------------- |
| 0    | All checks passed         |
| 1    | One or more checks failed |

---

### 4. `status`

Show current progress and statistics.

```bash
uv run conv-commit-stats status
```

**Options**: None (uses global options only)

**Behavior**:

- Shows current run status (if running)
- Shows most recent completed run summary
- Shows checkpoint state (for `--resume` decision)

**Output** (stdout):

```text
Current Run: run_2026-01-12T04:00:00Z (running)
  Progress: 523/1000 repos processed
  Last repo: microsoft/TypeScript
  Search cursor: stars:500..1000, page 3

Most Recent Completed: run_2026-01-01T04:00:00Z
  Repos: 847 qualified / 1000 processed
  Commits: 84700 analyzed
  Duration: 5h 12m
```

**Exit Codes**:

| Code | Meaning                        |
| ---- | ------------------------------ |
| 0    | Always (informational command) |

---

### 5. `prune`

Clean up old runs beyond retention limit.

```bash
uv run conv-commit-stats prune [OPTIONS]
```

**Options**:

| Option      | Type  | Default | Description                     |
| ----------- | ----- | ------- | ------------------------------- |
| `--keep`    | `INT` | `3`     | Number of recent runs to retain |
| `--dry-run` | flag  | `false` | Show what would be deleted      |

**Behavior**:

- Lists all completed runs sorted by `started_at`
- Identifies runs beyond the `--keep` threshold
- Deletes run metadata from `runs.json`
- Deletes associated repos from `repos.json`
- Clears progress if it references deleted run

**Output** (stdout):

```text
Pruning runs (keeping 3 most recent)...
Deleting: run_2025-10-01T04:00:00Z (523 repos)
Deleting: run_2025-09-01T04:00:00Z (498 repos)
Pruned 2 runs, 1021 repo records.
```

**Exit Codes**:

| Code | Meaning                       |
| ---- | ----------------------------- |
| 0    | Success (or nothing to prune) |

---

## Error Handling

### Common Error Messages

| Error                           | Cause                 | Resolution                              |
| ------------------------------- | --------------------- | --------------------------------------- |
| `GITHUB_TOKEN not set`          | Missing env var       | Set `GITHUB_TOKEN` environment variable |
| `Rate limit exceeded`           | API quota exhausted   | Wait for reset or use `--resume` later  |
| `Run not found: {id}`           | Invalid run ID        | Use `status` to list available runs     |
| `No completed runs`             | Export with no data   | Run `collect` first                     |
| `Data directory not found`      | Bad `--db-path`       | Check path exists or omit for default   |
| `Another collection in progress`| Concurrent run attempt| Wait for existing run or use `--resume` |
| `Progress file corrupted`       | Invalid progress.json | Run without `--resume` to start fresh   |

### Rate Limit Sleep Behavior

When the system sleeps due to rate limit exhaustion:

1. Calculate sleep duration from `X-RateLimit-Reset` header
2. Log: "Rate limit reached. Sleeping until {reset_time} ({duration} remaining)"
3. **Re-check remaining quota after wake**: If reset occurred during sleep and quota is now available, continue immediately
4. **If still limited**: Re-calculate sleep time and continue waiting
5. Log: "Rate limit reset. Resuming collection."

This prevents unnecessary waiting if the reset happens earlier than expected (e.g., due to clock skew).

### Signal Handling

| Signal            | Behavior                                     |
| ----------------- | -------------------------------------------- |
| `SIGINT` (Ctrl+C) | Finish current repo, save progress, exit 0   |
| `SIGTERM`         | Same as SIGINT                               |
| `SIGKILL`         | Immediate termination (progress may be lost) |

---

## Usage Examples

```bash
# Full collection run
uv run conv-commit-stats collect --max-repos 1000 --min-stars 3

# Resume interrupted run
uv run conv-commit-stats collect --resume

# Export latest run to visualization
uv run conv-commit-stats export --output docs/data.json

# Export specific run
uv run conv-commit-stats export --run run_2026-01-12T04:00:00Z

# Validate all data
uv run conv-commit-stats validate

# Check current status
uv run conv-commit-stats status

# Clean up old runs (keep 3)
uv run conv-commit-stats prune --keep 3

# Dry run prune
uv run conv-commit-stats prune --keep 1 --dry-run
```

---

## Help Text Convention

Each command should display help in this format:

```text
Usage: conv-commit-stats COMMAND [OPTIONS]

Conventional Commit Census CLI

Collect and visualize conventional commit type frequencies
across popular public GitHub repositories.

Commands:
  collect   Discover repos and collect commit statistics
  export    Generate visualization-ready JSON
  validate  Verify data integrity
  status    Show current progress and statistics
  prune     Clean up old runs

Run 'conv-commit-stats COMMAND --help' for command-specific help.
```
