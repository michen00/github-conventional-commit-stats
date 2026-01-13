# github-conventional-commit-stats — Specification v1.0

**Conventional Commit Census**: A self-updating GitHub Pages site that visualizes the frequency of conventional commit types across popular public repositories.

---

## 0. Constitution

### Guiding Principles

1. **Test-Driven Development (TDD)** — Write tests BEFORE implementation; tests define the contract
2. **Simplicity over cleverness** — Prefer straightforward implementations; this is a demo project, not production infrastructure
3. **Resumability** — The collector MUST be interruptible and resumable; never lose progress
4. **Rate limit respect** — Never exceed GitHub API limits; sleep proactively, not reactively
5. **Data transparency** — Users should understand exactly how data was collected
6. **Accessibility first** — The visualization must be usable by everyone

### Non-Goals (Out of Scope)

- ❌ Real-time updates or streaming
- ❌ User authentication or personalization
- ❌ Database server (we commit JSON to git)
- ❌ Build step for frontend (single HTML file)
- ❌ GraphQL API (REST is sufficient for this scale)
- ❌ Private repository support
- ❌ Historical trend analysis (single snapshot per run)
- ❌ Per-language or per-topic breakdowns (future enhancement)

### Constraints

| Constraint       | Value                       | Rationale                           |
| ---------------- | --------------------------- | ----------------------------------- |
| Python version   | ≥3.12                       | Modern typing, `StrEnum`, `tomllib` |
| Max repos        | ~1000                       | Balances coverage vs. API budget    |
| Max commits/repo | 100                         | Sufficient sample, limits API calls |
| Time window      | 1 year                      | Recent activity only                |
| Storage          | TinyDB (JSON)               | No server, git-committed            |
| Frontend         | Single HTML + Plotly.js CDN | No build step                       |
| CI runtime       | ≤6 hours                    | GitHub Actions limit                |

### Tech Stack

| Layer           | Technology                    | Version    |
| --------------- | ----------------------------- | ---------- |
| Language        | Python                        | ≥3.12      |
| Package manager | uv                            | latest     |
| HTTP client     | httpx                         | ≥0.27      |
| Database        | TinyDB                        | ≥4.8       |
| CLI framework   | Typer                         | ≥0.12      |
| Logging         | structlog                     | ≥24.0      |
| Validation      | Pydantic                      | ≥2.0       |
| Settings        | pydantic-settings             | ≥2.0       |
| DataFrames      | Polars + Pandera              | ≥1.0/≥0.25 |
| Linting         | ruff (via pre-commit)         | latest     |
| Type checking   | mypy (strict, via pre-commit) | latest     |
| Testing         | pytest + pytest-cov           | latest     |
| Frontend        | Plotly.js (CDN)               | latest     |
| CI/CD           | GitHub Actions                | v4 actions |

### Success Criteria

- [ ] Tests written BEFORE implementation (TDD)
- [ ] `make check` passes (lint, type check, tests)
- [ ] Test coverage ≥80% for `src/conv_commit_stats/`
- [ ] `conv-commit-stats collect --max-repos 10` completes without error
- [ ] `conv-commit-stats export` produces valid `docs/data.json`
- [ ] `docs/index.html` renders chart with real data
- [ ] CI workflow runs end-to-end on manual trigger
- [ ] Visualization is keyboard-navigable and passes WCAG AA contrast

---

## 1. Data Collection

### 1.1 Repository Discovery

Use GitHub Search API (via `gh search repos` or REST) with these filters:

| Filter      | Value         | API Qualifier                |
| ----------- | ------------- | ---------------------------- |
| Stars       | ≥3            | `stars:>=3`                  |
| Pushed      | within 1 year | `pushed:>{YYYY-MM-DD}`       |
| Archived    | false         | `archived:false`             |
| Fork        | false         | `--include-forks=false`      |
| Visibility  | public        | `visibility:public`          |
| Has license | true          | `license:*` (or post-filter) |
| Size        | >0            | `size:>0`                    |

**JSON fields to capture:**

```
fullName, defaultBranch, stargazersCount, language,
createdAt, pushedAt, license, isDisabled, size
```

**Post-fetch filters** (require API call per repo):

- `isDisabled: false`
- Total commits on default branch ≥ 100 (check via commits endpoint pagination)

