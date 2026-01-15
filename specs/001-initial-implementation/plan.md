# Implementation Plan: Conventional Commit Census

**Branch**: `001-initial-implementation` | **Date**: 2026-01-12 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-initial-implementation/spec.md`

## Summary

Build a self-updating GitHub Pages site that visualizes conventional commit type frequencies across ~1000 popular public repositories. The system consists of:

1. **CLI tool** (Python) for collecting commit data from GitHub API with resumable progress
2. **TinyDB storage** (JSON files) for persisting run data, repository records, and checkpoints
3. **Static visualization** (single HTML file with Plotly.js) deployed to GitHub Pages
4. **CI automation** (GitHub Actions) for monthly data collection and deployment

Technical approach follows TDD methodology with pure functions for parsing, isolated modules for GitHub API interaction, and atomic checkpoint saves for resumability.

## Technical Context

**Language/Version**: Python ≥3.12 (modern typing, StrEnum, tomllib)
**Primary Dependencies**: httpx (HTTP client), TinyDB (JSON storage), Typer (CLI), structlog (logging), Pydantic (validation), Polars + Pandera (DataFrame operations)
**Parsing Functions**: The parsing module includes `parse_breaking()` and `parse_has_scope()` functions to extract breaking change indicators and scopes from commit messages
**Storage**: TinyDB (JSON files committed to git): `data/runs.json`, `data/repos.json`, `data/progress.json`
**Testing**: pytest + pytest-cov (≥80% coverage required)
**Target Platform**: GitHub Actions (Ubuntu), GitHub Pages (static hosting)
**Project Type**: Single Python package + static HTML frontend
**Performance Goals**: Process 1000 repos in ≤6 hours, page load <5 seconds
**Constraints**: GitHub API rate limits (5000/hr PAT, 1000/hr GITHUB_TOKEN), 6-hour CI timeout
**Scale/Scope**: ~1000 repositories, 100 commits/repo, 3 runs retained

## Constitution Check

_GATE: Must pass before Phase 0 research. Re-check after Phase 1 design._

| Principle                   | Compliance | Evidence                                                                   |
| --------------------------- | ---------- | -------------------------------------------------------------------------- |
| **I. TDD**                  | ✅ Pass    | Tests written before implementation per spec §8.0; coverage ≥80% in SC-004 |
| **II. Simplicity**          | ✅ Pass    | Single package structure, TinyDB (no server), single HTML (no build step)  |
| **III. Resumability**       | ✅ Pass    | FR-006, FR-007 mandate checkpointing and SIGINT handling                   |
| **IV. Rate Limit Respect**  | ✅ Pass    | FR-008, FR-009, FR-010 define proactive rate limiting                      |
| **V. Data Transparency**    | ✅ Pass    | FR-023, US4 require methodology disclosure on visualization                |
| **VI. Accessibility First** | ✅ Pass    | FR-024 to FR-027 mandate colorblind-safe palette, WCAG AA, keyboard nav    |

**Gate Status**: ✅ PASSED — All 6 principles satisfied. Proceed to Phase 0.

## Project Structure

### Documentation (this feature)

```text
specs/001-initial-implementation/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (CLI interface spec)
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code (repository root)

```text
src/
└── conv_commit_stats/
    ├── __init__.py          # Package exports
    ├── __main__.py          # Entry point (uv run conv-commit-stats)
    ├── cli.py               # Typer CLI commands
    ├── collector.py         # GitHub API orchestration
    ├── github_client.py     # HTTP client with rate limiting
    ├── parsing.py           # Pure functions: regex, bot detection
    ├── storage.py           # TinyDB wrapper for 3 tables
    └── py.typed             # PEP 561 marker

tests/
├── __init__.py
├── conftest.py              # Shared fixtures
├── test_parsing.py          # Unit tests for pure functions
├── test_storage.py          # Storage layer tests
├── test_github_client.py    # Mocked API tests
├── test_collector.py        # Collector orchestration tests
└── test_cli_smoke.py        # E2E smoke test (requires GITHUB_TOKEN)

data/
├── runs.json                # Run metadata (TinyDB)
├── repos.json               # Per-repo commit counts (TinyDB)
└── progress.json            # Resume checkpoints (TinyDB)

docs/
├── index.html               # Visualization page (single file)
└── data.json                # Exported data for frontend
```

**Structure Decision**: Single Python package (`src/conv_commit_stats/`) following existing repo layout. No separate frontend build—static HTML with CDN-loaded Plotly.js. Data stored in `data/` directory as TinyDB JSON files.

## Complexity Tracking

> No violations. All choices align with Constitution Principle II (Simplicity).

| Choice                | Justification                                                  |
| --------------------- | -------------------------------------------------------------- |
| TinyDB over SQLite    | JSON files can be git-committed; no database server needed     |
| Single HTML over SPA  | No build step; direct GitHub Pages deployment                  |
| Sync httpx over async | Simpler debugging; rate limits already throttle throughput     |
| Polars over pandas    | Faster aggregation; better type support; aligns with AGENTS.md |

## Module Dependency Order

```text
# TDD: Write test file FIRST, then implementation

tests/test_parsing.py       → parsing.py        # No deps, pure functions
tests/test_storage.py       → storage.py        # No deps, TinyDB wrapper
tests/test_github_client.py → github_client.py  # No deps, HTTP + rate limiting
tests/test_collector.py     → collector.py      # Depends: parsing (including parse_breaking, parse_has_scope), storage, github_client
tests/test_cli_smoke.py     → cli.py            # Depends: collector, storage
                            → __main__.py       # Just imports cli
```

## Next Steps

1. Review `research.md` for technology decisions
2. Review `data-model.md` for entity schemas
3. Review `contracts/cli.md` for CLI interface specification
4. Review `quickstart.md` for developer onboarding
5. Run `/speckit.tasks` to generate implementation tasks
