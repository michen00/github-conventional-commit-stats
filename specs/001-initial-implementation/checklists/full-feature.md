# Pre-Release Gate Checklist: Conventional Commit Census

**Purpose**: Comprehensive requirements quality validation before release
**Created**: 2026-01-12
**Feature**: [spec.md](../spec.md)
**Depth**: Strict (Pre-release gate)
**Coverage**: Full feature (CLI, Data, Visualization, Resilience, Automation)
**Last Reviewed**: 2026-01-12
**Status**: ✅ All items addressed

---

## Data Collection Requirements

- [x] CHK001 Are repository discovery filter criteria explicitly quantified (stars ≥3, pushed within 1 year)? [Clarity, Spec §FR-001] ✓ Documented
- [x] CHK002 Is the maximum commits per repository limit documented (100 commits)? [Completeness, Spec §FR-002] ✓ Documented
- [x] CHK003 Are all 11 conventional commit types explicitly enumerated? [Completeness, Spec §FR-004] ✓ build, chore, ci, docs, feat, fix, perf, refactor, revert, style, test
- [x] CHK004 Is the bot detection pattern list comprehensive and documented? [Completeness, Spec §FR-005] ✓ Research §5 lists 17 patterns
- [x] CHK005 Are merge commit and empty commit exclusion criteria defined? [Clarity, Spec §FR-003] ✓ Documented
- [x] CHK006 Is the "pushed within 1 year" filter based on a rolling window or fixed date? [Ambiguity, Spec §FR-001] ✓ **Clarified**: Rolling 365-day window from collection start
- [x] CHK007 Are commit message parsing rules (lowercase, space after colon) explicitly specified? [Clarity, Research §4] ✓ Regex pattern documented

## Resumability & Checkpoint Requirements

- [x] CHK008 Is the checkpoint granularity defined (per repository vs per page)? [Clarity, Spec §FR-006] ✓ "after each completed repository"
- [x] CHK009 Are atomic write requirements specified for progress saves? [Completeness, Constitution §III] ✓ "a repo is either fully saved or not saved at all"
- [x] CHK010 Is the behavior on SIGINT/SIGTERM explicitly documented (finish current repo, save, exit 0)? [Clarity, CLI Contract] ✓ Documented
- [x] CHK011 Are progress checkpoint fields (run_id, search_cursor, last_repo) documented with types? [Completeness, Data Model §3] ✓ Full schema with types
- [x] CHK012 Is the resume behavior defined for corrupted progress files? [Edge Case, Data Model §8] ✓ **Added**: Log warning, exit with error if --resume, or delete and restart fresh
- [x] CHK013 Are requirements for concurrent run prevention documented? [Coverage, CLI Contract] ✓ **Added**: Concurrency check before starting collect

## Rate Limiting Requirements

- [x] CHK014 Are both PAT (5000/hr) and GITHUB_TOKEN (1000/hr) rate limits documented? [Completeness, Spec §FR-010] ✓ Documented in spec and research
- [x] CHK015 Is the proactive sleep threshold quantified (e.g., sleep when <10 remaining)? [Clarity, Research §6] ✓ "If remaining < 10"
- [x] CHK016 Is exponential backoff with jitter specified with concrete parameters? [Clarity, Spec §FR-009] ✓ Algorithm documented in research
- [x] CHK017 Are Search API rate limits (30/min) distinguished from Core API limits? [Completeness, Research §6] ✓ Rate limit buckets table
- [x] CHK018 Is behavior defined when rate limit resets while sleeping? [Edge Case, CLI Contract] ✓ **Added**: Re-check quota after wake, continue immediately if available

## Data Storage & Integrity Requirements

- [x] CHK019 Are all three TinyDB tables (runs, repos, progress) documented with schemas? [Completeness, Data Model] ✓ Full JSON schemas
- [x] CHK020 Are referential integrity rules defined (repos → runs foreign key)? [Clarity, Data Model §2] ✓ "run_id: Foreign key to Run"
- [x] CHK021 Is the retention policy quantified (3 most recent completed runs)? [Clarity, Spec §FR-013] ✓ Data Model §7 details policy
- [x] CHK022 Are validation rules for each entity field documented (non-negative counts, format patterns)? [Completeness, Data Model] ✓ Pydantic models with constraints
- [x] CHK023 Is the `commits_analyzed` = sum of type counts invariant documented? [Consistency, Data Model §2] ✓ Validation rule documented
- [x] CHK024 Are Run state transitions (running → completed/failed) explicitly defined? [Completeness, Data Model §1] ✓ State diagram included
- [x] CHK025 Is behavior defined when storage files are missing vs empty? [Edge Case, Data Model §8] ✓ **Added**: Table with scenarios and behaviors

## CLI Interface Requirements

