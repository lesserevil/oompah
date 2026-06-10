---
id: TASK-459.2
title: Make issue mutation endpoints backend-neutral
status: Merged
assignee: []
created_date: 2026-06-08 17:57
updated_date: 2026-06-10 03:12
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
oompah.task_costs:
  total_input_tokens: 113
  total_output_tokens: 49612
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 113
      output_tokens: 49612
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 113
    output_tokens: 49612
    cost_usd: 0.0
    recorded_at: '2026-06-09T23:00:26.515299+00:00'
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

author: oompah
created: 2026-06-09 23:00
---
Verification: All 84 targeted tests pass. Broader suite (479 tests) passes. Key acceptance criteria verified: (1) Tests confirm create/patch/comment/label endpoints dispatch exclusively through tracker.create_issue(), tracker.update_issue(), tracker.add_comment(), tracker.add_label(), tracker.remove_label() - backend agnostic; mock-based tests work with any tracker adapter. (2) _resolve_identifier() is tested to prefer issue_key body/query over path param (GitHub slash identifiers), and to URL-decode percent-encoded chars. TestAddLabelGitHubIdentifier.test_issue_key_body_overrides_path_identifier shows lesserevil/oompah-tasks#1234 is passed correctly to tracker without being confused by route parser.
---
<!-- COMMENT:BEGIN -->
index: 1
author: oompah
created: 2026-06-09 22:42

Agent dispatched (profile: default)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 2
author: oompah
created: 2026-06-09 22:42

Focus: Duplicate Investigator
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 3
author: oompah
created: 2026-06-09 23:00

Agent completed successfully in 1095s (49725 tokens)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 4
author: oompah
created: 2026-06-09 23:00

Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 171, Tool calls: 115
- Tokens: 113 in / 49.6K out [49.7K total]
- Cost: $0.0000
- Exit: normal, Duration: 18m 15s
- Log: TASK-459.2__20260609T224232Z.jsonl
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 5
author: oompah
created: 2026-06-10 02:46

Agent dispatched (profile: default)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 6
author: oompah
created: 2026-06-10 02:46

Focus: Duplicate Investigator
<!-- COMMENT:END -->
<!-- COMMENTS:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Made all issue mutation endpoints backend-neutral (TASK-459.2). Added three helpers to server.py: _resolve_identifier() (URL-decodes path params + supports issue_key body/query override for GitHub slash-identifiers), _managed_repo_slug() (https/ssh URL to owner/repo), _get_tracker_for_managed_repo() (project lookup by managed repo). Updated api_create_issue to require project_id OR managed_repo (400 if neither, 404 if no match). Updated api_update_issue, api_add_label, api_remove_label, api_add_comment, api_issue_full_detail to use _resolve_identifier and fall back to _find_tracker_for_issue when no explicit project_id. Added 28 new tests. Updated test_server_epic_state.py to reflect new behavior. All 479 tests pass. Branch epic-TASK-459 pushed.
<!-- SECTION:FINAL_SUMMARY:END -->
