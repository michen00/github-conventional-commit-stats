# Data Model: Conventional Commit Census

**Branch**: `001-initial-implementation` | **Date**: 2026-01-12

## Overview

This document defines the data entities, their attributes, relationships, and validation rules for the Conventional Commit Census system.

---

## Entity Diagram

```text
┌─────────────────────────────────────────────────────────────────┐
│                           Storage                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │  runs.json   │  │  repos.json  │  │progress.json │          │
│  │  (TinyDB)    │  │  (TinyDB)    │  │  (TinyDB)    │          │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘          │
│         │                 │                 │                   │
│         ▼                 ▼                 ▼                   │
│    ┌────────┐       ┌───────────┐    ┌───────────┐             │
│    │  Run   │──1:N──│RepoRecord │    │ Progress  │             │
│    └────────┘       └───────────┘    └───────────┘             │
│         │                                                       │
│         │  export                                               │
│         ▼                                                       │
│    ┌───────────┐                                               │
│    │ExportData │ ──────────────────► docs/data.json            │
│    └───────────┘                                               │
└─────────────────────────────────────────────────────────────────┘
```

---

## 1. Run

Represents a single collection execution with status, timestamps, and aggregate statistics.

### Run Attributes

| Field                    | Type               | Required | Description                                     |
| ------------------------ | ------------------ | -------- | ----------------------------------------------- |
| `run_id`                 | `str`              | ✓        | Unique identifier: `run_{ISO8601_timestamp}`    |
| `started_at`             | `datetime`         | ✓        | Collection start time (ISO 8601)                |
| `completed_at`           | `datetime \| None` |          | Collection end time (null if in progress)       |
| `status`                 | `RunStatus`        | ✓        | Current state: `running`, `completed`, `failed` |
| `repos_processed`        | `int`              | ✓        | Total repositories attempted                    |
| `repos_qualified`        | `int`              | ✓        | Repositories with valid commit data             |
| `total_commits_analyzed` | `int`              | ✓        | Sum of commits across all repos                 |

### State Transitions

```text
                 start
                   │
                   ▼
              ┌─────────┐
              │ running │
              └────┬────┘
                   │
         ┌─────────┼─────────┐
         │         │         │
    success    interrupt   error
         │         │         │
         ▼         ▼         ▼
    ┌──────────┐ ┌──────────┐ ┌────────┐
    │completed │ │ running  │ │ failed │
    └──────────┘ │(resumable)│ └────────┘
                 └──────────┘
```

### Run Validation Rules

- `run_id` MUST be unique across all runs
- `run_id` format: `run_{YYYY-MM-DDTHH:MM:SSZ}`
- `repos_qualified` MUST be ≤ `repos_processed`
- `completed_at` MUST be null when `status == running`
- `completed_at` MUST be set when `status in (completed, failed)`

### TinyDB Schema (runs.json)

```json
{
  "runs": {
    "1": {
      "run_id": "run_2026-01-12T04:00:00Z",
      "started_at": "2026-01-12T04:00:00Z",
      "completed_at": "2026-01-12T05:15:00Z",
      "status": "completed",
      "repos_processed": 1000,
      "repos_qualified": 847,
      "total_commits_analyzed": 84700
    }
  }
}
```

---

## 2. RepoRecord

Captures data about a single analyzed repository including commit type counts.

### RepoRecord Attributes

| Field              | Type          | Required | Description                             |
| ------------------ | ------------- | -------- | --------------------------------------- |
| `run_id`           | `str`         | ✓        | Foreign key to Run                      |
| `repo`             | `str`         | ✓        | Full name: `owner/repo`                 |
| `default_branch`   | `str`         | ✓        | Branch analyzed (e.g., `main`)          |
| `head_commit`      | `str`         | ✓        | SHA of latest commit at collection time |
| `stars`            | `int`         | ✓        | Star count at collection time           |
| `language`         | `str \| None` |          | Primary language (may be null)          |
| `created_at`       | `datetime`    | ✓        | Repository creation date                |
| `license`          | `str \| None` |          | SPDX license identifier                 |
| `timestamp`        | `datetime`    | ✓        | When this record was created            |
| `commits_analyzed` | `int`         | ✓        | Number of conventional commits found    |
| `build`            | `int`         | ✓        | Count of `build:` commits               |
| `chore`            | `int`         | ✓        | Count of `chore:` commits               |
| `ci`               | `int`         | ✓        | Count of `ci:` commits                  |
| `docs`             | `int`         | ✓        | Count of `docs:` commits                |
| `feat`             | `int`         | ✓        | Count of `feat:` commits                |
| `fix`              | `int`         | ✓        | Count of `fix:` commits                 |
| `perf`             | `int`         | ✓        | Count of `perf:` commits                |
| `refactor`         | `int`         | ✓        | Count of `refactor:` commits            |
| `revert`           | `int`         | ✓        | Count of `revert:` commits              |
| `style`            | `int`         | ✓        | Count of `style:` commits               |
| `test`             | `int`         | ✓        | Count of `test:` commits                |

### RepoRecord Validation Rules