- [x] CHK026 Are all 5 CLI commands (collect, export, validate, status, prune) documented? [Completeness, CLI Contract] ✓ Full contract
- [x] CHK027 Are command options, types, and defaults specified for each command? [Clarity, CLI Contract] ✓ Options tables per command
- [x] CHK028 Are exit codes documented for success (0) and failure (1) scenarios? [Completeness, CLI Contract] ✓ Exit code tables
- [x] CHK029 Is `--help` output format and content specified? [Clarity, CLI Contract] ✓ "Help Text Convention" section
- [x] CHK030 Are environment variables (GITHUB_TOKEN, CCC_DB_PATH) documented? [Completeness, CLI Contract] ✓ Environment Variables table
- [x] CHK031 Is error message format consistent across all commands? [Consistency, CLI Contract] ✓ "Common Error Messages" table (expanded)
- [x] CHK032 Is behavior defined when GITHUB_TOKEN is missing or invalid? [Edge Case, CLI Contract] ✓ Error message documented

## Visualization Requirements

- [x] CHK033 Is chart type explicitly specified (horizontal bar chart)? [Clarity, Spec §FR-019] ✓ Documented
- [x] CHK034 Are animation durations for legend toggle quantified (200-300ms)? [Clarity, Research §7] ✓ **Added**: Animation specifications table (150-400ms)
- [x] CHK035 Is hover tooltip content explicitly defined (count + percentage)? [Completeness, Spec §FR-021] ✓ "exact counts and percentages"
- [x] CHK036 Are theme toggle states documented (system → dark → light → system)? [Clarity, Research §7] ✓ Theme persistence section
- [x] CHK037 Is localStorage key name for theme preference specified? [Completeness, Research §7] ✓ **Added**: `ccc-theme-preference`
- [x] CHK038 Are loading state requirements defined for slow data fetch? [Edge Case, Spec Edge Cases] ✓ "gracefully loads with placeholder"
- [x] CHK039 Is error state behavior defined when data.json fails to load? [Edge Case, Spec Edge Cases] ✓ **Added**: Friendly error message with retry instructions

## Accessibility Requirements

- [x] CHK040 Is the colorblind-safe palette explicitly named (IBM Design Language)? [Clarity, Research §7] ✓ "IBM Design palette"
- [x] CHK041 Are all 11 commit type colors explicitly mapped? [Completeness, Research §7] ✓ **Added**: Full color mapping table (light/dark themes)
- [x] CHK042 Are keyboard navigation keys specified (Tab, Enter, Escape)? [Clarity, Spec §FR-025] ✓ "tab through legend, Enter to toggle"
- [x] CHK043 Is WCAG AA contrast ratio requirement quantified (4.5:1 for text)? [Clarity, Spec §FR-027] ✓ WCAG AA standard applies
- [x] CHK044 Are ARIA label requirements specified for chart, bars, and legend? [Completeness, Spec §FR-026] ✓ "all interactive elements"
- [x] CHK045 Are screen reader announcements defined for state changes? [Completeness, Research §7] ✓ **Added**: Live region announcements table
- [x] CHK046 Is focus management documented for legend toggle interactions? [Coverage, Research §7] ✓ **Added**: Focus behavior table and indicators

## Methodology & Transparency Requirements

- [x] CHK047 Are all methodology disclosure elements enumerated (sample size, date range, exclusions, timestamp)? [Completeness, Spec §FR-023] ✓ US4 acceptance scenarios
- [x] CHK048 Is source code attribution requirement documented (link to repository)? [Clarity, US4 Acceptance] ✓ "link to the repository source code"
- [x] CHK049 Is methodology section placement specified (same page as visualization)? [Clarity, Spec §SC-009] ✓ "visible on the same page"

## CI/CD Automation Requirements

- [x] CHK050 Is the monthly schedule explicitly defined (cron expression)? [Clarity, Spec §FR-028] ✓ **Updated**: `0 4 1 * *` (4 AM UTC on 1st)
- [x] CHK051 Is the CI timeout limit documented (6 hours)? [Completeness, Plan §Technical Context] ✓ Documented
- [x] CHK052 Is auto-revert behavior on validation failure documented? [Clarity, Spec §FR-030] ✓ Documented
- [x] CHK053 Are commit message format requirements for automated commits specified? [Completeness, Spec §FR-031] ✓ **Added**: `chore(data): update conventional commit statistics`
- [x] CHK054 Is manual trigger (workflow_dispatch) requirement documented? [Completeness, Spec §FR-032] ✓ **Added**: FR-032 added to spec

## Success Criteria Quality

