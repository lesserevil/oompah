---
id: TASK-402.10
title: Migrate Backlog config compatibility on startup and project add
status: Done
assignee:
  - oompah
created_date: '2026-06-01 19:25'
updated_date: '2026-06-09 00:29'
labels:
  - task
dependencies: []
parent_task_id: TASK-402
priority: high
ordinal: 22000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Add an oompah-owned Backlog.md compatibility migration check that runs when oompah starts and when a project is added.

Context:
- oompah is moving to Backlog.md as the required tracker.
- oompah now depends on a canonical Backlog status vocabulary, including Open, Backlog, Needs Answer, Needs Human, Decomposed, Duplicate Candidate, In Review, Needs CI Fix, Needs Rebase, Merged, and Archived.
- Existing projects may have a valid Backlog.md installation but an older backlog/config.yml with only To Do, In Progress, and Done.
- Today that mismatch causes later task edits or creates to fail when oompah tries to use newer statuses.
- This task should create a general compatibility/migration hook, not just a one-off status patch, because future oompah versions may require additional Backlog configuration checks.

Required behavior:
- On oompah service startup, inspect each repository's project-local Backlog config, such as `backlog/config.yml` in the main repo and in every configured project repo.
- When a project is added/registered, inspect that project repository's own `backlog/config.yml` before it is accepted or before agents can run against it.
- If Backlog.md is missing, continue to fail clearly with the existing requirement to run backlog init.
- If Backlog.md exists but its config is missing required oompah status options, update the config in place without deleting existing user statuses, labels, or unrelated config fields.
- The migration must be idempotent: running it repeatedly produces no further diff after the first successful update.
- The migration should preserve both existing Backlog.md config style and existing custom values where possible. Do not rewrite task files.
- The implementation should be structured so future config migrations can be added without scattering checks across startup and project creation paths.

Suggested design:
- Add a small Backlog compatibility module or helper, for example oompah/backlog_compat.py, with a function such as ensure_backlog_compatible(project_root: str | Path) -> BacklogCompatibilityResult.
- The result should describe whether Backlog was present, whether changes were made, and which migrations ran.
- The first migration should ensure required statuses are present.
- Add tests using temporary Backlog projects with minimal config.yml files.

Files to inspect first:
- oompah/projects.py
- oompah/__main__.py
- oompah/orchestrator.py
- oompah/tracker.py
- oompah/config.py
- tests/test_projects.py
- tests/test_backlog_tracker.py
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Oompah checks Backlog.md compatibility at service startup for all configured projects.
- [ ] #2 Oompah checks Backlog.md compatibility when a project is added or registered.
- [ ] #3 Required oompah statuses are added to backlog/config.yml without removing existing custom statuses or labels.
- [ ] #4 The migration is idempotent and future migrations can be added in one place.
- [ ] #5 Projects without Backlog.md still fail clearly with instructions to run backlog init.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Identify the startup path and project-add path where Backlog compatibility should be enforced.
2. Implement a reusable Backlog compatibility helper with an idempotent status-list migration.
3. Call the helper from startup/project loading and project creation/registration.
4. Add focused tests for missing Backlog config, old status list migration, custom statuses preserved, labels preserved, and idempotency.
5. Run focused tests, then make test if touched startup/project code has broad impact.
<!-- SECTION:PLAN:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Completed as part of the Backlog-only tracker migration. Removed Beads/bd runtime paths where applicable, moved lifecycle behavior to canonical Backlog.md statuses, updated UI/API/tests/docs for Backlog-only behavior, and verified with make test: 3677 passed.
<!-- SECTION:FINAL_SUMMARY:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Focused tests cover old config migration, idempotency, preservation of unrelated config, startup invocation, and project-add invocation.
- [ ] #2 No task files are rewritten by the compatibility migration.
<!-- DOD:END -->
