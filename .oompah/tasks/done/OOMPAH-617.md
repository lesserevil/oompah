---
id: OOMPAH-617
type: bug
status: Done
priority: 1
title: Integrate wrong-checkout submission protection
parent: OOMPAH-587
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-30T20:52:01.122820Z'
updated_at: '2026-08-03T20:04:07.132638Z'
work_branch: epic-OOMPAH-587--task-OOMPAH-617
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.integration:
  version: 1
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-587--task-OOMPAH-617
  base_branch: epic-OOMPAH-587
  base_sha: a678afc20f9c2c97e9dd5bb54c09c2c10903d84c
  updated_at: '2026-07-30T21:08:18.043310+00:00'
oompah.terminal_audit:
  queued_comment_posted: true
  applied_result_attempts:
    attempt-8a965b580c4e: '2026-07-30T21:15:51.532400+00:00'
  oompah.terminal_override_records:
  - version: 1
    override_id: override-2983271eb6fc
    project_id: proj-14849f1b
    task_id: OOMPAH-617
    target_state: Merged
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 001b2658edcab54e88b8437d53e3c4a46b89e9de2bfbdff8376f59cd294043e2
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: 'Owner reconciliation: parent OOMPAH-587 is Merged and its accepted rollup
      contains this previously audited Done child; durable integration-queue/rollup
      evidence survives branch pruning. OOMPAH-699 tracks automatic convergence.'
    created_at: '2026-08-02T18:27:24.777976+00:00'
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-617
    target_state: Merged
    evidence_fingerprint: 001b2658edcab54e88b8437d53e3c4a46b89e9de2bfbdff8376f59cd294043e2
    audit_ids:
    - audit-a02347139d13
    kind: override
    applied: true
    retired_at: '2026-08-02T18:27:31.211329+00:00'
  oompah.terminal_audit_result_intents: []
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-a02347139d13
    project_id: proj-14849f1b
    task_id: OOMPAH-617
    target_state: Done
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 49a0b5c1d2193ea7a9cea17099e45f3ad8e31eb283141d1c1216b149b4ce357b
    attempts:
    - version: 1
      attempt_id: attempt-8a965b580c4e
      target_state: Done
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 49a0b5c1d2193ea7a9cea17099e45f3ad8e31eb283141d1c1216b149b4ce357b
      created_at: '2026-07-30T21:08:10.734806+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-07-30T21:08:10.734806+00:00'
      branch_key: OOMPAH-617
      verdict: pass
      completed_at: '2026-07-30T21:15:51.532259+00:00'
      ended_at: '2026-07-30T21:15:51.532259+00:00'
    requested_by:
      version: 1
      identity: oompah-integration
      source: service
    previous_state: Ready to Integrate
    created_at: '2026-07-30T21:08:02.464799+00:00'
    updated_at: '2026-07-30T21:15:51.532259+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-8a965b580c4e
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 49a0b5c1d2193ea7a9cea17099e45f3ad8e31eb283141d1c1216b149b4ce357b
    created_at: '2026-07-30T21:08:10.734806+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-07-30T21:08:10.734806+00:00'
    branch_key: OOMPAH-617
oompah.work_branch: epic-OOMPAH-587--task-OOMPAH-617
oompah.task_costs:
  total_input_tokens: 29
  total_output_tokens: 4853
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 29
      output_tokens: 4853
      cost_usd: 0.0
  runs:
  - profile: auditor
    model: unknown
    input_tokens: 29
    output_tokens: 4853
    cost_usd: 0.0
    recorded_at: '2026-07-30T21:16:02.482857+00:00'
---
## Summary

Implementation scope: land the already implemented OOMPAH-576 fix onto the OOMPAH-587 epic branch. Reuse commit 6f5a859b2 from origin/OOMPAH-576; resolve only genuine conflicts with the current epic head. The change must reject task submission from a service/default checkout before queue or tracker mutation, validate the expected task branch and pushed head, and prevent integration worktree reset when a queue branch disagrees with the registered worktree. Relevant files: oompah/acp_tools.py, oompah/integration.py, oompah/integration_executor.py, oompah/projects.py, oompah/server.py, and the existing OOMPAH-576 regression tests. Tests: run focused project/integration/task-handoff/worker-submission suites on the combined epic tree and allow Oompah's exact combined-tree gate at integration. Acceptance criteria: the expected epic task branch is pushed and submitted; wrong-checkout submission fails before mutation; correct submission still integrates; malformed queue state cannot rewrite a live task worktree; OOMPAH-576's observed main/worktree collision cannot recur.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-30 20:52
---
Claimed directly by the operator Codex session to transplant the already-tested OOMPAH-576 commit onto the valid OOMPAH-587 epic branch; do not dispatch a second implementation agent.
---
author: oompah
created: 2026-07-30 20:52
---
Cherry-picked 6f5a859b2 cleanly onto origin/epic-OOMPAH-587 at combined-tree commit a678afc20 and pushed the expected branch epic-OOMPAH-587--task-OOMPAH-617. Focused project/integration/task-handoff/worker-submission suite on the combined tree: 125 passed.
---
author: oompah
created: 2026-07-30 20:52
---
Integrated OOMPAH-576 wrong-checkout submission and worktree-reset protection onto the OOMPAH-587 epic branch. Combined-tree focused regressions: 125 passed; branch pushed at a678afc20.
---
author: oompah
created: 2026-07-30 21:08
---
Queued for terminal transition to Done. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-07-30 21:08
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-07-30 21:08
---
Focus: Completion Auditor
---
author: oompah
created: 2026-07-30 21:15
---
Operator note for the active completion auditor: the exact combined-tree integration gate already passed before a678afc20 was pushed onto origin/epic-OOMPAH-587 and the queue was marked integrated at 21:08:01. The focused branch verification was 125 passed. Do not invoke make test-serial: the currently deployed run_command wrapper blocks the scheduler until OOMPAH-618 lands. Inspect the committed diff/evidence and submit the audit result.
---
author: oompah
created: 2026-07-30 21:15
---
Audit PASS — Done

[REDACTED]

Safe evidence:
- branch_head: a678afc20f9c2c97e9dd5bb54c09c2c10903d84c
- branch_name: epic-OOMPAH-587--task-OOMPAH-617
- focused_tests: 125 passed in 4.56s across test_projects.py, test_integration_executor.py, test_integration_record.py, test_task_handoff.py, test_worker_submission.py
- source_commit: 6f5a859b2 (origin/OOMPAH-576) — transplanted content matches on OOMPAH-576 files
- git_status: up to date with origin/epic-OOMPAH-587; working tree clean
---
author: oompah
created: 2026-07-30 21:16
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/opus]
- Turns: 31, Tool calls: 23
- Tokens: 29 in / 4.9K out [4.9K total]
- Cost: $0.0000
- Exit: normal, Duration: 7m 50s
- Log: OOMPAH-617__20260730T211250Z.jsonl
---
author: oompah
created: 2026-07-31 05:03
---
Operator rebase bookkeeping: refreshed the terminal task branch from a678afc20 to its patch-equivalent rebased head b30aa99dd under an exact force-with-lease. The branch is now an ancestor of origin/epic-OOMPAH-587 (0 commits outside the epic); the newer wrong-worktree resolution remains preserved.
---
author: oompah
created: 2026-08-02 18:27
---
Override by oompah-cli: terminal transition to Merged applied by project owner.

Reason: Owner reconciliation: parent OOMPAH-587 is Merged and its accepted rollup contains this previously audited Done child; durable integration-queue/rollup evidence survives branch pruning. OOMPAH-699 tracks automatic convergence.
---
<!-- COMMENTS:END -->