**Target:** ~1000 qualifying repositories

### 1.2 Commit Analysis

For each qualifying repo, fetch commits from default branch:

```bash
GET /repos/{owner}/{repo}/commits
  ?sha={default_branch}
  &since={one_year_ago_iso}
  &per_page=100
```

**Pagination:** Fetch up to **500 commits** max (5 pages × 100/page).

**Filtering pipeline** (client-side, per commit):

1. Skip merge commits (check `parents.length > 1`)
2. Skip empty commits (commit with no file changes — rare, but skip if `stats.total == 0`)
3. Skip bot authors (see §1.4)
4. Check if message matches conventional commit pattern
5. Stop after collecting **100 conventional commits** from non-bot authors

### 1.3 Conventional Commit Pattern

```regex
^(build|chore|ci|docs|feat|fix|perf|refactor|revert|style|test)(\([^)]*\))?!?: .*$
```

- **Case sensitive** — only lowercase prefixes
- **Space required** — a space must follow the colon (e.g., `feat:` is valid, `feat:` is not)
- **Description** — may be empty after the required space (e.g., `feat:` matches)
- **Scope** — optional, may not contain `)`
- **Breaking indicator** — `!` is optional

**Captured group:** First match group is the commit type.

### 1.4 Bot Detection (Ignorelist)

Flag as bot if `commit.author.login` or `commit.author.name` matches any:

```python
BOT_PATTERNS = [
    r"\[bot\]",                # contains [bot] anywhere (covers suffix case too)
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

Use `re.IGNORECASE` for all patterns.

### 1.5 Restart Strategy

**Skip-if-processed:** If `repos` table contains a record for the repo in the current run, skip entirely.

To force full refresh: clear progress and start new run.

**Progress checkpointing:**

- Save search cursor after each search page
- Save last processed repo after each repo completes
- On restart, resume from saved cursor/repo

#### Checkpoint Flow

```
┌─────────────────────────────────────────────────────────────────┐
│  Phase 1: SEARCH (discover repos via GitHub Search API)        │
│  ─────────────────────────────────────────────────────────────  │
│  GitHub Search paginates by star ranges to bypass 1000 limit:  │
│                                                                 │
│    stars:10000..∞     → pages 1-10  ✓ done                     │
│    stars:5000..10000  → pages 1-10  ✓ done                     │
│    stars:1000..5000   → pages 1-10  ✓ done                     │
│    stars:500..1000    → page 1 ✓, page 2 ✓, page 3 ← INTERRUPT │
│                                            ↑                    │
│                              search_cursor saved here           │
│                              {"stars_range": "500..1000",       │
│                               "page": 3}                        │
├─────────────────────────────────────────────────────────────────┤
│  Phase 2: COLLECT (fetch commits for each discovered repo)     │
│  ─────────────────────────────────────────────────────────────  │
│  Process repos sequentially (atomic: all-or-nothing per repo): │
│                                                                 │
│    ✓ facebook/react     → saved to repos.json                  │
│    ✓ microsoft/vscode   → saved to repos.json                  │
│    ✓ golang/go          → saved to repos.json                  │
│    ◯ rust-lang/rust     ← INTERRUPT (partial, NOT saved)       │
│                    ↑                                            │
│       last_repo = "golang/go" (last COMPLETED repo)            │
│       rust-lang/rust will be re-fetched on resume              │
└─────────────────────────────────────────────────────────────────┘
```

#### `progress.json` Schema

| Key             | Type                  | Purpose                       | Updated When           |
| --------------- | --------------------- | ----------------------------- | ---------------------- |
| `search_cursor` | `{stars_range, page}` | Bookmark in search pagination | After each search page |
| `last_repo`     | `string` (fullName)   | Last fully-processed repo     | After each repo saved  |
| `run_id`        | `string`              | Current run identifier        | At run start           |

**Example `progress.json`:**

```json
{
  "progress": {
    "1": {
      "key": "run_id",
      "value": "run_2025-01-12T04:00:00Z",
      "updated_at": "2025-01-12T04:00:00Z"
    },
    "2": {
      "key": "search_cursor",
      "value": { "stars_range": "500..1000", "page": 3 },
      "updated_at": "2025-01-12T04:15:00Z"
    },
    "3": {
      "key": "last_repo",
      "value": "golang/go",
      "updated_at": "2025-01-12T04:45:00Z"
    }
  }
}
```

#### Resume Behavior (`--resume`)

1. **Load `progress.json`** — Get `run_id`, `search_cursor`, `last_repo`
2. **Resume search** — If `search_cursor` exists, skip to that star range and page
3. **Skip processed repos** — Query `repos.json` for all repos with matching `run_id`; skip those
4. **Continue from last_repo** — Start processing from the repo AFTER `last_repo`
5. **Normal collection** — Process remaining repos, update checkpoints as usual

**Key invariant:** A repo is either fully saved or not saved at all. No partial repo data.

---

## 2. Rate Limiting

### 2.1 Rate Limit Buckets

| Bucket                  | Limit           | Resets       | Used For               |
| ----------------------- | --------------- | ------------ | ---------------------- |
| Search API              | 30/minute       | Every minute | Repo discovery         |
| Core API (PAT)          | 5,000/hour      | Hourly       | Repo metadata, commits |
| Core API (GITHUB_TOKEN) | 1,000/hour/repo | Hourly       | CI runner              |

**Recommendation:** Use a PAT stored as repository secret for faster runs.

### 2.2 Request Budget Estimation

For 1000 repos with 500 commits each:

| Phase   | Requests | Rate Limit             | Time   |
| ------- | -------- | ---------------------- | ------ |
| Search  | ~50      | 30/min                 | ~2 min |
| Commits | ~5000    | 5000/hr (PAT)          | ~1 hr  |
| Commits | ~5000    | 1000/hr (GITHUB_TOKEN) | ~5 hr  |

**Monthly schedule makes even 5hr runs acceptable.**

### 2.3 Rate Limit Handling

> **Reference implementation** — Adapt as needed.

```python
def handle_response(response: httpx.Response) -> None:
    remaining = int(response.headers.get("X-RateLimit-Remaining", 1))
    reset_at = int(response.headers.get("X-RateLimit-Reset", 0))
    resource = response.headers.get("X-RateLimit-Resource", "core")

    if remaining < 10:
        wait = max(0, reset_at - time.time()) + 5
        log.warning(f"{resource} rate limit low ({remaining}), sleeping {wait:.0f}s")
        time.sleep(wait)
