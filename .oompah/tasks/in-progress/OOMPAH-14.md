---
id: OOMPAH-14
type: bug
status: In Progress
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
updated_at: '2026-06-20T03:39:55.845263Z'
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
<!-- COMMENTS:END -->
