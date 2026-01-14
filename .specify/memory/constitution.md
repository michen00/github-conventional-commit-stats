<!--
================================================================================
SYNC IMPACT REPORT
================================================================================
Version change: N/A → 1.0.0 (initial creation)

Modified principles: N/A (initial creation)

Added sections:
  - Core Principles (6 principles from pre-spec.md)
  - Constraints & Non-Goals
  - Development Workflow
  - Governance

Removed sections: N/A (initial creation)

Templates requiring updates:
  ✅ plan-template.md - Constitution Check section aligned
  ✅ spec-template.md - Requirements section compatible
  ✅ tasks-template.md - TDD workflow compatible
  ✅ checklist-template.md - No principle-specific updates needed
  ✅ agent-file-template.md - No principle-specific updates needed

Follow-up TODOs: None
================================================================================
-->

# Conventional Commit Stats Constitution

## Core Principles

### I. Test-Driven Development (TDD)

Tests MUST be written BEFORE implementation code. Tests define the contract and expected behavior.

- Red-Green-Refactor cycle is strictly enforced
- Tests serve as executable documentation
- No implementation code without failing tests first
- Test coverage MUST be ≥80% for `src/conv_commit_stats/`

**Rationale:** TDD ensures requirements are captured upfront, prevents regressions, and produces self-documenting code. For a demo project, this discipline demonstrates best practices.

### II. Simplicity Over Cleverness

Prefer straightforward implementations over sophisticated or "clever" solutions. This is a demo project, not production infrastructure.

- YAGNI (You Ain't Gonna Need It) applies rigorously
- Avoid premature optimization
- No abstractions without clear, immediate benefit
- One obvious way to accomplish each task

**Rationale:** A demo project's value lies in clarity and teachability. Complex solutions obscure the core concepts being demonstrated.

### III. Resumability

The collector MUST be interruptible and resumable. Progress MUST never be lost.

- Save progress checkpoints after each completed unit of work
- Atomic writes: a repo is either fully saved or not saved at all
- Support graceful shutdown on SIGINT/SIGTERM
- `--resume` flag MUST restore exact state from last interruption

**Rationale:** GitHub API collection runs can take hours. Users should not lose progress due to network issues, rate limits, or manual interruption.

### IV. Rate Limit Respect

NEVER exceed GitHub API rate limits. Sleep proactively, not reactively.

- Check `X-RateLimit-Remaining` before requests hit zero
- Implement exponential backoff with jitter for retries
- Support both PAT (5000/hr) and GITHUB_TOKEN (1000/hr) rate limits
- Log rate limit status for observability

**Rationale:** Respecting rate limits is both ethical API citizenship and practical necessity. Hitting limits causes data collection failures.

### V. Data Transparency

Users MUST understand exactly how data was collected and what it represents.

- Document methodology on visualization page
- Show sample size, exclusions, and collection timestamp
- Explain bot detection and conventional commit patterns
- Make source code accessible from the visualization

**Rationale:** Data visualizations without methodology are meaningless. Transparency builds trust and enables reproducibility.

### VI. Accessibility First

The visualization MUST be usable by everyone regardless of ability.

- Use colorblind-safe palette (IBM Design Language)
- WCAG AA contrast minimum for all text
- Full keyboard navigation support
- ARIA labels on all interactive elements
- Screen reader announcements for state changes

**Rationale:** Accessibility is not optional. A visualization that excludes users based on ability fails its core purpose.

## Constraints & Non-Goals

### Technical Constraints

| Constraint       | Value                       | Rationale                           |
| ---------------- | --------------------------- | ----------------------------------- |
| Python version   | ≥3.12                       | Modern typing, `StrEnum`, `tomllib` |
| Max repos        | ~1000                       | Balances coverage vs. API budget    |
| Max commits/repo | 100                         | Sufficient sample, limits API calls |
| Time window      | 1 year                      | Recent activity only                |
| Storage          | TinyDB (JSON)               | No server, git-committed            |
| Frontend         | Single HTML + Plotly.js CDN | No build step                       |
| CI runtime       | ≤6 hours                    | GitHub Actions limit                |

### Explicit Non-Goals

The following are intentionally out of scope:

- ❌ Real-time updates or streaming
- ❌ User authentication or personalization
- ❌ Database server (we commit JSON to git)
- ❌ Build step for frontend (single HTML file)
- ❌ GraphQL API (REST is sufficient for this scale)
- ❌ Private repository support
- ❌ Historical trend analysis (single snapshot per run)
- ❌ Per-language or per-topic breakdowns (future enhancement)

## Development Workflow

### Mandatory Tools

| Tool            | Purpose                        | Command           |
| --------------- | ------------------------------ | ----------------- |
| `uv`            | Dependency management          | `uv run ...`      |
| `ruff`          | Linting and formatting         | `make format`     |
| `mypy`          | Type checking                  | `make check`      |
| `pytest`        | Testing                        | `make test`       |
| `pre-commit`    | Git hooks                      | `make develop`    |
| `make check`    | Full CI validation             | Before any commit |

### Code Style Requirements

- Use `pathlib.Path` over `os.path`
- Use `httpx` (sync) over `requests`
- Use `structlog` for logging
- Use `typer` with `rich` for CLI
- Use Pydantic models for data validation
- Use Polars + Pandera for DataFrame operations
- Define `__all__` as tuple in all modules

## Governance

### Amendment Procedure

1. Proposed changes MUST be documented with rationale
2. Changes MUST NOT violate core principles without explicit justification
3. Breaking changes require MAJOR version bump
4. All amendments MUST update this document's version and date

### Versioning Policy

This constitution follows semantic versioning:

- **MAJOR**: Backward-incompatible governance/principle changes
- **MINOR**: New principles or materially expanded guidance
- **PATCH**: Clarifications, wording, typo fixes

### Compliance Review

- All PRs MUST verify compliance with principles
- Code review MUST check TDD adherence (tests before implementation)
- `make check` MUST pass before merge
- Complexity additions MUST be justified against Principle II (Simplicity)

### Guidance Reference

For runtime development guidance, refer to:

- `AGENTS.md` — Agent-specific instructions
- `CLAUDE.md` — Claude-specific development guidance
- `pre-spec.md` — Full specification with implementation details

**Version**: 1.0.0 | **Ratified**: 2026-01-12 | **Last Amended**: 2026-01-12