```

### 2.4 Retry Strategy

**Exponential backoff with jitter:**

> **Reference implementation** — Adapt as needed.

```python
MAX_RETRIES = 5
BASE_DELAY = 1.0

for attempt in range(MAX_RETRIES):
    response = client.request(...)

    if response.status_code == 200:
        return response.json()

    if response.status_code in (403, 429):
        # Rate limited
        if "rate limit" in response.text.lower():
            handle_rate_limit_response(response)
            continue

    if response.status_code >= 500:
        # Server error, retry
        delay = BASE_DELAY * (2 ** attempt) + random.uniform(0, 1)
        time.sleep(delay)
        continue

    # Client error (4xx except 403/429), don't retry
    response.raise_for_status()

raise MaxRetriesExceeded()
```

### 2.5 Graceful Interruption

On `SIGINT`/`SIGTERM`:

1. Finish current repo (don't leave partial data)
2. Save progress cursor to `progress.json`
3. Exit code 0 (allows CI to treat as success for resume)

---

## 3. Storage Schema (TinyDB)

### 3.1 File Structure

```
data/
├── runs.json       # Run metadata
├── repos.json      # Per-repo commit counts
└── progress.json   # Resume checkpoints
```

Add to `.gitattributes`:

```gitattributes
# Treat TinyDB files as generated (no diff/merge conflicts)
data/*.json -diff -merge linguist-generated
```

### 3.2 Schemas

**runs.json:**

```json
{
  "_default": {},
  "runs": {
    "1": {
      "run_id": "run_2025-01-12T04:00:00Z",
      "started_at": "2025-01-12T04:00:00Z",
      "completed_at": "2025-01-12T05:15:00Z",
      "status": "completed",
      "repos_processed": 1000,
      "repos_qualified": 847,
      "total_commits_analyzed": 84700
    }
  }
}
```

**repos.json:**

```json
{
  "_default": {},
  "repos": {
    "1": {
      "run_id": "run_2025-01-12T04:00:00Z",
      "repo": "facebook/react",
      "default_branch": "main",
      "head_commit": "abc123def456",
      "stars": 220000,
      "language": "JavaScript",
      "created_at": "2013-05-24T16:15:54Z",
      "license": "MIT",
      "timestamp": "2025-01-12T04:02:15Z",
      "commits_analyzed": 100,
      "build": 12,
      "chore": 8,
      "ci": 5,
      "docs": 15,
      "feat": 25,
      "fix": 18,
      "perf": 3,
      "refactor": 7,
      "revert": 1,
      "style": 2,
      "test": 4
    }
  }
}
```

**progress.json:**

```json
{
  "_default": {},
  "progress": {
    "1": {
      "key": "run_id",
      "value": "run_2025-01-12T04:00:00Z",
      "updated_at": "2025-01-12T04:00:00Z"
    },
    "2": {
      "key": "search_cursor",
      "value": { "stars_range": "100..500", "page": 3 },
      "updated_at": "2025-01-12T04:15:00Z"
    },
    "3": {
      "key": "last_repo",
      "value": "facebook/react",
      "updated_at": "2025-01-12T04:45:00Z"
    }
  }
}
```

### 3.3 Retention Policy

**Keep only the 3 most recent completed runs.**

On run completion:

1. Mark run as `completed`
2. Query runs, sort by `started_at` descending
3. Delete runs beyond the 3rd oldest
4. Delete associated repo records from `repos.json`

Historical data is preserved in git history.

---

## 4. CLI Interface (Typer)

```bash
# Full collection run
uv run conv-commit-stats collect \
  --max-repos 1000 \
  --min-stars 3

# Resume interrupted run
uv run conv-commit-stats collect --resume

# Export aggregated data for visualization
uv run conv-commit-stats export \
  --run latest \
  --output docs/data.json

# Prune old runs (keep N most recent)
uv run conv-commit-stats prune --keep 3

# Validate data integrity
uv run conv-commit-stats validate

# Show current progress/stats
uv run conv-commit-stats status
```

**Environment variables:**

- `GITHUB_TOKEN` — Required. PAT or Actions token.
- `CCC_DB_PATH` — Optional. Override data directory path.

**Common options** (available on all commands):

- `--db-path PATH` — Override data directory (same as `CCC_DB_PATH` env var)

### 4.1 Dependencies

**Core dependencies** (add to `pyproject.toml`):

```toml
dependencies = [
    "httpx>=0.27.0",           # HTTP client with async support
    "tinydb>=4.8.0",           # Document-oriented database
    "typer>=0.12.0",           # CLI framework
    "rich>=13.0.0",            # Terminal formatting
    "structlog>=24.0.0",       # Structured logging
    "pydantic>=2.0",           # Data validation & API response models
    "pydantic-settings>=2.0",  # Type-safe settings & env var management
    "pandera[polars]>=0.25.0", # Schema validation for DataFrames
    "polars>=1.0.0",           # Fast DataFrame library for aggregation
]
```

> **Why these validation libraries:**
>
> - **Pydantic** — Type-safe models for GitHub API responses (`Repo`, `Commit`, `Run`). Catches schema drift.
> - **Pydantic-settings** — Manages `CCC_*` env vars and `GITHUB_TOKEN` with validation and `.env` support.
> - **Pandera + Polars** — Schema-validated DataFrames for aggregating commit counts and exporting `data.json`.

### 4.2 Entry Point

Add to `pyproject.toml`:

```toml
[project.scripts]
conv-commit-stats = "conv_commit_stats.cli:app"
```

---

## 5. Visualization

### 5.1 Tech Stack

Single HTML file with:

- **Plotly.js** (CDN) — interactive charting
- **Vanilla JS** — state & interactions
- **CSS custom properties** — theming & palette

No build step. Direct GitHub Pages deployment.

### 5.2 Features

**Primary view:** Horizontal bar chart of commit type frequencies (aggregated)

**Interactions:**

- Toggle individual commit types on/off (click legend)
- Hover for exact counts and percentages
- Animated transitions between states (200-300ms ease-out)

**Theming:**

- Respect `prefers-color-scheme` (system default first)
- Manual toggle: system → dark → light → system
- Persist preference in `localStorage`

### 5.3 Color Palette

Use CSS custom properties referencing a palette, not hardcoded hex values:

```css
:root {
  /* IBM Design colorblind-safe palette */
  --palette-purple: #6929c4;
  --palette-cyan: #1192e8;
  --palette-teal: #005d5d;
  --palette-magenta: #9f1853;
  --palette-red: #fa4d56;
  --palette-maroon: #570408;
  --palette-green: #198038;
  --palette-blue: #002d9c;
  --palette-pink: #ee538b;
  --palette-gold: #b28600;
  --palette-orange: #8a3800;

  /* Semantic mapping */
  --color-feat: var(--palette-purple);
  --color-fix: var(--palette-cyan);
  --color-docs: var(--palette-teal);
  --color-style: var(--palette-magenta);
  --color-refactor: var(--palette-red);
  --color-test: var(--palette-maroon);
  --color-chore: var(--palette-green);
  --color-ci: var(--palette-blue);
  --color-build: var(--palette-pink);
  --color-perf: var(--palette-gold);
  --color-revert: var(--palette-orange);
}
```

### 5.4 Accessibility

- Colorblind-safe palette (IBM Design Language)
- ARIA labels on all interactive elements
- Keyboard navigation (tab through legend, Enter to toggle)
- Sufficient contrast (WCAG AA minimum)
- Screen reader announcements on state changes

### 5.5 Methodology Section

Display on page:

- **Sample:** ~N repositories with ≥3 stars, active in last year, licensed, non-fork, non-archived
- **Commits analyzed:** Up to 100 most recent conventional commits per repo (from last year)
- **Exclusions:** Bot authors (pattern-matched), merge commits, non-conventional messages
- **Last updated:** {timestamp from latest run}
- **Total commits analyzed:** {aggregate count}
- **Source code:** Link to repository

---

## 6. CI/CD (GitHub Actions)

### 6.1 Scheduled Collection

```yaml
# .github/workflows/collect.yml
name: Collect Stats

