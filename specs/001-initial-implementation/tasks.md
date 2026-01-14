# Tasks: Conventional Commit Census

**Input**: Design documents from `/specs/001-initial-implementation/`
**Prerequisites**: plan.md ✓, spec.md ✓, research.md ✓, data-model.md ✓, contracts/cli.md ✓, quickstart.md ✓

**Tests**: Included per Constitution Principle I (TDD) - tests written BEFORE implementation

**Organization**: Tasks grouped by user story for independent implementation and testing

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: User story label (US1, US2, US3, US5)
  - Note: US4 (Methodology) is merged into US1 as the methodology section is on the same visualization page
- Include exact file paths in descriptions

## Path Conventions

- **Source**: `src/conv_commit_stats/`
- **Tests**: `tests/`
- **Data**: `data/`
- **Frontend**: `docs/`
- **CI/CD**: `.github/workflows/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and development environment configuration

- [x] T001 Verify project structure matches plan.md in src/conv_commit_stats/
- [x] T002 [P] Add dependencies to pyproject.toml: httpx, tinydb, typer[all], structlog, pydantic, pydantic-settings, polars, pandera
- [x] T003 [P] Add dev dependencies to pyproject.toml: pytest, pytest-cov, respx (for httpx mocking)
- [x] T004 [P] Create tests/conftest.py with shared fixtures (tmp_path for TinyDB, mock responses)
- [x] T005 [P] Create empty data/ directory with .gitkeep
- [x] T006 Run `uv lock` and `make develop` to verify installation

---

## Phase 2: Foundational (Core Modules - Blocking Prerequisites)

**Purpose**: Pure functions and isolated modules that ALL user stories depend on

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

### Parsing Module (Pure Functions)

- [x] T007 [P] Write tests for commit type regex parsing in tests/test_parsing.py
- [x] T008 [P] Write tests for bot detection patterns in tests/test_parsing.py
- [x] T009 Implement CommitType enum and CONVENTIONAL_COMMIT_PATTERN in src/conv_commit_stats/parsing.py
- [x] T010 Implement BOT_PATTERNS list and is_bot() function in src/conv_commit_stats/parsing.py
- [x] T011 Implement parse_commit_type() function in src/conv_commit_stats/parsing.py

### Storage Module (TinyDB Wrapper)

- [x] T012 [P] Write tests for Run, RepoRecord, Progress models in tests/test_storage.py
- [x] T013 [P] Write tests for TinyDB CRUD operations in tests/test_storage.py
- [x] T014 Implement Pydantic models (Run, RepoRecord, Progress, RunStatus) in src/conv_commit_stats/storage.py
- [x] T015 Implement Storage class with TinyDB tables (runs, repos, progress) in src/conv_commit_stats/storage.py
- [x] T016 Implement atomic checkpoint save methods in src/conv_commit_stats/storage.py

### GitHub Client Module (HTTP + Rate Limiting)

- [x] T017 [P] Write tests for rate limit handling with respx mocks in tests/test_github_client.py
- [x] T018 [P] Write tests for search API pagination in tests/test_github_client.py
- [x] T019 Implement GitHubClient class with httpx in src/conv_commit_stats/github_client.py
- [x] T020 Implement rate limit checking (X-RateLimit-Remaining < 10) in src/conv_commit_stats/github_client.py
- [x] T021 Implement exponential backoff with jitter in src/conv_commit_stats/github_client.py
- [x] T022 Implement star-range bucketing for search pagination in src/conv_commit_stats/github_client.py

**Checkpoint**: Foundation ready - run `make test` to verify all foundational tests pass

---

## Phase 3: User Story 1 - View Commit Type Distribution (Priority: P1) 🎯 MVP

**Goal**: Users can view a horizontal bar chart of commit type frequencies on GitHub Pages

**Independent Test**: Load docs/index.html with sample data.json and verify chart displays with all 11 commit types, tooltips work, and accessibility features function

**Note**: US4 (Methodology) is incorporated here as the methodology section is on the same page

### Sample Data for Testing

- [x] T023 [US1] Create sample docs/data.json with realistic commit type distribution per data-model.md §4

### Visualization Implementation

- [x] T024 [P] [US1] Create docs/index.html with HTML structure (chart container, legend, methodology section, theme toggle)
- [x] T025 [P] [US1] Add Plotly.js CDN and chart initialization script in docs/index.html
- [x] T026 [P] [US1] Implement horizontal bar chart with IBM Design Language colors per research.md §7
- [x] T027 [P] [US1] Implement hover tooltips with count and percentage in docs/index.html
- [x] T028 [P] [US1] Implement legend toggle with 250ms animation in docs/index.html
- [x] T029 [P] [US1] Implement theme toggle (system → dark → light → system) with localStorage persistence in docs/index.html
- [x] T030 [P] [US1] Add methodology section with sample size, date range, exclusions, timestamp in docs/index.html
- [x] T031 [P] [US1] Add repository attribution link in docs/index.html

### Accessibility Implementation

- [x] T032 [P] [US1] Implement keyboard navigation (Tab through legend, Enter to toggle) in docs/index.html
- [x] T033 [P] [US1] Add ARIA labels to chart, bars, legend items, and theme toggle in docs/index.html
- [x] T034 [P] [US1] Implement aria-live region for screen reader announcements in docs/index.html
- [x] T035 [P] [US1] Verify WCAG AA contrast ratios for all text and interactive elements
- [x] T036 [P] [US1] Add focus indicators (2px solid outline) per research.md §7

### Error Handling

- [x] T037 [P] [US1] Implement loading state with placeholder in docs/index.html
- [x] T038 [P] [US1] Implement error state when data.json fails to load in docs/index.html

**Checkpoint**: US1 complete - open docs/index.html locally to verify visualization works with sample data

---

## Phase 4: User Story 2 - Collect Repository Data (Priority: P2)

**Goal**: Maintainer can run CLI to collect commit statistics from ~1000 GitHub repositories with resumability

**Independent Test**: Run `uv run conv-commit-stats collect --max-repos 10` and verify data files created in data/

### Collector Tests

- [x] T039 [P] [US2] Write tests for repository discovery flow in tests/test_collector.py
- [x] T040 [P] [US2] Write tests for commit parsing orchestration in tests/test_collector.py
- [x] T041 [P] [US2] Write tests for checkpoint save/resume in tests/test_collector.py
- [x] T042 [P] [US2] Write tests for SIGINT/SIGTERM handling in tests/test_collector.py

### Collector Implementation

- [x] T043 [US2] Implement Collector class with dependency injection in src/conv_commit_stats/collector.py
- [x] T044 [US2] Implement discover_repositories() with star-range bucketing in src/conv_commit_stats/collector.py
- [x] T045 [US2] Implement process_repository() with commit fetching and parsing in src/conv_commit_stats/collector.py
- [x] T046 [US2] Implement run() method with checkpoint saves after each repo in src/conv_commit_stats/collector.py
- [x] T047 [US2] Implement signal handler for graceful SIGINT/SIGTERM in src/conv_commit_stats/collector.py
- [x] T048 [US2] Implement resume logic from progress checkpoint in src/conv_commit_stats/collector.py

### CLI Tests

- [ ] T049 [P] [US2] Write smoke tests for collect command in tests/test_cli_smoke.py
- [ ] T050 [P] [US2] Write smoke tests for validate command in tests/test_cli_smoke.py
- [ ] T051 [P] [US2] Write smoke tests for status command in tests/test_cli_smoke.py
- [ ] T052 [P] [US2] Write smoke tests for prune command in tests/test_cli_smoke.py

### CLI Implementation

- [ ] T053 [US2] Create Typer app with global options (--db-path, --help, --version) in src/conv_commit_stats/cli.py
- [ ] T054 [US2] Implement Settings class with pydantic-settings for GITHUB_TOKEN, CCC_* env vars in src/conv_commit_stats/cli.py
- [ ] T055 [US2] Implement collect command with --max-repos, --min-stars, --resume options in src/conv_commit_stats/cli.py
- [ ] T056 [US2] Implement concurrency check (no parallel runs) in collect command in src/conv_commit_stats/cli.py
- [ ] T057 [US2] Implement validate command with integrity checks per cli.md in src/conv_commit_stats/cli.py
- [ ] T058 [US2] Implement status command showing current/recent runs in src/conv_commit_stats/cli.py
- [ ] T059 [US2] Implement prune command with --keep, --dry-run options in src/conv_commit_stats/cli.py
- [ ] T060 [US2] Update src/conv_commit_stats/__main__.py to import and run cli.app

**Checkpoint**: US2 complete - run `uv run conv-commit-stats collect --max-repos 10` to verify collection works

---

## Phase 5: User Story 3 - Export Data for Visualization (Priority: P3)

**Goal**: Maintainer can export collected data to JSON format for the visualization

**Independent Test**: Run `uv run conv-commit-stats export` and verify docs/data.json contains all required fields per data-model.md §4

### Export Tests

- [ ] T061 [P] [US3] Write tests for data aggregation with Polars in tests/test_cli_smoke.py
- [ ] T062 [P] [US3] Write tests for ExportData JSON schema validation in tests/test_cli_smoke.py

### Export Implementation

- [ ] T063 [US3] Implement ExportData, CommitTypeCounts, Methodology Pydantic models in src/conv_commit_stats/storage.py
- [ ] T064 [US3] Implement aggregate_run_data() using Polars in src/conv_commit_stats/cli.py
- [ ] T065 [US3] Implement export command with --run, --output options in src/conv_commit_stats/cli.py
- [ ] T066 [US3] Implement Pandera schema validation before export in src/conv_commit_stats/cli.py

**Checkpoint**: US3 complete - run full pipeline: collect → export → verify docs/data.json → refresh visualization

---

## Phase 6: User Story 5 - Automated Monthly Updates (Priority: P5)

**Goal**: CI/CD automatically collects, exports, validates, and deploys data monthly

**Independent Test**: Trigger workflow_dispatch manually and verify it completes: collect → export → commit → deploy

### CI/CD Implementation

- [ ] T067 [US5] Create .github/workflows/collect.yml with monthly cron schedule (0 4 1 * *)
- [ ] T068 [US5] Add workflow_dispatch trigger for manual runs in .github/workflows/collect.yml
- [ ] T069 [US5] Implement collection step with 6-hour timeout in .github/workflows/collect.yml
- [ ] T070 [US5] Implement export and validate steps in .github/workflows/collect.yml
- [ ] T071 [US5] Implement git commit with conventional message: "chore(data): update conventional commit statistics"
- [ ] T072 [US5] Implement auto-revert on validation failure in .github/workflows/collect.yml
- [ ] T073 [US5] Configure GitHub Pages deployment in .github/workflows/collect.yml

**Checkpoint**: US5 complete - trigger workflow manually to verify full pipeline

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, cleanup, and final validation

- [ ] T074 [P] Update src/conv_commit_stats/__init__.py with public API exports
- [ ] T075 [P] Add py.typed marker file for PEP 561 compliance
- [ ] T076 [P] Verify ≥80% test coverage with `make test`
- [ ] T077 Run quickstart.md validation: full workflow from clone to visualization
- [ ] T078 [P] Update README.md with usage instructions and badges
- [ ] T079 Run `make check` to verify all linting, formatting, and tests pass
- [ ] T080 Final accessibility audit of docs/index.html with browser tools

---

## Dependencies & Execution Order

### Phase Dependencies

```text
Phase 1 (Setup)
    │
    ▼
