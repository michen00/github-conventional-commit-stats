# Research: Conventional Commit Census

**Branch**: `001-initial-implementation` | **Date**: 2026-01-12

## Overview

This document captures technology decisions and research findings for the initial implementation of the Conventional Commit Census project.

---

## 1. HTTP Client Selection

**Decision**: httpx (synchronous mode)

**Rationale**:

- Aligns with AGENTS.md guidance: "Use `httpx` (sync) over `requests`"
- Modern API with type hints and context manager support
- Built-in timeout and retry support
- Connection pooling for repeated GitHub API calls

**Alternatives Considered**:

| Option   | Rejected Because                                               |
| -------- | -------------------------------------------------------------- |
| requests | Older API, less type support, guidance says use httpx          |
| aiohttp  | Async adds complexity; rate limits already throttle throughput |
| urllib3  | Too low-level for this use case                                |

---

## 2. Storage Layer Selection

**Decision**: TinyDB with JSON files

**Rationale**:

- Specified in Constitution constraints: "Storage: TinyDB (JSON)"
- No server required—files can be git-committed
- Simple document-based queries for run/repo lookups
- Python-native with zero configuration

**File Structure**:

```text
data/
├── runs.json       # Run metadata (TinyDB table: runs)
├── repos.json      # Repository records (TinyDB table: repos)
└── progress.json   # Progress checkpoints (TinyDB table: progress)
```

**Alternatives Considered**:

| Option     | Rejected Because                                     |
| ---------- | ---------------------------------------------------- |
| SQLite     | Requires binary file handling; harder to diff in git |
| PostgreSQL | Requires server; explicit non-goal per constitution  |
| Plain JSON | No query capability; TinyDB adds indexing            |

---

## 3. CLI Framework Selection

**Decision**: Typer with Rich

**Rationale**:

- Specified in AGENTS.md: "Use `typer` with `rich-argparse` for CLI"
- Type-hint based command definition
- Automatic `--help` generation
- Rich integration for colored output and progress bars

**Commands Designed**:

| Command    | Purpose                                |
| ---------- | -------------------------------------- |
| `collect`  | Discover repos and gather commit stats |
| `export`   | Generate visualization-ready JSON      |
| `validate` | Verify data integrity                  |
| `status`   | Show current progress/statistics       |
| `prune`    | Clean up old runs                      |

---

## 4. Conventional Commit Parsing

**Decision**: Regex-based parsing with strict lowercase matching

**Pattern**:

```regex
^(build|chore|ci|docs|feat|fix|perf|refactor|revert|style|test)(\([^)]*\))?!?: .+$
```

**Rationale**:

- Case-sensitive lowercase matches official conventional commits spec
- Space after colon required (per spec)
- Optional scope in parentheses, no nested parens allowed
- Optional `!` for breaking changes
- Simple regex is sufficient; no AST parsing needed

**Alternatives Considered**:

| Option                | Rejected Because                                          |
| --------------------- | --------------------------------------------------------- |
| Case-insensitive      | Conventional commits spec requires lowercase              |
| Full parser lib       | Over-engineering; regex is sufficient for type extraction |
| Angular commit format | Different format; we target standard conventional commits |

---

## 5. Bot Detection Strategy

**Decision**: Pattern matching against known bot usernames

**Pattern List** (case-insensitive):

```python
BOT_PATTERNS = [
    r"\[bot\]",                # Contains [bot] anywhere
    r"^dependabot",            # dependabot
    r"^renovate",              # renovate
    r"^github-actions",        # github-actions
    r"^pre-commit-ci",         # pre-commit-ci
    r"^semantic-release",      # semantic-release
    r"^snyk-",                 # snyk-bot
    r"^greenkeeper",           # greenkeeper
    r"^imgbot",                # imgbot
    r"^allcontributors",       # allcontributors
    r"^mergify",               # mergify
    r"^codecov",               # codecov
    r"^depfu",                 # depfu
    r"^whitesource-bolt",      # whitesource
    r"^mend-bolt",             # mend (formerly whitesource)
    r"^restyled-io",           # restyled
    r"^github-learning-lab",   # learning lab
    r"^release-please",        # release-please
]
```

**Rationale**:

- Covers ~95% of bot commits in popular repos
- Simple pattern matching is fast and maintainable
- List can be extended without code changes

---

## 6. Rate Limiting Strategy

**Decision**: Proactive sleep with header inspection

**Algorithm**:

1. After each response, check `X-RateLimit-Remaining`
2. If remaining < 10, calculate sleep time from `X-RateLimit-Reset`
3. Sleep proactively before next request
4. On 403/429, parse reset time and sleep with backoff

**Rate Limit Buckets**:

| Bucket                  | Limit     | Used For               |
| ----------------------- | --------- | ---------------------- |
| Search API              | 30/minute | Repository discovery   |
| Core API (PAT)          | 5000/hour | Commits, repo metadata |
| Core API (GITHUB_TOKEN) | 1000/hour | CI runner              |

**Alternatives Considered**:

| Option                | Rejected Because                                 |
| --------------------- | ------------------------------------------------ |
| Reactive only         | Violates Principle IV (proactive, not reactive)  |
| Fixed delays          | Inefficient; wastes time when limits are healthy |
| Secondary rate limits | Handled by exponential backoff on 403            |

---

## 7. Visualization Technology

**Decision**: Single HTML file with Plotly.js CDN

**Rationale**:

- Constitution constraint: "Frontend: Single HTML + Plotly.js CDN"
- No build step required
- Plotly.js has excellent accessibility support
- CDN delivery means no bundling needed