on:
  schedule:
    - cron: "0 4 1 * *" # Monthly, 1st at 04:00 UTC
  workflow_dispatch: # Manual trigger

jobs:
  collect:
    runs-on: ubuntu-latest
    timeout-minutes: 360 # 6 hours max

    steps:
      - uses: actions/checkout@v6

      - name: Install uv
        uses: astral-sh/setup-uv@v4

      - name: Collect stats
        env:
          GITHUB_TOKEN: ${{ secrets.GH_PAT }} # Use PAT for higher rate limit
        run: |
          uv run conv-commit-stats collect --max-repos 1000
          uv run conv-commit-stats prune --keep 3
          uv run conv-commit-stats export --output docs/data.json

      - name: Commit and push
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add data/ docs/data.json
          git diff --staged --quiet || git commit -m "chore: update conventional commit stats [skip ci]"
          git push
```

### 6.2 Validation on Push (with Auto-Revert)

```yaml
# .github/workflows/validate.yml
name: Validate

on:
  push:
    branches: [main]
    paths:
      - "data/**"
      - "docs/**"

jobs:
  validate:
    runs-on: ubuntu-latest
    # Skip if this is a revert commit (git revert produces "Revert ..." messages)
    if: "!startsWith(github.event.head_commit.message, 'Revert')"

    steps:
      - uses: actions/checkout@v6
        with:
          fetch-depth: 2 # Need parent for revert

      - name: Install uv
        uses: astral-sh/setup-uv@v4

      - name: Validate data
        id: validate
        run: |
          uv run conv-commit-stats validate
          uv run python -c "import json; d=json.load(open('docs/data.json')); assert d['total_commits'] > 0"
          test -f docs/index.html

      - name: Revert on failure
        if: failure()
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git revert --no-edit HEAD
          git push
