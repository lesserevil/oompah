---
id: OOMPAH-284
type: task
status: Open
priority: null
title: Fix Release Delivery task associations and metadata-only filtering
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-21T03:38:39.097123Z'
updated_at: '2026-07-21T03:41:33.096937Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Bug: Trickle release/0.11 Release Delivery shows no needs-delivery task rows despite 44 substantive commits reachable from main and absent from release/0.11. The current association path assigns broad branch history to a merged task (for example TRICKLE-12 receives 3,012 commits), including commits already ancestral to release/0.11. The aggregate then marks every task row delivered by ancestry and the default needs-delivery filter hides all 23 rows.\n\nImplement: (1) associate a merged task/epic only with commits introduced by its PR/merge, excluding inherited/base-branch history; (2) exclude commits whose changed paths are exclusively .oompah/ from Release Delivery candidate, association, ancestry, and unassociated diagnostics results; (3) keep mixed code-plus-.oompah commits eligible; (4) invalidate/rebuild cached backlogs after the fix.\n\nTests: construct a repo where a task branch contains inherited release-branch history plus one new code commit and metadata-only commits; verify only the new code commit appears as needs delivery. Add a regression fixture matching the Trickle pattern and assert default backlog exposes pending task rows for a release branch behind main.\n\nAcceptance criteria: a task with inherited commits already on the target release branch is not falsely delivered when its introduced code commit is absent; metadata-only commits never appear as deliverable rows; mixed commits remain visible.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