- `repo` MUST be unique within a run (composite key: `run_id` + `repo`)
- All commit type counts MUST be ≥ 0
- `commits_analyzed` MUST equal sum of all type counts
- `stars` MUST be ≥ 3 (minimum filter threshold)

### TinyDB Schema (repos.json)

```json
{
  "repos": {
    "1": {
      "run_id": "run_2026-01-12T04:00:00Z",
      "repo": "facebook/react",
      "default_branch": "main",
      "head_commit": "abc123def456",
      "stars": 220000,
      "language": "JavaScript",
      "created_at": "2013-05-24T16:15:54Z",
      "license": "MIT",
      "timestamp": "2026-01-12T04:02:15Z",
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

---

## 3. Progress

Stores resumption state for interrupted collection runs.

### Progress Attributes

| Field        | Type          | Required | Description                                          |
| ------------ | ------------- | -------- | ---------------------------------------------------- |
| `key`        | `str`         | ✓        | Progress key: `run_id`, `search_cursor`, `last_repo` |
| `value`      | `str \| dict` | ✓        | Progress value (type depends on key)                 |
| `updated_at` | `datetime`    | ✓        | When this checkpoint was saved                       |

### Progress Keys

| Key             | Value Type                      | Description                          |
| --------------- | ------------------------------- | ------------------------------------ |
| `run_id`        | `str`                           | Current run identifier               |
| `search_cursor` | `{stars_range: str, page: int}` | Position in search pagination        |
| `last_repo`     | `str`                           | Last fully-processed repository name |

### Progress Validation Rules

- Each key MUST appear at most once per run
- `search_cursor.page` MUST be ≥ 1
- `last_repo` MUST be a valid `owner/repo` format

### TinyDB Schema (progress.json)

```json
{
  "progress": {
    "1": {
      "key": "run_id",
      "value": "run_2026-01-12T04:00:00Z",
      "updated_at": "2026-01-12T04:00:00Z"
    },
    "2": {
      "key": "search_cursor",
      "value": { "stars_range": "500..1000", "page": 3 },
      "updated_at": "2026-01-12T04:15:00Z"
    },
    "3": {
      "key": "last_repo",
      "value": "facebook/react",
      "updated_at": "2026-01-12T04:45:00Z"
    }
  }
}
```

---

## 4. ExportData

The visualization-consumable format containing aggregated commit type counts.

### ExportData Attributes

| Field           | Type               | Required | Description                           |
| --------------- | ------------------ | -------- | ------------------------------------- |
| `run_id`        | `str`              | ✓        | Source run identifier                 |
| `generated_at`  | `datetime`         | ✓        | Export timestamp                      |
| `total_repos`   | `int`              | ✓        | Number of repositories in aggregation |
| `total_commits` | `int`              | ✓        | Total conventional commits counted    |
| `counts`        | `CommitTypeCounts` | ✓        | Aggregated counts per type            |
| `methodology`   | `Methodology`      | ✓        | Collection methodology metadata       |

### CommitTypeCounts (nested)

| Field      | Type  | Description                 |
| ---------- | ----- | --------------------------- |
| `build`    | `int` | Aggregated build commits    |
| `chore`    | `int` | Aggregated chore commits    |
| `ci`       | `int` | Aggregated ci commits       |
| `docs`     | `int` | Aggregated docs commits     |
| `feat`     | `int` | Aggregated feat commits     |
| `fix`      | `int` | Aggregated fix commits      |
| `perf`     | `int` | Aggregated perf commits     |
| `refactor` | `int` | Aggregated refactor commits |
| `revert`   | `int` | Aggregated revert commits   |
| `style`    | `int` | Aggregated style commits    |
| `test`     | `int` | Aggregated test commits     |

### Methodology (nested)

| Field                  | Type        | Description                       |
| ---------------------- | ----------- | --------------------------------- |
| `min_stars`            | `int`       | Minimum star filter used          |
| `max_commits_per_repo` | `int`       | Maximum commits analyzed per repo |
| `time_window_days`     | `int`       | Days of commit history analyzed   |
| `excluded`             | `list[str]` | List of exclusion criteria        |

### JSON Schema (docs/data.json)

```json
{
  "run_id": "run_2026-01-12T04:00:00Z",
  "generated_at": "2026-01-12T05:20:00Z",
  "total_repos": 847,
  "total_commits": 84700,
  "counts": {
    "feat": 25000,
    "fix": 20000,
    "docs": 12000,
    "chore": 10000,
    "refactor": 8000,
    "test": 5000,
    "ci": 2000,
    "build": 1500,
    "style": 800,
    "perf": 300,
    "revert": 100
  },
  "methodology": {
    "min_stars": 3,
    "max_commits_per_repo": 100,
    "time_window_days": 365,
    "excluded": [
      "merge commits",
      "bot authors",
      "non-conventional messages",
      "archived repositories",
      "forks"
    ]
  }
}
```

---

## 5. Enumerations

### RunStatus

```python
class RunStatus(StrEnum):
    RUNNING = auto()     # Collection in progress
    COMPLETED = auto()   # Successfully finished
    FAILED = auto()      # Terminated with error