```

### 6.3 GitHub Pages Deployment

```yaml
# .github/workflows/pages.yml
name: Deploy Pages

on:
  push:
    branches: [main]
    paths: ["docs/**"]
  workflow_run:
    workflows: ["Validate"]
    types: [completed]
    branches: [main]

permissions:
  pages: write
  id-token: write

jobs:
  deploy:
    runs-on: ubuntu-latest
    if: ${{ github.event_name == 'push' || github.event.workflow_run.conclusion == 'success' }}
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}

    steps:
      - uses: actions/checkout@v6

      - uses: actions/configure-pages@v4

      - uses: actions/upload-pages-artifact@v3
        with:
          path: docs/

      - id: deployment
        uses: actions/deploy-pages@v4
```

---

## 7. Project Structure

### 7.1 Naming Convention

| Context              | Name                               | Notes                               |
| -------------------- | ---------------------------------- | ----------------------------------- |
| Repository           | `github-conventional-commit-stats` | GitHub repo name                    |
| PyPI distribution    | `github-conventional-commit-stats` | `pip install ...`                   |
| Python module        | `conv_commit_stats`                | `from conv_commit_stats import ...` |
| CLI command          | `conv-commit-stats`                | `uv run conv-commit-stats ...`      |
| Environment variable | `CCC_*`                            | Prefix for config vars              |

### 7.2 Directory Layout

```
github-conventional-commit-stats/
├── .github/
│   └── workflows/
│       ├── collect.yml       # Scheduled data collection
│       ├── validate.yml      # Post-push validation + auto-revert
│       ├── pages.yml         # GitHub Pages deployment
│       └── ci.yml            # PR checks (lint, test)
├── data/
│   ├── runs.json             # Run metadata (TinyDB)
│   ├── repos.json            # Per-repo counts (TinyDB)
│   └── progress.json         # Resume checkpoints (TinyDB)
├── docs/
│   ├── index.html            # Visualization page
│   └── data.json             # Exported data for frontend
├── src/
│   └── conv_commit_stats/
│       ├── __init__.py
│       ├── __main__.py       # Entry point
│       ├── cli.py            # Typer CLI commands
│       ├── collector.py      # GitHub API + collection orchestration
│       ├── github_client.py  # HTTP client with rate limiting
│       ├── parsing.py        # Pure functions: regex, bot detection
│       ├── py.typed          # PEP 561 marker
│       └── storage.py        # TinyDB wrapper for 3 tables
├── tests/
│   ├── __init__.py
│   ├── conftest.py           # Fixtures
│   ├── test_parsing.py       # Unit tests for pure functions
│   ├── test_storage.py       # Storage layer tests
│   ├── test_github_client.py # Mocked API tests
│   └── test_cli_smoke.py     # E2E smoke test
├── pyproject.toml
├── .pre-commit-config.yaml
├── .gitattributes
├── .ruff.toml
└── README.md
```

---

## 8. Testing Strategy

### 8.0 TDD Workflow (Required)

> **⚠️ IMPORTANT:** This project follows strict Test-Driven Development. Tests are written BEFORE implementation.

**The Red-Green-Refactor Cycle:**

1. **RED** — Write a failing test that defines expected behavior
2. **GREEN** — Write the minimum code to make the test pass
3. **REFACTOR** — Clean up while keeping tests green

**Implementation Order (per module):**

```
1. Create test file (e.g., tests/test_parsing.py)
2. Write test cases from spec (copy from §8.1-8.4)
3. Run tests → they should FAIL (no implementation yet)
4. Create implementation file (e.g., src/conv_commit_stats/parsing.py)
5. Implement until tests pass
6. Refactor if needed, ensure tests stay green
7. Run `make check` before moving to next module
```

**Benefits for this project:**

- Tests in this spec serve as **executable documentation**
- Pure functions (`parsing.py`) are ideal TDD candidates
- Mocked HTTP tests ensure rate limiting works without hitting API
- Prevents regressions when refactoring

### 8.1 Unit Tests (`tests/test_parsing.py`)

```python
import pytest
from conv_commit_stats.parsing import is_conventional_commit, extract_type, is_bot