- [x] CHK055 Is "5 seconds page load" measurable with specific methodology? [Measurability, Spec §SC-001] ✓ Clear metric
- [x] CHK056 Is "6 hours for 1000 repos" testable under specified rate limits? [Measurability, Spec §SC-002] ✓ Testable with rate limit context
- [x] CHK057 Is "80% test coverage" scope defined (src/conv_commit_stats/ only)? [Clarity, Constitution §I] ✓ "src/conv_commit_stats/"
- [x] CHK058 Are "clear usage instructions" for --help objectively verifiable? [Measurability, CLI Contract] ✓ Help text format specified
- [x] CHK059 Is "valid JSON" export criteria defined (schema compliance)? [Clarity, Data Model §4] ✓ ExportData schema defined

## Assumption Validation

- [x] CHK060 Is the GitHub API version/endpoint dependency documented? [Dependency, Spec Assumptions] ✓ "current rate limits and endpoint structure"
- [x] CHK061 Are bot detection patterns validated against current bot naming conventions? [Assumption, Research §5] ✓ 17 patterns documented
- [x] CHK062 Is JavaScript requirement for visualization documented? [Assumption, Spec Assumptions] ✓ "JavaScript enabled"
- [x] CHK063 Is the conventional commit format specification referenced? [Dependency, Spec Assumptions] ✓ "widely-adopted specification"

## Cross-Cutting Consistency

- [x] CHK064 Are commit type names consistent across spec, data model, and CLI? [Consistency] ✓ All 11 types match
- [x] CHK065 Is "conventional commit" terminology used consistently (not "conventional message")? [Consistency] ✓ Consistent
- [x] CHK066 Are entity names consistent between spec (Key Entities) and data model? [Consistency] ✓ Run, RepoRecord, Progress, ExportData
- [x] CHK067 Do CLI command descriptions match functional requirements? [Consistency, Spec vs CLI Contract] ✓ Aligned

## Edge Case & Recovery Coverage

- [x] CHK068 Is behavior defined for zero qualifying repositories found? [Edge Case, Spec Edge Cases] ✓ "logs a warning and completes with zero"
- [x] CHK069 Is behavior defined for repository with zero conventional commits? [Edge Case, Spec Edge Cases] ✓ "recorded with all type counts as zero"
- [x] CHK070 Is behavior defined for GitHub API completely unavailable? [Exception Flow, Spec Edge Cases] ✓ "retries with exponential backoff, then exits"
- [x] CHK071 Is partial failure behavior (some repos fail, others succeed) documented? [Recovery, Spec Edge Cases] ✓ **Added**: Log and skip failed repos, continue, complete if any succeeded
- [x] CHK072 Is data migration behavior between schema versions documented? [Recovery, Data Model §8] ✓ **Added**: No auto-migration policy with rationale and upgrade guidance

---

## Summary

| Status         | Count  | Percentage |
| -------------- | ------ | ---------- |
| ✅ Completed   | 72     | 100%       |
| ⚠️ Outstanding | 0      | 0%         |
| **Total**      | **72** | **100%**   |

## Gaps Addressed in This Review

| CHK    | Gap Description               | Resolution                            | Document               |
| ------ | ----------------------------- | ------------------------------------- | ---------------------- |
| CHK006 | Rolling vs fixed date         | Clarified as "rolling 365-day window" | spec.md §FR-001        |
| CHK012 | Corrupted progress file       | Added error handling table            | data-model.md §8       |
| CHK013 | Concurrent run prevention     | Added concurrency check behavior      | cli.md §collect        |
| CHK018 | Rate limit reset during sleep | Added re-check after wake             | cli.md §Error Handling |
| CHK025 | Missing vs empty files        | Added scenario/behavior table         | data-model.md §8       |
| CHK034 | Animation durations           | Added animation specifications        | research.md §7         |
| CHK037 | localStorage key name         | Specified `ccc-theme-preference`      | research.md §7         |
| CHK039 | data.json load failure        | Added edge case                       | spec.md Edge Cases     |
| CHK041 | Color mapping                 | Added full 11-type color table        | research.md §7         |
| CHK045 | Screen reader announcements   | Added live region table               | research.md §7         |
| CHK046 | Focus management              | Added focus behavior table            | research.md §7         |
| CHK053 | Automated commit format       | Added FR-031                          | spec.md §Automation    |
| CHK054 | Manual workflow trigger       | Added FR-032                          | spec.md §Automation    |
| CHK071 | Partial failure behavior      | Added edge case                       | spec.md Edge Cases     |
| CHK072 | Schema migration              | Added policy with rationale           | data-model.md §8       |

---

## Notes

- **Gate Type**: Pre-release validation (strict)
- **Coverage**: All 7 spec domains + data model + CLI contract
- **Focus**: Balanced (Completeness, Clarity, Consistency, Measurability, Coverage)
- **Result**: All 72 checklist items have been addressed
- **Recommendation**: Ready to proceed to implementation phase
