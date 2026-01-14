# Feature Specification: Conventional Commit Census

**Feature Branch**: `001-initial-implementation`
**Created**: 2026-01-12
**Status**: Draft
**Input**: User description: "Conventional Commit Census: A self-updating GitHub Pages site that visualizes the frequency of conventional commit types across popular public repositories"

## User Scenarios & Testing _(mandatory)_

### User Story 1 - View Commit Type Distribution (Priority: P1)

A developer or researcher visits the GitHub Pages site to understand how conventional commit types are distributed across popular open-source repositories. They want to see at a glance which commit types (feat, fix, docs, etc.) are most commonly used in the community.

**Why this priority**: This is the core value proposition—without the visualization, the project delivers no user value. Everything else supports this experience.

**Independent Test**: Can be fully tested by loading the visualization page with exported data and verifying the chart displays correctly with all 11 commit types visible.

**Acceptance Scenarios**:

1. **Given** the visualization page has been deployed with valid data, **When** a user visits the page, **Then** they see a horizontal bar chart showing the frequency of each conventional commit type
2. **Given** the chart is displayed, **When** a user hovers over a bar, **Then** they see the exact count and percentage for that commit type
3. **Given** the chart is displayed, **When** a user clicks a legend item, **Then** that commit type toggles on/off with a smooth animation

---

### User Story 2 - Collect Repository Data (Priority: P2)

A maintainer runs the CLI tool to collect conventional commit statistics from approximately 1000 popular public GitHub repositories. The collection process respects API rate limits and can be resumed if interrupted.

**Why this priority**: Without data collection, there's nothing to visualize. This enables P1 but requires infrastructure that P1 doesn't need directly.

**Independent Test**: Can be tested by running the collect command with `--max-repos 10` and verifying data files are created with proper structure.

**Acceptance Scenarios**:

1. **Given** a valid GitHub token is configured, **When** the user runs the collect command, **Then** the system discovers and processes qualifying repositories
2. **Given** collection is in progress, **When** the process is interrupted, **Then** progress is saved and can be resumed with `--resume`
3. **Given** rate limits are approaching, **When** the system detects low remaining quota, **Then** it proactively sleeps before hitting the limit

---

### User Story 3 - Export Data for Visualization (Priority: P3)

A maintainer exports the collected data into a format consumable by the visualization frontend, producing a JSON file that contains aggregated commit type counts and metadata.

**Why this priority**: This bridges collection (P2) and visualization (P1), enabling the full workflow.

**Independent Test**: Can be tested by running the export command against existing collected data and verifying the output JSON contains all required fields.

**Acceptance Scenarios**:

1. **Given** data has been collected from repositories, **When** the user runs the export command, **Then** a JSON file is produced containing aggregated counts for all 11 commit types
2. **Given** the export completes, **When** the user checks the output file, **Then** it includes metadata: total repos, total commits, last updated timestamp

---

### User Story 4 - Understand Data Methodology (Priority: P4)

A user viewing the visualization wants to understand how the data was collected, including sample size, exclusions, and methodology, to properly interpret the results.

**Why this priority**: Transparency builds trust but is not required for basic functionality.

**Independent Test**: Can be tested by verifying the methodology section is visible on the page and contains all required disclosure elements.

**Acceptance Scenarios**:

1. **Given** a user is viewing the visualization, **When** they look at the methodology section, **Then** they see sample size, date range, exclusion criteria, and collection timestamp
2. **Given** a user is curious about the source, **When** they look for attribution, **Then** they find a link to the repository source code

---

### User Story 5 - Automated Monthly Updates (Priority: P5)

The system automatically runs the collection, export, and deployment pipeline monthly via CI/CD, keeping the visualization data fresh without manual intervention.

**Why this priority**: Automation ensures long-term value but the core product works with manual runs.

**Independent Test**: Can be tested by triggering the workflow manually and verifying it completes the full pipeline: collect → export → commit → deploy.

**Acceptance Scenarios**:

1. **Given** the scheduled workflow triggers, **When** the collection and export complete, **Then** updated data is committed to the repository
2. **Given** new data is committed, **When** validation passes, **Then** the updated visualization is deployed to GitHub Pages

---

### Edge Cases

- What happens when no qualifying repositories are found?
  - System logs a warning and completes with zero repos processed
- What happens when a repository has no conventional commits?
  - Repository is recorded with all type counts as zero
- What happens when the GitHub API is completely unavailable?
  - System retries with exponential backoff, then exits with saved progress
- What happens when rate limits are exhausted mid-collection?
  - System saves progress and sleeps until reset, or can be resumed later
- What happens when data files are corrupted?
  - Validate command detects issues and reports specific errors
- What happens when a user accesses the page on a slow connection?
  - Visualization gracefully loads with placeholder until data arrives
- What happens when data.json fails to load (404, network error, invalid JSON)?
  - Visualization displays a friendly error message with instructions to check back later
- What happens when some repositories fail during collection (partial failure)?
  - Failed repos are logged and skipped; collection continues with remaining repos; run completes as `completed` (not `failed`) if at least one repo succeeded