class TestConventionalCommit:
    @pytest.mark.parametrize("message,expected", [
        ("feat: add login", True),
        ("feat(auth): add login", True),
        ("feat(auth)!: breaking change", True),
        ("feat: ", True),              # space required, empty desc OK
        ("feat:", False),              # missing required space
        ("Feat: capitalized", False),  # case sensitive
        ("FEAT: uppercase", False),
        ("feature: wrong prefix", False),
        ("feat add login", False),     # missing colon
        ("feat:no space", False),      # missing space after colon
        ("feat(nested(paren)): bad", False),  # nested parens
        ("fix(scope: broken): msg", False),   # unbalanced
    ])
    def test_is_conventional_commit(self, message, expected):
        assert is_conventional_commit(message) == expected

    @pytest.mark.parametrize("message,expected_type", [
        ("feat: add login", "feat"),
        ("fix(auth): bug", "fix"),
        ("docs: update readme", "docs"),
        ("not conventional", None),
    ])
    def test_extract_type(self, message, expected_type):
        assert extract_type(message) == expected_type


class TestBotDetection:
    @pytest.mark.parametrize("author,expected", [
        ("dependabot[bot]", True),
        ("renovate[bot]", True),
        ("pre-commit-ci[bot]", True),
        ("github-actions[bot]", True),
        ("semantic-release-bot", True),
        ("snyk-bot", True),
        ("jane-doe", False),
        ("botman", False),        # doesn't match patterns
        ("robot-team", False),    # doesn't match patterns
        ("my-bot-helper", False), # "bot" in middle, no brackets
    ])
    def test_is_bot(self, author, expected):
        assert is_bot(author) == expected
