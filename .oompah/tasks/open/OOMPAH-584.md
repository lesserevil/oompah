---
id: OOMPAH-584
type: epic
status: Open
priority: 1
title: Return the oompah delivery control plane to green
parent: null
children:
- OOMPAH-585
- OOMPAH-586
- OOMPAH-587
- OOMPAH-588
- OOMPAH-630
- OOMPAH-631
- OOMPAH-632
- OOMPAH-633
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-30T14:13:01.872040Z'
updated_at: '2026-07-31T05:02:56.762374Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Goal

Restore the oompah project to an objectively green state across service health, terminal auditing, task access, integration delivery, and repository hygiene. This epic coordinates four focused child epics; implementation belongs in their actionable children rather than in this umbrella branch.

Scope and acceptance

- The service is healthy, unpaused, restartable through documented Makefile targets, and operator/task-worker authentication succeeds with least privilege.
- Terminal audits dispatch successfully, pending/stale transitions recover, and alerts accurately represent failures and clear after recovery.
- No task is stranded in Ready to Integrate or In Validation; the OOMPAH-460 chain drains in dependency order and main remains clean.
- Worktree/branch cleanup runs without errors or warning floods, preserves dirty/unmerged work, and removes safe terminal artifacts.
- The merged-label maintenance lane is project-scoped and error-free.
- Focused tests cover every fix and the configured complete Makefile gate passes on each review-ready head.

Live evidence at creation

The service had 54 pending terminal audits; OOMPAH-580 and OOMPAH-582 were stale In Validation after auditor launch failures; OOMPAH-484 and OOMPAH-487 had real rebase conflicts; downstream OOMPAH-485/488/489 were waiting; OOMPAH-574/575/576/581 were Ready to Integrate without open PRs; managed cleanup retained 20 worktrees, 117 local branches, and 67 remote branches; merged_labels rejected legacy OOMPAH-476 because project_id was absent.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-30 14:18
---
Project-owner-approved green recovery work; dispatch under recorded dependencies and acceptance criteria.
---
author: oompah
created: 2026-07-30 14:27
---
Recovery graph created and accepted: child epics OOMPAH-585 through OOMPAH-588; implementation children OOMPAH-589 through OOMPAH-603. Finish-order and true hard-start edges are recorded. The live scheduler claimed OOMPAH-589 and OOMPAH-590 first; direct operator implementation is deferred while service workers are making progress. If the current broken terminal-audit runtime prevents the audit-fix epic from delivering, bootstrap those exact reviewed heads to main through the normal PR/full-gate path, then resume scheduler ownership.
---
<!-- COMMENTS:END -->
