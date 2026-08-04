---
id: OOMPAH-808
type: task
status: Open
priority: null
title: Fence nested-epic dispatch until prerequisite code is reachable
parent: OOMPAH-763
children: []
blocked_by: []
start_blocked_by: []
labels:
- human-only
assignee: null
created_at: '2026-08-04T21:45:34.568898Z'
updated_at: '2026-08-04T22:13:47.201484Z'
work_branch: epic-OOMPAH-763--task-OOMPAH-808
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: d7bddd80d28d0965f56d075e5545a112d35734356e7266b832f38aadfa7e69e0
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-04T22:07:57.743005+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: OOMPAH-808 is a specific implementation task addressing\
    \ the exact reproduction path of OOMPAH-796 \u2014 preventing stale nested-epic\
    \ dispatch by validating prerequisite code reachability before workspace launch.\
    \ Active peers OOMPAH-806/809/810 target related but distinct workflow concerns\
    \ (gate authority, capacity, transport). The task is correctly positioned as a\
    \ child of OOMPAH-763's workflow engine epic with its own narrow acceptance criteria\
    \ and test scope.\nLooking at OOMPAH-808 and comparing against the active tasks\
    \ in the provided corpus:\n\n**Analysis:**\n\nOOMPAH-808 addresses a specific\
    \ workflow engine defect: preventing dispatch of nested-epic children until all\
    \ prerequisite code is reachable from the actual dispatch base, using generation\
    \ CAS fencing and topology repair. The issue stems from a live reproduction (OOMPAH-796)\
    \ where a nested epic child was dispatched with a terminal prerequisite, but the\
    \ required contracts existed only on the parent epic branch, not on the stale\
    \ child base.\n\n**Examining active peer tasks:**\n\n- **OOMPAH-763** (parent\
    \ epic): Broader workflow engine migration; contains this task as a component\n\
    - **OOMPAH-767-770** (In Progress epics): Domain migration, liveness control,\
    \ transition service \u2014 orthogonal scopes\n- **OOMPAH-806** (In Progress):\
    \ \"Fence stalled-task recovery behind internal gate authority\" \u2014 addresses\
    \ watchdog authority, not dispatch precondition validation for nested epics\n\
    - **OOMPAH-807** (In Progress): Audit lifecycle for metadata-only Archived \u2014\
    \ unrelated\n- **OOMPAH-809** (Open): Scheduler capacity reservation \u2014 explicitly\
    \ references OOMPAH-808 as a related but distinct issue; about lane starvation,\
    \ not dispatch prerequisite checking\n- **OOMPAH-810** (Open): Auditor command\
    \ result delivery \u2014 unrelated\n\nNone of the active tasks describe preventing\
    \ nested-epic dispatch until hard-start prerequisite code is reachable from the\
    \ dispatch base with generation CAS fencing and topology repair.\n\n---\n\nFocus\
    \ handoff: duplicate_detector\n\nDuplicate preflight verdict: no_duplicate\n\n\
    Matches: none\n\nEvidence: OOMPAH-808 is a specific implementation task addressing\
    \ the exact reproduction path of OOMPAH-796 \u2014 preventing stale nested-epic\
    \ dispatch by validating prerequisite code reachability before workspace launch.\
    \ Active peers OOMPAH-806/809/810 target related but distinct workflow concerns\
    \ (gate authority, capacity, transport). The task is correctly positioned as a\
    \ child of OOMPAH-763's workf"
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 76b7829b-681e-4e55-a791-4004eb6e577c
oompah.work_branch: epic-OOMPAH-763--task-OOMPAH-808
oompah.integration:
  version: 2
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-763--task-OOMPAH-808
  base_branch: epic-OOMPAH-763
  base_sha: f1e7925b7263f980517f943291102c8c83335ed2
  updated_at: '2026-08-04T22:11:01.955812+00:00'
