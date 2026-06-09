---
id: TASK-459.6
title: Update create issue UI for GitHub-backed projects
status: In Progress
assignee: []
created_date: '2026-06-08 17:57'
updated_date: '2026-06-09 23:28'
labels:
  - task
  - github-issues
  - tracker-migration
dependencies:
  - TASK-459.2
  - TASK-459.5
references:
  - plans/github-issues-tracker-migration.md
modified_files:
  - oompah/templates/dashboard.html
  - tests/test_server_issue_enhance.py
parent_task_id: TASK-459
priority: high
ordinal: 128000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Revise the create issue modal so GitHub-backed projects create GitHub Issues through oompah, not Backlog.md files. Require a target managed project, expose target branch, issue type, priority, focus labels, and optional parent epic.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Creating a task for a GitHub-backed project never writes a Backlog task file.
- [ ] #2 The modal still supports legacy Backlog projects during transition.
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-09 23:17
---
Agent dispatched (profile: default)
---

author: oompah
created: 2026-06-09 23:19
---
Understanding: Task requires updating the create issue modal in dashboard.html so GitHub-backed projects (tracker_kind=github_issues) create GitHub Issues via the oompah API (not Backlog.md files). Two blockers (TASK-459.2, TASK-459.5) are Done. Plan: (1) Update server.py api_create_issue to parse and pass labels from request body to tracker.create_issue(); (2) Update dashboard.html create dialog HTML to add GitHub-specific fields: target branch (text input), focus labels (text input for comma-separated routing labels like needs:frontend), and parent epic selector dropdown; (3) Add JS: updateGitHubFieldsVisibility() to show/hide GitHub fields based on selected project's tracker_kind; hook into onCreateProjectChange(), openCreateDialog(), openCreateDialogForEpic(); update submitCreateDialog() and enhanceCreateDialog() to include new fields; (4) Legacy Backlog projects keep old behavior; (5) Tests: unit tests for server labels passthrough + dashboard HTML pattern tests for new create dialog fields.
---

author: oompah
created: 2026-06-09 23:20
---
Discovery: Found all relevant code. dashboard.html create dialog (line 5353) has project/type/title/priority/description fields but lacks target_branch, focus labels, and parent epic selector. server.py api_create_issue (line 1747) already accepts target_branch/managed_repo from request body but does NOT forward labels to tracker.create_issue(). Tracker protocol (tracker.py line 269) already defines create_issue(labels=). The fix requires: (1) server.py: parse body.get('labels') and pass to tracker.create_issue(); (2) dashboard.html: add create-github-fields div with target_branch input and focus_labels input; add isGitHubBacked() helper; add updateGitHubFieldsVisibility() called from onCreateProjectChange/openCreateDialog/openCreateDialogForEpic; update submitCreateDialog() and enhanceCreateDialog() to include new fields; (3) new test file for create dialog GitHub fields.
---

author: oompah
created: 2026-06-09 23:28
---
Implementation: Two files changed. (1) oompah/server.py: api_create_issue now parses 'labels' from request body (accepts JSON list or comma-separated string) and forwards it to tracker.create_issue(labels=). This enables routing labels like 'needs:frontend' to be stored on GitHub Issues. (2) oompah/templates/dashboard.html: Added #create-github-fields div (hidden by default) inside the create dialog with: Target Branch text input, Focus Labels text input (comma-separated), Parent Epic select dropdown. Added isGitHubBacked(projectId) helper. Added updateGitHubFieldsVisibility() that shows the GitHub section and populates the epic selector when the selected project has tracker_kind='github_issues'. Wired into onCreateProjectChange(), openCreateDialog(), openCreateDialogForEpic(). Updated submitCreateDialog() to include target_branch, labels array, and parent epic from the GitHub fields. Updated enhanceCreateDialog() to include target_branch for better enhancement context. CSS added for #create-github-fields section separator. Legacy Backlog projects: GitHub fields stay hidden because isGitHubBacked() returns false for projects without tracker_kind='github_issues'.
---

author: oompah
created: 2026-06-09 23:28
---
Verification: 45/45 new tests pass (10 server create labels tests + 35 dashboard create GitHub tests). 392/392 dashboard+server-issue tests pass. 373/373 tracker/config/projects/models tests pass. 266/266 server tests pass. No regressions found. AC #1 (GitHub-backed project never writes Backlog task): verified by server_create_labels tests showing labels/target_branch forwarded through tracker.create_issue() protocol (the same API endpoint that TASK-459.2 made backend-neutral). AC #2 (legacy Backlog projects still work): GitHub fields are hidden when isGitHubBacked() returns false, so legacy projects see no new UI changes.
---
<!-- COMMENTS:END -->
