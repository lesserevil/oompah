---
id: TASK-458.7
title: Add GitHub tracker fake and contract coverage
status: Open
assignee: []
created_date: '2026-06-08 17:57'
updated_date: '2026-06-09 16:13'
labels:
  - task
  - github-issues
  - tracker-migration
dependencies:
  - TASK-458.6
  - TASK-457.4
references:
  - plans/github-issues-tracker-migration.md
modified_files:
  - tests
parent_task_id: TASK-458
priority: high
ordinal: 121000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Build fake GitHub fixtures or mocked REST/GraphQL responses that run the shared tracker contract suite and cover auth failures, rate limits, pagination, issue fields, body fallback, labels, comments, and relationship operations.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 GitHubIssueTracker passes all shared tracker contract tests.
- [ ] #2 Failure cases are tested without making live network calls.
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-09 13:30
---
Agent dispatched (profile: default)
---

author: oompah
created: 2026-06-09 13:41
---
Understanding: TASK-458.7 is NOT a duplicate. Searched for similar tasks (tracker contract, github tracker fake/mock) and found no prior implementation targeting GitHubIssueTracker in the shared contract suite. TASK-457.4 added shared contract tests for FakeTracker and BacklogMdTracker, and TASK-458.6 completed GitHubIssueTracker hierarchy/dependency support - both are Done and unblocked.

Plan:
1. Fix GitHubIssueTracker.create_issue to: (a) add parent:N label when parent= is given, (b) close the GitHub issue via PATCH when initial_status is terminal
2. Add _parse_comment_body helper and normalize fetch_comments/add_comment to return {author, text} keys (required by contract tests)
3. Create FakeGitHubHTTPServer class in test_shared_tracker_contract.py that intercepts httpx.Client.request calls and simulates GitHub REST API with in-memory state
4. Add github_tracker fixture and add 'github' to the tracker parametrize list
5. Run make test to verify all existing + new contract tests pass
---

author: oompah
created: 2026-06-09 13:53
---
Discovery: Root cause identified. The shared contract suite (test_shared_tracker_contract.py) runs against FakeTracker and BacklogMdTracker but NOT GitHubIssueTracker. Key gaps found:
1. GitHubIssueTracker.create_issue accepted parent= param but never encoded it as a parent:N label
2. create_issue didn't close issues on terminal initial_status (breaking fetch_issues_by_states for Done)
3. fetch_comments returned raw GitHub dicts without author/text keys (required by contract)
4. add_comment returned raw GitHub dict without author/text keys
5. get_metadata raised TrackerError for invalid identifiers instead of returning {}
6. _gh_issue_to_issue set id=database_id instead of id=canonical_identifier (breaking id==identifier contract)
---

author: oompah
created: 2026-06-09 13:53
---
Implementation: 6 changes made to oompah/github_tracker.py:
1. Added _COMMENT_BODY_RE regex and _parse_comment_body() helper to parse '**author**: text' format
2. create_issue: added parent:N label encoding when parent= argument is given
3. create_issue: added PATCH to close issue immediately when initial_status is terminal (e.g. 'Done')
4. fetch_comments: now adds author/text keys to each comment dict by parsing the oompah body format
5. add_comment: return dict now includes author and text keys alongside raw GitHub fields
6. _gh_issue_to_issue: id now equals identifier (canonical form) instead of GitHub's database ID
7. get_metadata: catches TrackerError on invalid identifier and returns {} instead of re-raising

Changes to tests/test_shared_tracker_contract.py:
- Added imports for unittest.mock.patch, httpx, urllib.parse
- Added FakeGitHubHTTPServer class (~160 lines) with in-memory issue/label/comment storage, routing all API calls to handlers
- Added github_tracker fixture that patches httpx.Client.request with the fake server
- Updated tracker parametrize from ['fake', 'backlog'] to ['fake', 'backlog', 'github']

Changes to tests/test_github_tracker.py:
- Updated test_id_uses_github_id → test_id_uses_canonical_identifier to reflect new id=canonical behavior
- Updated test_get_metadata_invalid_identifier_raises_tracker_error → returns {} instead of raising
---
<!-- COMMENTS:END -->
