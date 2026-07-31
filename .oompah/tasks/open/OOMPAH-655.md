---
id: OOMPAH-655
type: task
status: Open
priority: null
title: Enforce full-gate service isolation outside candidate branch code
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-31T10:36:19.315184Z'
updated_at: '2026-07-31T10:36:31.766282Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: c4b23c89dcfc0193c43c11b0db6cfe4a74992181d8fcf9756474c5929cc1a56c
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: fbd0b9b1-5dc1-44fe-afe7-02166e1f78d1
  claim_owner: f6d86559-4e9d-42bf-ac66-416781dbb14f
  claimed_at: '2026-07-31T10:36:25.688036+00:00'
  claim_expires_at: '2026-07-31T11:06:25.688036+00:00'
  retry_count: 0
  retry_after: null
oompah.agent_run_id: 23e66880-628a-4786-9e29-2eb363e3d3e4
---
## Summary

Post-OOMPAH-652 deployment regression: the running server is isolated, but preserved candidate branches created before ec0ec7d89 still contain Makefiles that hard-code the canonical .oompah.pid and ignore OOMPAH_PYTEST_GATE/private lifecycle variables. Reopening OOMPAH-623/650/651/653 dispatched workers onto those exact old heads, so a branch-local make test or the exact review gate could still discover/signal the operator service until an operator fenced and rebased them. Candidate code cannot be trusted to implement its own containment boundary. Implementation scope: move or duplicate the critical gate isolation into the current server/runner-controlled launch boundary before executing any candidate command: private temp root, PID/meta files, port, HOME/tool state, process group/session capture, and exact ownership cleanup must be enforced even when the checked-out branch Makefile/scripts predate or ignore the variables. Detect non-cooperating lifecycle targets and either wrap/sandbox them safely or fail closed into Needs Rebase without starting the command. Integrate required-base repair for existing standalone and shared-epic task branches so a merged safety prerequisite cannot be declared available while their executable gate path omits it. Add regression fixtures using an intentionally old/malicious Makefile that reads canonical lifecycle files and tries broad cleanup, plus resumed clean and recovered branches behind main; prove the live sentinel/service survives, no worker starts before a required rebase when containment cannot be guaranteed, owned descendants are reaped, and normal current branches still gate. Acceptance: no candidate branch version can weaken the operator-service isolation boundary; stale resumed branches are safely repaired or fail closed with actionable state; focused lifecycle/integration tests and make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-31 10:36
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-31 10:36
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
