---
id: OOMPAH-578
type: task
status: In Review
priority: null
title: Prune terminal worktrees that use the legacy epic-task branch shape
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-30T03:38:06.370836Z'
updated_at: '2026-07-30T03:45:01.181241Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: d1960f5c80910ab045a91771a1fd1610b7de6041b4d14c65fedec22236127e64
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: bfacc1e4-289e-4291-97c2-eb14cd5e2cfc
  claim_owner: c148d053-52b8-4f8d-9ca8-c83978d885d6
  claimed_at: '2026-07-30T03:42:24.628994+00:00'
  claim_expires_at: '2026-07-30T04:12:24.628994+00:00'
  retry_count: 0
  retry_after: null
oompah.agent_run_id: a0ccc9a8-23ed-4903-bc6c-3201c8da1776
---
## Summary

Implementation scope: Extend OOMPAH-561 terminal cleanup compatibility for legacy task records whose exact Oompah-owned worktree/branch is named epic-<task-identifier> even though the tracker record type is task. Treat only the exact same-identifier legacy shape as owned; continue rejecting shared parent epic branches and arbitrary metadata. Remove the matching epic-named worktree before deleting its local/remote branch. Relevant code: oompah/projects.py and tests/test_projects.py (plus orchestrator cleanup tests if needed). Tests: reproduce an Archived task with work_branch=epic-TASK-42 and epic-TASK-42 worktree, prove worktree/local/remote cleanup; prove epic-TASK-EPIC for child TASK-42 remains protected; run focused project/orchestrator cleanup tests and the configured full gate. Acceptance criteria: legacy terminal Oompah workspaces are pruned on the normal 60-second cleanup cadence, exact ownership checks remain fail-closed, and active/shared/unmerged work is preserved.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-30 03:38
---
Reproduced live: archived OOMPAH-237, OOMPAH-323, and OOMPAH-325 retain registered epic-OOMPAH-* worktrees because their tracker type is task; cleanup removes neither the epic-named directory nor branch and logs an ownership rejection. Implementing exact same-identifier legacy compatibility while preserving shared-parent branch rejection.
---
author: oompah
created: 2026-07-30 03:42
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-30 03:42
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
