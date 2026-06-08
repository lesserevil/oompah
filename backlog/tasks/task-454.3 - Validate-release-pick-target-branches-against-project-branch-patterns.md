---
id: TASK-454.3
title: Validate release-pick target branches against project branch patterns
status: Done
assignee: []
created_date: '2026-06-08 17:29'
updated_date: '2026-06-08 18:09'
labels:
  - task
dependencies:
  - TASK-454.1
parent_task_id: TASK-454
priority: high
ordinal: 93000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Add validation that requested release-pick targets match the managed project's configured branch patterns and are not protected source-only branches unless explicitly allowed. Return actionable errors for unknown or untracked targets.
<!-- SECTION:DESCRIPTION:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-08 17:57
---
Agent dispatched (profile: default)
---

author: oompah
created: 2026-06-08 17:58
---
Understanding: This is NOT a duplicate. TASK-456.5 surfaces validation errors in the UI; TASK-454.3 is about the backend validation logic that checks release-pick targets against configured branch patterns. TASK-454.1 (done) built the plumbing to read target_branch from task metadata. This task needs to validate those targets: match against project's configured branch patterns and reject protected source-only branches unless explicitly allowed. Plan: explore project config/branch pattern system, find where release-pick targets are resolved, add validation with actionable errors.
---

author: oompah
created: 2026-06-08 18:02
---
Discovery: Key findings: (1) Project model already has branches: list[str] (patterns like 'release/*'), default_branch: str, and matches_branch(name) method using fnmatch. (2) Issue model has target_branch: str | None (populated from oompah.target_branch frontmatter by TASK-454.1). (3) oompah.backports / oompah.backport_of metadata lives in tracker, not Issue model. Plan: create oompah/release_pick_validation.py with validate_release_pick_target() and validate_backports_list() functions. Wire validate_release_pick_target into orchestrator._should_dispatch as a gating check. Tests in tests/test_release_pick_validation.py.
---

author: oompah
created: 2026-06-08 18:08
---
Implementation: Created oompah/release_pick_validation.py with: (1) validate_release_pick_target(issue, project, tracker=None) — validates issue.target_branch against project.branches patterns (fnmatch); rejects source-only branch for backport issues unless backport:allow-source label is present; (2) validate_backports_list(backports, project) — validates oompah.backports list entries; (3) _is_release_pick_issue() — detects backport tasks via tracker metadata or 'backport'/'backport:*' labels. Wired validate_release_pick_target into orchestrator._should_dispatch after duplicate_candidate check — rejects with reason 'invalid_target_branch:untracked_branch' or 'invalid_target_branch:source_only_branch'. Project lookup gracefully skipped when project_id or project not found. 44 new tests in tests/test_release_pick_validation.py.
---

author: oompah
created: 2026-06-08 18:09
---
Verification: 44/44 new tests pass in tests/test_release_pick_validation.py. Related test suites also pass: test_backlog_tracker.py (50/50 including TASK-454.1 tests), test_models.py (122/122), test_candidate_preflight.py + test_close_gate.py + test_landing_gate.py (141/141), test_orchestrator_handlers.py + test_project_pause.py (302/302). Branch pushed to origin/epic-TASK-454.
---
<!-- COMMENTS:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Added oompah/release_pick_validation.py with validate_release_pick_target() and validate_backports_list(). Validates issue.target_branch against project.branches fnmatch patterns; blocks source-only (default) branch for backport issues unless backport:allow-source label present. Wired into Orchestrator._should_dispatch — invalid targets rejected with 'invalid_target_branch:untracked_branch' or 'invalid_target_branch:source_only_branch' and actionable error messages. 44 tests, all passing.
<!-- SECTION:FINAL_SUMMARY:END -->
