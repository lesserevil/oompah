---
id: OOMPAH-616
type: bug
status: In Validation
priority: 1
title: Integrate terminal-audit retry ownership fencing
parent: OOMPAH-585
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-30T20:47:41.612111Z'
updated_at: '2026-07-30T20:54:51.659856Z'
work_branch: epic-OOMPAH-585--task-OOMPAH-616
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 54f20cacdfc4e9acc07a8fbb560a8db4079825625f6ad4d699372e0d32e4497c
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
  retry_after: '2026-07-30T20:49:48.290395+00:00'
oompah.agent_run_id: 666032db-c114-4d08-9f56-ece5bc8e02e0
oompah.work_branch: epic-OOMPAH-585--task-OOMPAH-616
oompah.integration:
  version: 1
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-585--task-OOMPAH-616
  base_branch: epic-OOMPAH-585
  base_sha: 45838987c7435c344c39cf77d0dd3ed1c135834c
  updated_at: '2026-07-30T20:54:49.494135+00:00'
oompah.task_costs:
  total_input_tokens: 294
  total_output_tokens: 74
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 294
      output_tokens: 74
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 294
    output_tokens: 74
    cost_usd: 0.0
    recorded_at: '2026-07-30T20:49:48.067654+00:00'
oompah.terminal_audit:
  queued_comment_posted: true
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-2461e8bb7254
    project_id: proj-14849f1b
    task_id: OOMPAH-616
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 0964ac8afc3b37e150cae341bca6d514ab7a10549b3e048759c6627ce31a2224
    attempts:
    - version: 1
      attempt_id: attempt-e22d7c6e350a
      target_state: Done
      request_state: in_progress
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 0964ac8afc3b37e150cae341bca6d514ab7a10549b3e048759c6627ce31a2224
      created_at: '2026-07-30T20:54:45.329403+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-07-30T20:54:45.329403+00:00'
      branch_key: epic-OOMPAH-585--task-OOMPAH-616
    requested_by:
      version: 1
      identity: oompah-integration
      source: service
    previous_state: Ready to Integrate
    created_at: '2026-07-30T20:54:24.446967+00:00'
    updated_at: '2026-07-30T20:54:45.329403+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-e22d7c6e350a
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 0964ac8afc3b37e150cae341bca6d514ab7a10549b3e048759c6627ce31a2224
    created_at: '2026-07-30T20:54:45.329403+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-07-30T20:54:45.329403+00:00'
    branch_key: epic-OOMPAH-585--task-OOMPAH-616
---
## Summary

Implementation scope: land the already implemented and fully tested OOMPAH-615 fix onto the OOMPAH-585 epic branch. Reuse commit ce8a124fc from origin/OOMPAH-615; resolve only genuine conflicts with the current epic head. The change must serialize terminal-audit staging against implementation In Progress writes, fence in-flight retry dispatch before worker creation, suppress normal-exit retries after an In Validation handoff, wake the audit lane after cleanup, and release the fence when an incomplete audit returns work to Open. Relevant files: oompah/orchestrator.py, oompah/server.py, tests/test_dispatch_close_race.py, tests/test_orchestrator_handlers.py, and tests/test_terminal_status_interfaces.py. Tests: run the focused scheduler/server/audit race suites on the combined epic tree; preserve the recorded full-gate evidence from ce8a124fc (terminal mutation scan passed; 13,736 passed, 7 skipped) and allow Oompah's exact combined-tree gate to run at integration. Acceptance criteria: the commit is pushed on the child's expected epic task branch, integration cannot regress In Validation to In Progress, no stale implementation worker can start after terminal ownership, and the child is submitted through the normal epic integration queue.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-30 20:47
---
Claimed directly by the operator Codex session to transplant the already-tested OOMPAH-615 commit onto the valid OOMPAH-585 epic branch; do not dispatch a second implementation agent.
---
author: oompah
created: 2026-07-30 20:48
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-30 20:48
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-30 20:49
---
Cherry-picked ce8a124fc cleanly onto origin/epic-OOMPAH-585 at combined-tree commit 45838987c and pushed the expected branch epic-OOMPAH-585--task-OOMPAH-616. Focused scheduler/server/audit suite on the combined tree: 408 passed.
---
author: oompah
created: 2026-07-30 20:49
---
Integrated the fully gated OOMPAH-615 ownership-race fix onto the OOMPAH-585 epic branch. Combined-tree focused regressions: 408 passed; source commit full gate: terminal mutation scan passed, 13,736 passed, 7 skipped.
---
author: oompah
created: 2026-07-30 20:49
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 0, Tool calls: 15
- Tokens: 294 in / 74 out [368 total]
- Cost: $0.0000
- Exit: terminated, Duration: 1m 20s
- Log: OOMPAH-616__20260730T204836Z.jsonl
---
author: oompah
created: 2026-07-30 20:54
---
Queued for terminal transition to Done. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-07-30 20:54
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-07-30 20:54
---
Focus: Completion Auditor
---
<!-- COMMENTS:END -->
