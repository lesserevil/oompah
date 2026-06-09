---
id: TASK-459.2
title: Make issue mutation endpoints backend-neutral
status: In Progress
assignee: []
created_date: '2026-06-08 17:57'
updated_date: '2026-06-09 22:59'
labels:
  - task
  - github-issues
  - tracker-migration
dependencies:
  - TASK-459.1
  - TASK-458.4
references:
  - plans/github-issues-tracker-migration.md
modified_files:
  - oompah/server.py
  - tests/test_server_issue_enhance.py
  - tests/test_server_label_api.py
parent_task_id: TASK-459
priority: high
ordinal: 124000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Update create, patch, comment, label, and detail endpoints so they call only tracker protocol methods and support GitHub-backed identifiers. Handle URL-encoded identifiers and require project_id or managed_repo when creating new tasks.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Create/update/comment/label endpoints work for GitHub and Backlog trackers in tests.
- [ ] #2 Route parsing cannot confuse slashes in fully qualified GitHub identifiers.
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-09 22:42
---
Agent dispatched (profile: default)
---

author: oompah
created: 2026-06-09 22:43
---
Understanding: After searching for duplicates (search: mutation endpoints, create patch comment, tracker protocol), confirmed this is NOT a duplicate - it's a unique subtask focused on making mutation endpoints backend-neutral. TASK-459.1 (Done) extended the schema for GET endpoints; this task covers write-path: create, patch, comment, label, and detail endpoints. TASK-458.4 (Backlog) is a blocker for GitHub implementation but I can make the server endpoints dispatch through the tracker protocol now. Plan: (1) Read current server.py mutation code and the tracker protocol; (2) Update create/patch/comment/label/detail endpoints to call tracker.create_issue, tracker.update_issue, etc.; (3) Handle URL-encoded identifiers; (4) Require project_id or managed_repo for creation; (5) Tests.
---

author: oompah
created: 2026-06-09 22:50
---
Discovery: No duplicate found - confirmed unique task. Current state: API endpoints already call tracker protocol methods (create_issue, update_issue, etc.). Gaps found: (1) No urllib.parse import for URL-decoding identifiers; (2) api_create_issue uses only project_id, needs managed_repo support; (3) api_update_issue strictly requires project_id (400 error) - should fall back to searching by identifier; (4) No issue_key body/query support for GitHub identifiers with slashes (since %2F is decoded to / before routing); (5) No URL-decoding in mutation endpoints. Plan: Add _resolve_identifier(), _managed_repo_slug(), _get_tracker_for_managed_repo() helpers; update create to accept project_id OR managed_repo; update patch/label/comment/detail to use _resolve_identifier + support managed_repo or fallback to _find_tracker_for_issue.
---

author: oompah
created: 2026-06-09 22:59
---
Implementation: Updated oompah/server.py with three new helpers: _resolve_identifier() (URL-decodes identifiers + supports issue_key body/query override for GitHub slash-identifiers), _managed_repo_slug() (extracts owner/repo from https/ssh remote URLs), _get_tracker_for_managed_repo() (finds project/tracker by managed code repo). Updated api_create_issue to require project_id OR managed_repo. Updated api_update_issue to remove strict project_id requirement - now falls back to _find_tracker_for_issue. Updated api_add_label, api_remove_label, api_add_comment, api_issue_full_detail to use _resolve_identifier and support managed_repo fallback. Updated tests/test_server_epic_state.py to reflect new behavior (missing project_id → 404 not 400). Added 28 new tests in test_server_issue_enhance.py (TestCreateIssueManagedRepo, TestResolveIdentifier, TestManagedRepoSlug, TestGetTrackerForManagedRepo) and test_server_label_api.py (TestAddLabelGitHubIdentifier, TestRemoveLabelGitHubIdentifier). 479 tests passing.
---
<!-- COMMENTS:END -->