Phase 2 (Foundational) ◄── BLOCKS all user stories
    │
    ├──────────────────────────┬──────────────────────────┐
    ▼                          ▼                          ▼
Phase 3 (US1)             Phase 4 (US2)             [Can parallelize]
    │                          │
    │                          ▼
    │                     Phase 5 (US3) ◄── Needs US2 data
    │                          │
    └──────────────────────────┼──────────────────────────┘
                               ▼
                         Phase 6 (US5) ◄── Needs US2 + US3 complete
                               │
                               ▼
                         Phase 7 (Polish)
```

### User Story Dependencies

| Story | Depends On | Can Start After |
|-------|------------|-----------------|
| US1 (P1) | Foundational | Phase 2 complete |
| US2 (P2) | Foundational | Phase 2 complete |
| US3 (P3) | US2 | Phase 4 complete |
| US5 (P5) | US2, US3 | Phase 5 complete |

### Within Each Phase

- Tests marked [P] can run in parallel
- Tests MUST be written and FAIL before implementation
- Implementation follows module dependency order from plan.md

---

## Parallel Opportunities

### Phase 2 - All foundational modules in parallel:

```text
T007-T011 (parsing)     ─┐
T012-T016 (storage)     ─┼─► All independent, can parallelize
T017-T022 (github_client)┘
```

### Phase 3 - Independent UI components (all [P] after T023):

```text
T024-T031 (chart + methodology) ─┐
T032-T036 (accessibility)        ─┼─► All [P] marked, parallelize after T023 (sample data)
T037-T038 (error handling)       ┘
```

### Phase 4 - Tests before implementation:

```text
T039-T042 (collector tests) ──► Then T043-T048 (collector impl)
T049-T052 (CLI tests)       ──► Then T053-T060 (CLI impl)
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: User Story 1 (visualization with sample data)
4. **STOP and VALIDATE**: Load docs/index.html locally - chart should work!
5. Deploy to GitHub Pages manually if desired

### Full Implementation

1. Setup + Foundational → Foundation ready
2. US1 → Visualization works with sample data (deployable MVP!)
3. US2 → Collection CLI works → Real data available
4. US3 → Export CLI works → Real data.json replaces sample
5. US5 → Automation works → Self-updating site!
6. Polish → Production ready

### Suggested Order for Solo Developer

```text
Week 1: Setup + Foundational + US1 (MVP visualization)
Week 2: US2 (collection - largest phase)
Week 3: US3 + US5 + Polish
```

---

## Summary

| Phase | Tasks | Parallelizable |
|-------|-------|----------------|
| Phase 1: Setup | 6 | 4 |
| Phase 2: Foundational | 16 | 6 |
| Phase 3: US1 (P1) | 16 | 15 |
| Phase 4: US2 (P2) | 22 | 8 |
| Phase 5: US3 (P3) | 6 | 2 |
| Phase 6: US5 (P5) | 7 | 0 |
| Phase 7: Polish | 7 | 4 |
| **Total** | **80** | **39** |

---

## Notes

- [P] tasks = different files, no dependencies within phase
- [Story] label maps task to specific user story for traceability
- Each user story is independently completable and testable
- Constitution requires TDD: verify tests fail before implementing
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
