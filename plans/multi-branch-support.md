# Multi-Branch Support for Projects

## Overview

Projects can now track multiple branch patterns (beyond just `main`), including glob patterns like `release/*`, `hotfix/*`, with a configurable `default_branch` for new task worktrees.

## Motivation

- Track release branches (`release/*`) for backport tasks
- Track hotfix branches (`hotfix/*`) for urgent fixes
- Support monorepos with multiple release trains
- Allow tasks to target specific branches via `target_branch` field

## Data Model Changes

### Project Model (`oompah/models.py`)

**New Fields:**
- `branches: list[str]` - List of branch patterns to track (supports fnmatch globs)
- `default_branch: str` - Primary branch for new task worktrees

**New Methods:**
- `primary_branch` property - Returns `default_branch`
- `matches_branch(branch_name: str) -> bool` - Checks if branch matches any tracked pattern using fnmatch

**Backward Compatibility:**
- Legacy `branch` field retained (returns `default_branch`)
- `__post_init__` handles migration from old `branch` to new `branches`/`default_branch`
- `to_dict()` / `from_dict()` serialize both old and new fields

### Issue Model (`oompah/models.py`)

**New Field:**
- `target_branch: str | None` - Allows tasks to target specific branches

## Component Updates

### Tracker (`oompah/tracker.py`)
- Issue construction reads `target_branch` from tracker metadata

### ProjectStore (`oompah/projects.py`)
- `create()` accepts `branches` and `default_branch` parameters
- `create_worktree()` accepts optional `base_branch` parameter
- `create_epic_worktree()` uses `default_branch` instead of `branch`
- `sync_project_sources()` pulls from `default_branch`
- `UPDATABLE_FIELDS` includes `branches` and `default_branch`

### Orchestrator (`oompah/orchestrator.py`)
All `project.branch` references updated to `project.default_branch`:
- `_epic_auto_close_check()`
- `_resolve_epic_target_branch()`
- `_open_epic_main_prs()`
- `_ensure_review_exists()`
- `_run_verifier_for_completed_agent()`
- `_check_close_gate()`
- `_create_workspace_for_issue()` passes `issue.target_branch` to `create_worktree()`

### Server/Webhooks (`oompah/server.py`)
- `_webhook_advanced_tracked_branch()` uses `project.matches_branch()` for all tracked branches

### Prompt (`oompah/prompt.py`)
- `_project_to_template_vars()` uses `default_branch`

## API Endpoints

### POST `/api/v1/projects`
```json
{
  "repo_url": "https://github.com/org/repo.git",
  "name": "my-project",
  "branches": ["main", "release/*", "hotfix/*"],
  "default_branch": "main"
}
```

### PATCH `/api/v1/projects/{id}`
```json
{
  "branches": ["main", "release/*", "hotfix/*"],
  "default_branch": "main"
}
```

### GET `/api/v1/projects` / `/api/v1/projects/{id}`
Response includes:
```json
{
  "branch": "main",
  "branches": ["main", "release/*", "hotfix/*"],
  "default_branch": "main"
}
```

## UI (`/projects-manage`)

**Add Project Form:**
- "Branches (comma-separated, supports globs like release/*, hotfix/*)"
- "Default Branch (for new tasks)"

**Project Cards Display:**
- "Branches:" - comma-separated list
- "Default Branch:"

**Edit Project Form:**
- Same fields as Add form

## Branch Pattern Matching

Uses Python's `fnmatch` module for glob patterns:
- `main` - exact match
- `release/*` - matches `release/1.0`, `release/2.0`, etc.
- `hotfix/*` - matches `hotfix/urgent`, `hotfix/security`, etc.
- `feature/*` - matches any feature branch

## Testing

All 3635 tests pass including:
- `tests/test_projects_crud.py` - CRUD operations with new fields
- `tests/test_close_gate.py` - Close gate uses `default_branch`
- `tests/test_webhooks.py` - Webhook branch matching
- `tests/test_merge_queue.py` - Merge queue with multi-branch
- `tests/test_epic_auto_close.py` - Epic auto-close
- `tests/test_epic_strategy.py` - Epic shared workflow

## Migration Path

Existing projects with only `branch` field:
1. On load, `__post_init__` converts `branch` → `branches=[branch]`, `default_branch=branch`
2. On save, both old and new fields written
3. UI shows both legacy and new fields for gradual migration

## Future Considerations

- API for creating tasks targeting specific branch (`target_branch` on task create)
- Branch-specific agent profiles / concurrency limits
- Per-branch webhook filtering
- Release branch auto-detection from git tags