```

### 8.2 Storage Tests (`tests/test_storage.py`)

- CRUD operations on all three tables
- Retention policy (keep 3 runs)
- Progress checkpointing
- Export format validation
- Concurrent access safety (not critical for single-process)

### 8.3 GitHub Client Tests (`tests/test_github_client.py`)

- Mock HTTP responses
- Rate limit header parsing
- Retry logic
- Pagination handling

### 8.4 E2E Smoke Test (`tests/test_cli_smoke.py`)

```python
import json
import os
from pathlib import Path

import pytest
from typer.testing import CliRunner

from conv_commit_stats.cli import app

runner = CliRunner()


@pytest.mark.skipif(
    not os.environ.get("GITHUB_TOKEN"),
    reason="GITHUB_TOKEN required for E2E test"
)
def test_collect_smoke(tmp_path: Path):
    """Collect from a small set of repos, verify data written."""
    result = runner.invoke(app, [
        "collect",
        "--max-repos", "5",
        "--min-stars", "10000",  # high stars = stable repos
        "--db-path", str(tmp_path),
    ])

    assert result.exit_code == 0
    assert (tmp_path / "runs.json").exists()
    assert (tmp_path / "repos.json").exists()

    # Validate export
    export_path = tmp_path / "data.json"
    result = runner.invoke(app, [
        "export",
        "--output", str(export_path),
        "--db-path", str(tmp_path),
    ])

    assert result.exit_code == 0
    data = json.loads(export_path.read_text())
    assert data["total_repos"] > 0
    assert data["total_commits"] > 0
    assert "counts" in data
    assert all(k in data["counts"] for k in [
        "feat", "fix", "docs", "chore", "refactor",
        "test", "ci", "build", "style", "perf", "revert"
    ])
```

---

## 9. Additional Metadata

Per-repo metadata captured (free from repo object):

| Field        | Type     | Notes                   |
| ------------ | -------- | ----------------------- |
| `stars`      | int      | For weighting/filtering |
| `language`   | string   | Primary language        |
| `created_at` | datetime | Repo age                |
| `license`    | string   | License SPDX ID         |
| `pushed_at`  | datetime | Last activity           |

These require no extra API calls and enable future analysis (e.g., "do Python repos have more `test` commits?").

---

## 10. Open Items / Future Enhancements

- [ ] Language breakdown visualization
- [ ] Topic-based filtering
- [ ] Time series across multiple runs (if we query historical data)
- [ ] RSS/Atom feed of updates
- [ ] GraphQL API for more efficient queries (single request for repo + commits)
- [ ] Support for private repos (with appropriate scopes)
- [ ] Configurable time window (currently 1 year; original concept was 5 years)

---

## Appendix A: GitHub API Endpoints Used

| Endpoint                            | Purpose        | Rate Limit Bucket    |
| ----------------------------------- | -------------- | -------------------- |
| `GET /search/repositories`          | Discover repos | Search (30/min)      |
| `GET /repos/{owner}/{repo}`         | Repo metadata  | Core (5000/hr)       |
| `GET /repos/{owner}/{repo}/commits` | Commit history | Core (5000/hr)       |
| `GET /rate_limit`                   | Check limits   | Core (doesn't count) |

---

## Appendix B: gh CLI Equivalents

```bash
# Search repos
gh search repos \
  --stars=">=3" \
  --updated=">$(date -d '1 year ago' +%Y-%m-%d)" \
  --archived=false \
  --include-forks=false \
  --visibility=public \
  --license="*" \
  --limit=100 \
  --json fullName,defaultBranch,stargazersCount,language,license,isDisabled,size

