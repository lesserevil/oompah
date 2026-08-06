---
id: OOMPAH-578
type: task
status: In Validation
priority: null
title: Prune terminal worktrees that use the legacy epic-task branch shape
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-30T03:38:06.370836Z'
updated_at: '2026-08-06T04:48:55.090571Z'
work_branch: OOMPAH-578
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/589
review_number: '589'
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: d1960f5c80910ab045a91771a1fd1610b7de6041b4d14c65fedec22236127e64
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: Duplicate screening worker was terminated.
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: '2026-07-30T03:45:21.070032+00:00'
oompah.agent_run_id: a0ccc9a8-23ed-4903-bc6c-3201c8da1776
oompah.review_url: https://github.com/lesserevil/oompah/pull/589
oompah.review_number: '589'
oompah.work_branch: OOMPAH-578
oompah.target_branch: main
oompah.task_costs:
  total_input_tokens: 470
  total_output_tokens: 155
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 470
      output_tokens: 155
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 470
    output_tokens: 155
    cost_usd: 0.0
    recorded_at: '2026-07-30T03:45:20.313058+00:00'
oompah.terminal_audit:
  queued_comment_posted: true
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-6058ba047ef0
    project_id: proj-14849f1b
    task_id: OOMPAH-578
    target_state: Archived
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 04ead9f2975e5d456c6bd8de782eb966b00345592b78bd70c1379ee237b9cbaf
    attempts: []
    requested_by:
      version: 1
      identity: oompah
      source: auto_archive
    previous_state: Merged
    created_at: '2026-08-06T04:48:49.630286+00:00'
  attempt_history: []
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
author: oompah
created: 2026-07-30 03:45
---
Implemented exact legacy ownership compatibility at commit d02fec346 and opened PR #589. Focused cleanup safety tests: 18 passed. Full make test: 13,618 passed, 7 skipped. The cleanup continues to reject child/shared epic branches that do not exactly match the terminal task identifier.
---
author: oompah
created: 2026-07-30 03:45
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 0, Tool calls: 25
- Tokens: 470 in / 155 out [625 total]
- Cost: $0.0000
- Exit: terminated, Duration: 2m 52s
- Log: OOMPAH-578__20260730T034233Z.jsonl
---
author: oompah
created: 2026-08-06 04:48
---
Queued Archived audit: Aged Merged auto-archive (closed 7 days ago). An auditor will review before the task is retired.
---
<!-- COMMENTS:END -->