```

### CommitType

```python
class CommitType(StrEnum):
    BUILD = auto()
    CHORE = auto()
    CI = auto()
    DOCS = auto()
    FEAT = auto()
    FIX = auto()
    PERF = auto()
    REFACTOR = auto()
    REVERT = auto()
    STYLE = auto()
    TEST = auto()
```

---

## 6. Pydantic Model Definitions

```python
from datetime import datetime
from enum import StrEnum, auto
from typing import Annotated

from pydantic import BaseModel, Field, NonNegativeInt


class RunStatus(StrEnum):
    RUNNING = auto()
    COMPLETED = auto()
    FAILED = auto()


class CommitType(StrEnum):
    BUILD = auto()
    CHORE = auto()
    CI = auto()
    DOCS = auto()
    FEAT = auto()
    FIX = auto()
    PERF = auto()
    REFACTOR = auto()
    REVERT = auto()
    STYLE = auto()
    TEST = auto()


class Run(BaseModel):
    run_id: str = Field(pattern=r"^run_\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
    started_at: datetime
    completed_at: datetime | None = None
    status: RunStatus
    repos_processed: NonNegativeInt = 0
    repos_qualified: NonNegativeInt = 0
    total_commits_analyzed: NonNegativeInt = 0


class RepoRecord(BaseModel):
    run_id: str
    repo: str = Field(pattern=r"^[\w.-]+/[\w.-]+$")
    default_branch: str
    head_commit: str = Field(min_length=7, max_length=40)
    stars: Annotated[int, Field(ge=3)]
    language: str | None = None
    created_at: datetime
    license: str | None = None
    timestamp: datetime
    commits_analyzed: NonNegativeInt
    build: NonNegativeInt = 0
    chore: NonNegativeInt = 0
    ci: NonNegativeInt = 0
    docs: NonNegativeInt = 0
    feat: NonNegativeInt = 0
    fix: NonNegativeInt = 0
    perf: NonNegativeInt = 0
    refactor: NonNegativeInt = 0
    revert: NonNegativeInt = 0
    style: NonNegativeInt = 0
    test: NonNegativeInt = 0


class SearchCursor(BaseModel):
    stars_range: str
    page: Annotated[int, Field(ge=1)]


class Progress(BaseModel):
    key: str
    value: str | SearchCursor
    updated_at: datetime


class CommitTypeCounts(BaseModel):
    build: NonNegativeInt = 0
    chore: NonNegativeInt = 0
    ci: NonNegativeInt = 0
    docs: NonNegativeInt = 0
    feat: NonNegativeInt = 0
    fix: NonNegativeInt = 0
    perf: NonNegativeInt = 0
    refactor: NonNegativeInt = 0
    revert: NonNegativeInt = 0
    style: NonNegativeInt = 0
    test: NonNegativeInt = 0


class Methodology(BaseModel):
    min_stars: int = 3
    max_commits_per_repo: int = 100
    time_window_days: int = 365
    excluded: list[str]


class ExportData(BaseModel):
    run_id: str
    generated_at: datetime
    total_repos: NonNegativeInt
    total_commits: NonNegativeInt
    counts: CommitTypeCounts
    methodology: Methodology
```

---

## 7. Retention Policy

**Rule**: Keep only the 3 most recent completed runs.

**On Run Completion**:

1. Mark run as `completed` or `failed`
2. Query all runs, sort by `started_at` descending
3. Identify runs beyond the 3rd most recent
4. Delete those runs from `runs.json`
5. Delete associated repo records from `repos.json`
6. Historical data remains accessible via git history

**Invariant**: At most 3 completed runs exist in storage at any time.

---

## 8. Storage Edge Cases & Error Handling

### Missing vs Empty Storage Files

| Scenario | Behavior |
| -------- | -------- |
| File does not exist | Create new empty TinyDB table; proceed normally |
| File exists but is empty (0 bytes) | Treat as corrupted; log warning and recreate |
| File exists with valid JSON `{}` | Valid empty table; proceed normally |
| File exists with invalid JSON | Treat as corrupted (see below) |

### Corrupted Progress File Handling

When `progress.json` is corrupted (invalid JSON, missing required keys, or fails schema validation):

1. Log warning with specific corruption details
2. **If `--resume` flag was used**: Exit with error code 1 and message: "Progress file corrupted. Run without --resume to start fresh collection."
3. **If fresh collection (no `--resume`)**: Delete corrupted progress file and start new collection
4. **Never silently ignore corruption** - always inform the user

### Schema Migration Policy

**Current Policy**: No automatic schema migration.

**Rationale**: This is a demo project with TinyDB storage. Schema changes between versions are handled by:

1. Existing data remains valid (additive changes only)
2. Breaking changes are avoided in minor releases
3. If breaking changes are necessary: document in CHANGELOG and advise users to `prune --keep 0` before upgrading

**Future Consideration**: If schema migration becomes necessary, implement via a `migrate` CLI command that transforms data in-place with backup.