# List commits (no direct gh command, use API)
gh api repos/{owner}/{repo}/commits \
  --paginate \
  -q '.[] | {sha, message: .commit.message, author: .author.login}'
```

---

## Appendix C: Validation Checks

The `validate` command should verify:

1. **Schema validity:** All JSON files parse correctly
2. **Referential integrity:** All repos reference existing runs
3. **Data sanity:**
   - No negative counts
   - Counts sum to reasonable totals
   - Timestamps are valid ISO format
   - Run IDs are unique
4. **Export validity:**
   - `docs/data.json` exists and parses
   - Contains expected keys
   - `total_commits > 0`

---

## Appendix D: Implementation Hints

> **Note for AI agents:** This section provides guidance for implementation planning.

### Module Dependency Order (TDD: Tests First)

```
# For each module: write test file FIRST, then implementation

tests/test_parsing.py       → then → parsing.py        (no deps, pure functions)
tests/test_storage.py       → then → storage.py        (no deps, TinyDB wrapper)
tests/test_github_client.py → then → github_client.py  (no deps, HTTP + rate limiting)
tests/test_collector.py     → then → collector.py      (depends: parsing, storage, github_client)
tests/test_cli_smoke.py     → then → cli.py            (depends: collector, storage)
                                   → __main__.py       (just imports cli)
```

### Pure Functions (TDD Priority)

> **Write `tests/test_parsing.py` FIRST**, then implement these functions:

| Function                 | Signature                       | Test Cases      |
| ------------------------ | ------------------------------- | --------------- |
| `is_conventional_commit` | `(message: str) -> bool`        | §8.1 (12 cases) |
| `extract_type`           | `(message: str) -> str \| None` | §8.1 (4 cases)  |
| `is_bot`                 | `(author: str) -> bool`         | §8.1 (10 cases) |

These are ideal TDD candidates: pure functions with no side effects, behavior fully specified by test cases.

### Existing Project Structure

This repo uses a template with existing tooling:

- `Makefile` — Use `make check`, `make test`, `make format`
- `.ruff.toml` — Linting config exists
- `pyproject.toml` — Add dependencies here, entry point in `[project.scripts]`
- `src/conv_commit_stats/` — Package already exists with correct naming

### Code Style Preferences

- Use `pathlib.Path` over `os.path`
- Use `httpx` (sync) over `requests`
- Use `structlog` for logging
- Use `typer` with `rich` for CLI
- Use `__slots__` where beneficial
- **Pydantic models** — Define `Repo`, `Commit`, `Run` models for API responses and storage
- **Pydantic-settings** — Use `BaseSettings` for `CCC_*` env vars (not `os.environ.get()`)
- **Polars + Pandera** — Use for aggregation and export; validate DataFrames before writing

### Testing Approach (TDD Required)

> **⚠️ Write tests BEFORE implementation. This is non-negotiable.**

**Per-module workflow:**

| Step | Action                                     | Verification          |
| ---- | ------------------------------------------ | --------------------- |
| 1    | Create `tests/test_<module>.py`            | File exists           |
| 2    | Copy test cases from spec (§8.1-8.4)       | Tests written         |
| 3    | Run `make test`                            | Tests FAIL (expected) |
| 4    | Create `src/conv_commit_stats/<module>.py` | File exists           |
| 5    | Implement functions                        | Tests PASS            |
| 6    | Run `make check`                           | All checks pass       |

**Testing specifics:**

1. **Pure functions first** — `parsing.py` has zero dependencies, ideal for TDD
2. **Mock HTTP** — Use `pytest` fixtures with `httpx.MockTransport`
3. **E2E smoke test** — Skip in CI unless `GITHUB_TOKEN` is set
4. **No snapshot testing** — API responses change too frequently

**Example TDD flow for `parsing.py`:**

```bash
# Step 1-2: Create test file with cases from spec
# Step 3: Run tests (should fail)
uv run pytest tests/test_parsing.py -v
# → FAILED (ImportError: No module named 'conv_commit_stats.parsing')

# Step 4-5: Create parsing.py, implement functions
# Step 6: Run again
uv run pytest tests/test_parsing.py -v
# → PASSED

make check  # Ensure lint + types + all tests pass
```