## Requirements _(mandatory)_

### Functional Requirements

**Data Collection**

- **FR-001**: System MUST discover repositories using GitHub Search API with filters: ≥3 stars, pushed within rolling 365-day window from collection start, public, not archived, not a fork, has license
- **FR-002**: System MUST analyze up to 100 conventional commits per repository from the last year
- **FR-003**: System MUST skip merge commits, empty commits, and commits from bot authors when counting
- **FR-004**: System MUST recognize exactly 11 conventional commit types: build, chore, ci, docs, feat, fix, perf, refactor, revert, style, test
- **FR-005**: System MUST detect bot authors using pattern matching against known bot name patterns
- **FR-006**: System MUST save progress after each completed repository to enable resumability
- **FR-007**: System MUST support graceful interruption (SIGINT/SIGTERM) without losing progress

**Rate Limiting**

- **FR-008**: System MUST respect GitHub API rate limits by checking remaining quota before requests
- **FR-009**: System MUST implement exponential backoff with jitter for transient failures
- **FR-010**: System MUST support both PAT (5000 requests/hour) and GITHUB_TOKEN (1000 requests/hour) rate limits

**Data Storage**

- **FR-011**: System MUST persist run metadata, repository data, and progress checkpoints as JSON files
- **FR-012**: System MUST maintain referential integrity between runs and their repository records
- **FR-013**: System MUST retain only the 3 most recent completed runs, with older data accessible via git history

**CLI Interface**

- **FR-014**: System MUST provide a `collect` command with options for max repos, minimum stars, and resume
- **FR-015**: System MUST provide an `export` command that produces visualization-ready JSON
- **FR-016**: System MUST provide a `validate` command to verify data integrity
- **FR-017**: System MUST provide a `status` command to show current progress and statistics
- **FR-018**: System MUST provide a `prune` command to clean up old runs

**Visualization**

- **FR-019**: Visualization MUST display a horizontal bar chart of commit type frequencies
- **FR-020**: Visualization MUST support interactive legend toggling with animated transitions
- **FR-021**: Visualization MUST display hover tooltips with exact counts and percentages
- **FR-022**: Visualization MUST respect system color scheme preference and support manual theme toggle
- **FR-023**: Visualization MUST include a methodology section explaining data collection approach

**Accessibility**

- **FR-024**: Visualization MUST use a colorblind-safe color palette
- **FR-025**: Visualization MUST be fully keyboard-navigable (tab through legend, Enter to toggle)
- **FR-026**: Visualization MUST include ARIA labels on all interactive elements
- **FR-027**: Visualization MUST meet WCAG AA contrast requirements

**Automation**

- **FR-028**: CI workflow MUST run collection on a monthly schedule (cron: `0 4 1 * *` - 4 AM UTC on the 1st of each month)
- **FR-029**: CI workflow MUST automatically commit updated data and trigger deployment
- **FR-030**: CI workflow MUST validate data integrity and auto-revert on validation failure
- **FR-031**: CI workflow MUST use conventional commit format for automated commits: `chore(data): update conventional commit statistics`
- **FR-032**: CI workflow MUST support manual triggering via `workflow_dispatch` for ad-hoc updates

### Key Entities

- **Run**: Represents a single collection execution with status, timestamps, and aggregate statistics. Each run has a unique identifier and tracks how many repositories were processed.

- **Repository Record**: Captures data about a single analyzed repository including its name, star count, primary language, license, and counts for each of the 11 conventional commit types from that run.

- **Progress Checkpoint**: Stores resumption state including the current run ID, search cursor position (star range and page), and the last fully-processed repository name.

- **Export Data**: The visualization-consumable format containing aggregated commit type counts, total repositories, total commits, collection timestamp, and methodology metadata.

## Success Criteria _(mandatory)_

### Measurable Outcomes

- **SC-001**: Users can view the complete visualization page and interact with it within 5 seconds of page load
- **SC-002**: Collection command processes up to 1000 repositories within 6 hours when using standard rate limits
- **SC-003**: Collection can be interrupted at any point and resume without re-processing already-completed repositories
- **SC-004**: Test coverage for the collection logic is at least 80%
- **SC-005**: All CLI commands complete successfully with `--help` providing clear usage instructions
- **SC-006**: Visualization is navigable using only keyboard (tab, enter, escape)
- **SC-007**: Visualization passes automated accessibility contrast checks (WCAG AA)
- **SC-008**: Monthly automated workflow completes successfully with updated data deployed
- **SC-009**: 100% of visualized data includes clear methodology disclosure visible on the same page
- **SC-010**: Export produces valid JSON that the visualization can render without errors

## Assumptions

- GitHub API remains available with current rate limits and endpoint structure
- Conventional commit format follows the widely-adopted specification (lowercase types, colon+space separator)
- Bot detection patterns cover the most common CI/automation tools (dependabot, renovate, github-actions, etc.)
- Users have a modern browser with JavaScript enabled for the visualization
- GitHub Pages remains available for hosting static content
- A Personal Access Token or GITHUB_TOKEN is available for API access
