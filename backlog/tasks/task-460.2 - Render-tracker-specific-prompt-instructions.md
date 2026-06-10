---
id: TASK-460.2
title: Render tracker-specific prompt instructions
status: Done
assignee: []
created_date: '2026-06-08 17:57'
updated_date: '2026-06-10 03:49'
labels:
  - task
  - github-issues
  - tracker-migration
dependencies:
  - TASK-460.1
  - TASK-457.2
references:
  - plans/github-issues-tracker-migration.md
modified_files:
  - oompah/prompt.py
  - WORKFLOW.md
  - tests/test_prompt.py
parent_task_id: TASK-460
priority: high
ordinal: 132000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Update prompt rendering so the task reference section comes from the active tracker. GitHub-backed tasks should show oompah task commands and GitHub issue URL; legacy Backlog tasks may keep Backlog commands.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 GitHub-backed prompts do not include backlog task create/edit commands.
- [ ] #2 Legacy Backlog prompts remain functional for legacy dispatch.
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-10 03:40
---
Agent dispatched (profile: default)
---

author: oompah
created: 2026-06-10 03:42
---
Understanding: No duplicate found. This task needs to update prompt rendering so GitHub-backed tasks show oompah task commands (from TASK-460.1) and the GitHub issue URL (from TASK-457.2 Issue model), while legacy Backlog tasks keep existing Backlog CLI commands. Plan: (1) explore oompah/prompt.py and the Issue model, (2) identify where Backlog commands are currently rendered, (3) add tracker_kind-based branching, (4) add tests in tests/test_prompt.py, (5) update WORKFLOW.md if needed.
---

author: oompah
created: 2026-06-10 03:44
---
Discovery: Key findings: (1) Issue model (oompah/models.py) already has tracker_kind, provider_url, display_identifier fields from TASK-457.2. (2) _issue_to_template_vars() in prompt.py does NOT yet expose tracker_kind/provider_url/display_identifier/project_id to templates. (3) WORKFLOW.md has a static '## Backlog.md Quick Reference' section plus scattered backlog command references in Progress Comments, Missing capabilities, Handoff, and Instructions sections. Plan: add tracker fields to template vars in prompt.py, then update WORKFLOW.md with conditional blocks using {% if issue.tracker_kind == 'github_issues' %} to show oompah task commands for GitHub tasks and keep backlog commands for legacy tasks. oompah task create requires --project <project-id>, so project_id must also be added to template vars.
---

author: oompah
created: 2026-06-10 03:49
---
Implementation: Updated oompah/prompt.py to expose tracker_kind, provider_url, display_identifier, project_id from Issue to Liquid templates. Updated WORKFLOW.md with conditional {% if issue.tracker_kind == 'github_issues' %} blocks in: Quick Reference section, Progress Comments, Missing capabilities, Handoff, and Instructions close steps. GitHub tasks get oompah task commands + GitHub issue URL; legacy Backlog tasks keep existing backlog commands unchanged.
---

author: oompah
created: 2026-06-10 03:49
---
Verification: All 38 prompt tests pass (12 new tests in TestTrackerIdentityTemplateVars + TestTrackerSpecificConditionalRendering). Combined with existing tests: 151 tests pass across test_prompt.py, test_models.py, test_task_cli.py, test_workflow_loading.py. AC1 verified by test: GitHub-backed prompt contains oompah task commands and excludes backlog task create/edit. AC2 verified by test: legacy Backlog prompt retains all backlog commands unchanged.
---
<!-- COMMENTS:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Updated prompt rendering to be tracker-aware. (1) oompah/prompt.py: _issue_to_template_vars() now exposes tracker_kind, provider_url, display_identifier, project_id to Liquid templates. (2) WORKFLOW.md: all agent-facing command references (Quick Reference table, Progress Comments, Missing capabilities, Handoff, Instructions close) use {% if issue.tracker_kind == 'github_issues' %} conditional blocks — GitHub-backed tasks see oompah task commands + GitHub issue URL; legacy Backlog tasks keep backlog commands unchanged. (3) 12 new tests in tests/test_prompt.py verify both ACs end-to-end using the live WORKFLOW.md template.
<!-- SECTION:FINAL_SUMMARY:END -->