**Features**:

- Horizontal bar chart for commit type frequencies
- Interactive legend toggling
- Hover tooltips with counts and percentages
- Dark/light theme support via CSS custom properties
- Colorblind-safe IBM Design palette

### Animation Specifications

| Animation | Duration | Easing |
|-----------|----------|--------|
| Legend toggle (show/hide bar) | 250ms | ease-out |
| Hover highlight | 150ms | ease-in-out |
| Theme transition | 200ms | ease |
| Initial chart load | 400ms | ease-out |

### Theme Persistence

**localStorage Key**: `ccc-theme-preference`

**Values**:
- `"system"` - Follow system preference (default)
- `"dark"` - Force dark theme
- `"light"` - Force light theme

**Toggle Cycle**: system → dark → light → system

### Color Palette (IBM Design Language - Colorblind Safe)

| Commit Type | Light Theme | Dark Theme | Hex |
|-------------|-------------|------------|-----|
| feat | Blue 60 | Blue 50 | `#0043ce` / `#4589ff` |
| fix | Red 60 | Red 50 | `#da1e28` / `#fa4d56` |
| docs | Teal 60 | Teal 50 | `#007d79` / `#08bdba` |
| chore | Gray 60 | Gray 50 | `#6f6f6f` / `#8d8d8d` |
| refactor | Purple 60 | Purple 50 | `#8a3ffc` / `#a56eff` |
| test | Green 60 | Green 50 | `#198038` / `#42be65` |
| ci | Cyan 60 | Cyan 50 | `#0072c3` / `#33b1ff` |
| build | Magenta 60 | Magenta 50 | `#d02670` / `#ee5396` |
| style | Orange 60 | Orange 50 | `#ba4e00` / `#ff832b` |
| perf | Yellow 60 | Yellow 40 | `#b28600` / `#d2a106` |
| revert | Cool Gray 60 | Cool Gray 50 | `#4d5358` / `#697077` |

### Accessibility: Screen Reader Support

**Live Region Announcements** (using `aria-live="polite"`):

| Event | Announcement |
|-------|--------------|
| Chart loaded | "Commit type distribution chart loaded. {total} commits across {repos} repositories." |
| Legend item toggled ON | "{type} commits shown. {count} commits, {percent}% of total." |
| Legend item toggled OFF | "{type} commits hidden." |
| Theme changed | "Theme changed to {theme} mode." |
| Data load error | "Unable to load data. Please try again later." |

### Accessibility: Focus Management

| Interaction | Focus Behavior |
|-------------|----------------|
| Tab through legend | Focus moves to each legend item in order |
| Enter on legend item | Toggle visibility, focus remains on item |
| Escape on legend item | No action (focus remains) |
| Tab past last legend item | Focus moves to methodology section |
| After theme toggle | Focus remains on toggle button |

**Focus Indicators**: 2px solid outline using theme accent color, 2px offset

---

## 8. GitHub Search API Pagination Strategy

**Decision**: Star-range bucketing to bypass 1000-result limit

**Algorithm**:

```text
stars:10000..∞     → pages 1-10
stars:5000..10000  → pages 1-10
stars:1000..5000   → pages 1-10
stars:500..1000    → pages 1-10
stars:100..500     → pages 1-10
stars:3..100       → pages 1-10
```

**Rationale**:

- GitHub Search API limits to 1000 results per query
- Star-range bucketing allows accessing more repos
- Saves search cursor position for resumability

---

## 9. Pydantic Models Design

**Decision**: Use Pydantic v2 models for all data structures

**Models**:

| Model          | Purpose                                       |
| -------------- | --------------------------------------------- |
| `GitHubRepo`   | API response for repository                   |
| `GitHubCommit` | API response for commit                       |
| `Run`          | Run metadata stored in TinyDB                 |
| `RepoRecord`   | Per-repo commit counts                        |
| `Progress`     | Checkpoint state                              |
| `ExportData`   | Visualization JSON structure                  |
| `Settings`     | Environment configuration (pydantic-settings) |

**Rationale**:

- Type safety for API responses catches schema drift
- Validation at boundaries (API responses, file loading)
- pydantic-settings for `GITHUB_TOKEN` and `CCC_*` env vars

---

## 10. DataFrame Operations

**Decision**: Polars with Pandera validation

**Rationale**:

- AGENTS.md: "Prefer `polars` over `pandas` for data manipulation"
- Polars is faster for aggregation operations
- Pandera validates DataFrame schemas before export
- Used only for final aggregation in export command

**Operations**:

- Aggregate commit counts across all repos in a run
- Calculate percentages per commit type
- Generate export JSON with metadata

---

## Summary of Technology Stack

| Layer           | Technology          | Version    |
| --------------- | ------------------- | ---------- |
| Language        | Python              | ≥3.12      |
| Package Manager | uv                  | latest     |
| HTTP Client     | httpx               | ≥0.27      |
| Database        | TinyDB              | ≥4.8       |
| CLI Framework   | Typer               | ≥0.12      |
| Logging         | structlog           | ≥24.0      |
| Validation      | Pydantic            | ≥2.0       |
| Settings        | pydantic-settings   | ≥2.0       |
| DataFrames      | Polars + Pandera    | ≥1.0/≥0.25 |
| Testing         | pytest + pytest-cov | latest     |
| Frontend        | Plotly.js (CDN)     | latest     |
| CI/CD           | GitHub Actions      | v4         |

All technology choices align with Constitution constraints and AGENTS.md guidance.
