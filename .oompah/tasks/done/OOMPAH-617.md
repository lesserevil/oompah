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
updated_at: '2026-07-30T21:15:53.895149Z'
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
<!-- COMMENTS:END -->
