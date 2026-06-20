---
id: OOMPAH-14
type: bug
status: In Review
priority: 1
title: Preserve GitHub issue labels and type during native intake webhooks
parent: null
children: []
blocked_by: []
labels:
- bug
- native-tracker
- github-intake
- webhook
- metadata
assignee: null
created_at: '2026-06-20T03:03:06.527980Z'
updated_at: '2026-06-20T03:59:01.335315Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 512d45d6-22ac-4ede-bd49-da4944c61c85
---
## Summary

The native GitHub-intake webhook path does not normalize issue labels the same way the polling path does. In `github_intake_bridge._github_issue_from_event()`, the event issue is converted to an `Issue` with `issue_type="task"` and without user labels, even when the GitHub issue payload contains template labels such as `type:bug`, `type:feature`, or routing labels.

The polling path calls `GitHubIssueTracker.fetch_all_issues()`, which does extract status, priority, type, parent, dependencies, and user-facing labels from the GitHub issue labels/body. If a webhook creates the native task before the polling fallback sees it, the native task can permanently lose the intended issue type/labels because existing imports are only reconciled for status/comments.

Expected behavior:
- Webhook-driven native GitHub intake and polling-driven intake should produce equivalent native task metadata.
- Template-created GitHub issues with `type:*` labels should become native tasks with the correct issue type.
- User/routing labels should be preserved when imported.

Acceptance criteria:
- Refactor webhook issue normalization to share the same GitHub issue parsing logic as `GitHubIssueTracker` or otherwise parse the same fields.
- Add tests for a native-intake `issues.opened` webhook carrying `type:bug`, priority, parent/dependency, and routing labels.
- Existing native import reconciliation should update missing type/labels when safe, or document and test why it must not.
- Polling and webhook import paths produce matching native issue type and labels for the same GitHub payload.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-20 03:36
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-06-20 03:36
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-06-20 03:36
---
Understanding: This issue reports that the native GitHub-intake webhook path (github_intake_bridge._github_issue_from_event()) does not parse issue labels the same way the polling path does (GitHubIssueTracker.fetch_all_issues()). Webhook-created native tasks lose type:*, priority, parent, dependency, and routing labels. Plan: First investigating whether this is a duplicate of an existing issue before any implementation.
---
author: oompah
created: 2026-06-20 03:37
---
Duplicate investigation complete: No duplicate found. OOMPAH-12 involves labels in the dashboard UI (different problem). OOMPAH-11 is about template endpoints. No existing task covers the webhook _github_issue_from_event() label normalization bug. Proceeding with implementation.
---
author: oompah
created: 2026-06-20 03:39
---
Discovery: Two root causes found:

1. _github_issue_from_event() in github_intake_bridge.py constructs Issue with hardcoded issue_type='task' and no label parsing, even though event.raw['issue'] has the same label structure as the GitHub API response. The fix: import _gh_issue_to_issue from github_tracker.py and call it when the issue dict has a number.

2. ensure_native_issue_for_github_issue() calls native_tracker.create_issue() with issue_type='task' (hardcoded) and labels=['external:github'] only — ignoring the issue_type, labels, parent_id, and priority already parsed on the github_issue object.

The polling path calls GitHubIssueTracker.fetch_all_issues() which calls _gh_issue_to_issue() and correctly extracts type:*, priority:*, parent:*, depends-on:*, and user-facing labels. The webhook path skips all that.

Additionally: _reconcile_native_status_from_github_issue() only reconciles open/closed state but never updates type/labels on already-imported tasks, so once a task is imported without correct metadata, it stays wrong.
---
author: oompah
created: 2026-06-20 03:54
---
Implementation: Fixed three issues in oompah/github_intake_bridge.py:

1. _github_issue_from_event(): Now imports and calls _gh_issue_to_issue() from github_tracker when the webhook event has a full issue payload (issue.number present). This ensures type:*, priority:*, parent:*, depends-on:*, and user-facing labels are all extracted from the webhook payload identically to the polling path. The minimal Issue construction is kept as a fallback for edge cases.

2. ensure_native_issue_for_github_issue(): Now forwards issue_type, user-facing labels (+external:github), and parent_id from the parsed GitHub issue to native_tracker.create_issue(). Previously hardcoded issue_type='task' and labels=['external:github'].

3. Added _reconcile_native_type_and_labels() helper: Backfills missing type/labels on already-imported tasks when they still carry defaults (issue_type='task', no routing labels). Called from _reconcile_native_status_from_github_issue() so polling and webhook reconciliation both repair pre-fix tasks safely. Only adds labels, never removes; only updates type when it is still 'task'.

Also updated FakeNativeTracker in tests to support 'type' and 'add-label' update fields.

Added 16 new tests covering: label parsing from webhook payload, type/priority/parent/depends-on extraction, routing label preservation, ensure_native_issue forwarding, full webhook handler integration, polling==webhook equivalence, and reconciliation backfill.
---
author: oompah
created: 2026-06-20 03:54
---
Verification: All 6923 tests pass (28 skipped, 0 failures). The 28 new tests in test_github_intake_bridge.py all pass including: label parsing from webhook event payload, type/priority/parent/depends-on extraction, routing label preservation, ensure_native_issue forwarding all fields, full webhook handler integration (type:bug, priority:2, team-alpha labels), polling==webhook equivalence, and reconciliation backfill of missing type/labels on existing tasks.
---
author: oompah
created: 2026-06-20 03:56
---
Completion: Delivered fix for OOMPAH-14. No duplicate found (investigated OOMPAH-11, OOMPAH-12, OOMPAH-13 — all orthogonal). 

Changes pushed on branch OOMPAH-14:
- _github_issue_from_event() now calls _gh_issue_to_issue() (same logic as polling) when event has full issue dict — extracts type:*, priority:*, parent:*, depends-on:*, user labels
- ensure_native_issue_for_github_issue() forwards issue_type, user labels, parent_id to native create
- New _reconcile_native_type_and_labels() repairs pre-fix tasks: backfills type (if still default 'task') and adds missing labels without removing existing ones
- 16 new passing tests; full suite: 6923 passed, 28 skipped, 0 failures
---
author: oompah
created: 2026-06-20 03:56
---
Fixed webhook label normalization: _github_issue_from_event() now uses _gh_issue_to_issue() to parse type/priority/parent/labels from webhook payload identically to polling path; ensure_native_issue forwards all parsed fields to native create; new _reconcile_native_type_and_labels() backfills missing type/labels on existing tasks. 16 new tests added. All 6923 tests pass.
---
author: oompah
created: 2026-06-20 03:56
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 0, Tool calls: 76
- Tokens: 129 in / 3.6K out [3.7K total]
- Cost: $0.0000
- Exit: terminated, Duration: 20m 12s
- Log: OOMPAH-14__20260620T033644Z.jsonl
---
<!-- COMMENTS:END -->
