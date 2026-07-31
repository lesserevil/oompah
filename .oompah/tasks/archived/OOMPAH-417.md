---
id: OOMPAH-417
type: task
status: Archived
priority: null
title: 'Regression tests: stall-to-recovery path and orphan-reset dispatch integration'
parent: OOMPAH-414
children: []
blocked_by:
- OOMPAH-415
- OOMPAH-416
labels: []
assignee: null
created_at: '2026-07-23T19:34:44.997439Z'
updated_at: '2026-07-31T06:01:30.457992Z'
work_branch: epic-OOMPAH-414
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: cfdf3167-0a32-448c-a1a5-ea7807fc0d0a
oompah.work_branch: epic-OOMPAH-414
oompah.terminal_audit:
  queued_comment_posted: true
  oompah.terminal_override_records:
  - version: 1
    override_id: override-4008da069b0b
    project_id: proj-14849f1b
    task_id: OOMPAH-417
    target_state: Archived
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: fa604df0422e6722c6a0cbc33114f01f40a0c858f3c46268ab822f66f3c6d23b
    authorized_by:
      version: 1
      identity: lesserevil
      source: api
    reason: Archive stale child of merged epic as superseded; undelivered combined
      regression is preserved in actionable top-level OOMPAH-640.
    created_at: '2026-07-31T06:01:20.101422+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-c99213bdc59f
    project_id: proj-14849f1b
    task_id: OOMPAH-417
    target_state: Archived
    request_state: superseded
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 1fc57444ac3d0a0247c6626edeb7d6f5f33f2a22b2281a4208c6b7eee70aca74
    attempts: []
    requested_by:
      version: 1
      identity: oompah
      source: auto_archive
    previous_state: Merged
    created_at: '2026-07-30T21:55:16.148863+00:00'
  - version: 1
    audit_id: audit-c82d10975d68
    project_id: proj-14849f1b
    task_id: OOMPAH-417
    target_state: Archived
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: fa604df0422e6722c6a0cbc33114f01f40a0c858f3c46268ab822f66f3c6d23b
    attempts:
    - version: 1
      attempt_id: attempt-06574e7cafd9
      target_state: Archived
      request_state: in_progress
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: fa604df0422e6722c6a0cbc33114f01f40a0c858f3c46268ab822f66f3c6d23b
      created_at: '2026-07-31T06:01:17.955642+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-07-31T06:01:17.955642+00:00'
      branch_key: epic-OOMPAH-414
    requested_by:
      version: 1
      identity: api-client
      source: api
    previous_state: Needs Human
    created_at: '2026-07-31T06:00:23.935672+00:00'
    updated_at: '2026-07-31T06:01:17.955642+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-06574e7cafd9
    target_state: Archived
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: fa604df0422e6722c6a0cbc33114f01f40a0c858f3c46268ab822f66f3c6d23b
    created_at: '2026-07-31T06:01:17.955642+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-07-31T06:01:17.955642+00:00'
    branch_key: epic-OOMPAH-414
---
## Summary

### Problem

There is no integrated regression test covering the full July 23 stall scenario: scheduler stalls, is detected within the new threshold (from OOMPAH-415), orphan resets are made (from OOMPAH-416), dispatch wakes, and eligible tasks are dispatched. The existing tests in test_dispatch_loop_heartbeat.py cover detection and recovery in isolation, but not the combined stall → orphan-reset → REFRESH_REQUESTED → dispatch path.

### Prerequisites

Depends on OOMPAH-415 (new dispatch_stale_threshold_ms config) and OOMPAH-416 (REFRESH_REQUESTED after orphan resets) being merged first.

### Scope

In tests/test_dispatch_loop_heartbeat.py (or a new file tests/test_stall_recovery_regression.py):

Add the following scenarios, following existing patterns using MagicMock orchestrators:

(a) Stall+recovery within new threshold:
  - Configure dispatch_stale_threshold_ms=2000 and dispatch_stale_grace_ms=500 (small values for fast test)
  - Advance time to simulate a stall past the threshold
  - Call check_and_recover_dispatch_loop() repeatedly; verify recovery is triggered before the old 15-minute threshold would have fired

(b) Orphan-reset + dispatch wake integration:
  - Set up an orchestrator with one orphaned In Progress task (no running agent)
  - Call _reset_orphaned_in_progress() and capture events posted
  - Verify a REFRESH_REQUESTED event was posted
  - Verify the task status was set to Open (via mock tracker)

(c) Exocomp-style clean dispatch after stall recovery:
  - Simulate a scheduler that stalled (no tick for 3 min) with no running agents
  - Trigger recovery (restart)
  - Simulate a fresh tick with two orphaned-then-reset tasks now Open
  - Verify both tasks are dispatched (dispatched_count == 2)

Also: run make test to verify the full test suite passes (all existing tests + new regression tests).

### Acceptance

make test passes cleanly. The three regression scenarios above are all green. The new tests would have caught the July 23 incident if they had existed before.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-23 21:08
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-23 21:08
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-23 21:09
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/default]
- Turns: 0, Tool calls: 7
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 1m 10s
- Log: OOMPAH-417__20260723T210806Z.jsonl
---
author: oompah
created: 2026-07-30 21:55
---
Queued Archived audit: Aged Merged auto-archive (closed 7 days ago). An auditor will review before the task is retired.
---
author: oompah
created: 2026-07-30 21:59
---
The parent epic OOMPAH-414 merged from epic-OOMPAH-414, but this task was In Validation with work branch epic-OOMPAH-414. Its work is not proven to be in the merged epic. Inspect the task's agent history and remote branches, recover any missing commits through a new recovery epic or approved follow-up PR, then move this task to Done only after the recovered work is verified on the target branch.
---
author: oompah
created: 2026-07-30 22:00
---
The parent epic OOMPAH-414 merged from epic-OOMPAH-414, but this task was Needs Human with work branch epic-OOMPAH-414. Its work is not proven to be in the merged epic. Inspect the task's agent history and remote branches, recover any missing commits through a new recovery epic or approved follow-up PR, then move this task to Done only after the recovered work is verified on the target branch.
---
author: oompah
created: 2026-07-31 06:00
---
Post-restart re-evaluation: the threshold and reset-wake portions landed with parent OOMPAH-414, but the combined two-task dispatch regression was not delivered. Remaining accepted work is now tracked actionably in top-level OOMPAH-640 because this child belongs to an already-merged epic. Archiving this stale child as superseded, not as fully completed.
---
author: oompah
created: 2026-07-31 06:01
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-07-31 06:01
---
Override by lesserevil: terminal transition to Archived applied by project owner.

Reason: Archive stale child of merged epic as superseded; undelivered combined regression is preserved in actionable top-level OOMPAH-640.
---
author: oompah
created: 2026-07-31 06:01
---
Run #1 [attempt=1, profile=auditor, role=— -> unknown/unknown]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 5s
---
author: oompah
created: 2026-07-31 06:01
---
Focus: Completion Auditor
---
<!-- COMMENTS:END -->
