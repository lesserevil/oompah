---
id: OOMPAH-655
type: task
status: In Progress
priority: null
title: Enforce full-gate service isolation outside candidate branch code
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-31T10:36:19.315184Z'
updated_at: '2026-07-31T10:39:40.874465Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: c4b23c89dcfc0193c43c11b0db6cfe4a74992181d8fcf9756474c5929cc1a56c
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-07-31T10:39:27.536184+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\n\nDuplicate preflight verdict: no_duplicate\n\
    \nMatches: none\n\nEvidence: Reviewed the authoritative state-branch records for\
    \ OOMPAH-619, 623, 650\u2013654 and historical matches. OOMPAH-652 is merged and\
    \ the active tasks have distinct scopes; no active duplicate exists."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
oompah.agent_run_id: 5f8d0cf1-7f01-48be-916e-0905e57ca0cb
oompah.task_costs:
  total_input_tokens: 2697692
  total_output_tokens: 7615
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 2697692
      output_tokens: 7615
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 2697692
    output_tokens: 7615
    cost_usd: 0.0
    recorded_at: '2026-07-31T10:39:27.535729+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-655__20260731T103632Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-655
    source_sha: ec0ec7d89fb8804571fcf7e780558e6d979b73ea
    completed_at: '2026-07-31T10:39:27.539684+00:00'
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
author: oompah
created: 2026-07-31 10:39
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 25
- Tokens: 2.7M in / 7.6K out [2.7M total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 58s
- Log: OOMPAH-655__20260731T103632Z.jsonl
---
author: oompah
created: 2026-07-31 10:39
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-31 10:39
---
Focus: Maintenance Engineer
---
<!-- COMMENTS:END -->
