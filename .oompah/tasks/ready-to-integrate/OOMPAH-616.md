---
id: OOMPAH-616
type: bug
status: Ready to Integrate
priority: 1
title: Integrate terminal-audit retry ownership fencing
parent: OOMPAH-585
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-30T20:47:41.612111Z'
updated_at: '2026-07-30T20:49:50.417525Z'
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
  state: ready
  attempts: 0
  task_branch: epic-OOMPAH-585--task-OOMPAH-616
  head_sha: 45838987c7435c344c39cf77d0dd3ed1c135834c
  submitted_at: '2026-07-30T20:49:32.032464+00:00'
  updated_at: '2026-07-30T20:49:32.032464+00:00'
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
<!-- COMMENTS:END -->