oompah.task_costs:
  total_input_tokens: 10
  total_output_tokens: 2000
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 10
      output_tokens: 2000
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 2000
    cost_usd: 0.0
    recorded_at: '2026-08-04T22:07:57.741390+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-808__20260804T220457Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: epic-OOMPAH-763--task-OOMPAH-808
    source_sha: f1e7925b7263f980517f943291102c8c83335ed2
    completed_at: '2026-08-04T22:07:57.768504+00:00'
---
## Summary

Live OOMPAH-796 reproduction on 2026-08-04: OOMPAH-770 and its private task branch were created at old main a681ec2fc. Hard-start prerequisite OOMPAH-785 was terminal and the server dispatched OOMPAH-796, but the required WorkDecision/job contracts existed only on the authoritative parent lineage epic-OOMPAH-763 at f1e7925b7. The worker therefore concluded the contract did not exist and was about to reinvent it. Operator workaround revoked the empty run and fast-forwarded epic-OOMPAH-770 plus the task branch to f1e7925b7. Implementation scope: before any nested-epic child workspace/claim/provider launch, resolve the immediate parent target and required hard-start landing heads; prove every required code head is reachable from the nested epic base and new private task base. If not, atomically suppress dispatch, publish a reason-coded waiting state, and schedule exactly one authorized parent-to-child epic topology repair using the OOMPAH-633/754 policy; never fall back to main or launch on a stale base. Fence repair versus dispatch/status/head changes with a generation CAS, recreate/advance the private task branch only after the repaired epic head is published, and resume naturally after restart. Relevant code: workspace creation/private branch base selection, duplicate-to-implementation handoff, hard-start prerequisite reachability, nested epic target resolution, integration staleness repair, task/health projections. Required tests: exact OOMPAH-770/796 old-main base with terminal prerequisite reachable only from epic-OOMPAH-763; zero worker/provider launch before repair; one correct fast-forward/rebase to immediate parent then one dispatch on the repaired SHA; concurrent dependency completion and dispatch; restart mid-repair; wrong/unresolved parent fails closed; standalone/top-level tasks unaffected. Acceptance: a terminal hard-start prerequisite cannot authorize implementation until its code is reachable from the actual dispatch base, and no nested worker can inspect or mutate a stale lineage.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-04 21:53
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-04 21:53
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-04 22:03
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 9m 53s
- Log: OOMPAH-808__20260804T215342Z.jsonl
---
author: oompah
created: 2026-08-04 22:04
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-04 22:04
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-04 22:08
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 2.0K out [2.0K total]
- Cost: $0.0000
- Exit: normal, Duration: 3m 24s
- Log: OOMPAH-808__20260804T220457Z.jsonl
---
author: oompah
created: 2026-08-04 22:10
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-04 22:11
---
Focus: Oompah Tests Auth Specialist
---
author: oompah
created: 2026-08-04 22:11
---
Understanding: nested-epic dispatch must prove hard-start prerequisite code is reachable from the actual epic and private-task bases before any workspace, claim, provider, or worker launch. I will trace existing target-resolution, reachability, repair, generation-CAS, and dispatch paths, then add a focused guard plus regression tests while preserving standalone/top-level behavior.
---
author: oompah
created: 2026-08-04 22:13
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 39
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 2m 27s
- Log: OOMPAH-808__20260804T221110Z.jsonl
---
author: oompah
created: 2026-08-04 22:13
---
Collision/topology fence: this implementation was dispatched from f1e7925b7 just as OOMPAH-806/807/796 were legitimately modifying projects.py/orchestrator.py/workflow_contract.py. No OOMPAH-808 edits existed, so the stale run was revoked cleanly. A direct hard-start edge to nested OOMPAH-796 was correctly rejected because it would create container reachability cycle OOMPAH-763 -> OOMPAH-770 -> OOMPAH-763. The temporary human-only label is therefore the explicit dispatch fence; remove it after OOMPAH-796 lands, then redispatch from the updated common root lineage. This is the exact topology bug OOMPAH-808 will fix.
---
<!-- COMMENTS:END -->
