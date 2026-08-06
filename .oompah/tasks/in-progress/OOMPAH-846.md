---
id: OOMPAH-846
type: bug
status: In Progress
priority: 1
title: Enforce validation-resource leases for every spawned worker command path
parent: OOMPAH-763
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-06T04:12:19.034116Z'
updated_at: '2026-08-06T04:31:28.555626Z'
work_branch: epic-OOMPAH-763--task-OOMPAH-846
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: b1eb4300e6f8f1f1f6ebbfef7a4c528408e31166bab0ca036707120e840ffa9f
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-06T04:17:28.842530+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: The supplied corpus includes OOMPAH-816 (Done), which\
    \ introduced validation_resource_lease for exact gates and auditors, and OOMPAH-841\
    \ (Done), which prevents guards from capturing provider bootstrap processes. Neither\
    \ addresses the regression described in OOMPAH-846: that worker commands from\
    \ systems like OOMPAH-808 and OOMPAH-844 can spawn pytest and make test processes\
    \ outside any validation-resource lease, bypassing enforcement based on command\
    \ path. Active tasks OOMPAH-809 (scheduler lanes), OOMPAH-831 (auditor tools),\
    \ OOMPAH-847 (test isolation), and OOMPAH-811 (integration rearm) address distinct\
    \ concerns. This is a confirmed new regression requiring universal command-path\
    \ guard installation, not a duplicate of prior work.\nI'll conduct a thorough\
    \ duplicate screening of OOMPAH-846 by examining the supplied project task corpus.\n\
    \n## Analysis of OOMPAH-846\n\n**Current Issue**: Enforce validation-resource\
    \ leases for every spawned worker command path\n\n**Core Problem**: Live regression\
    \ where worker commands (OOMPAH-808, OOMPAH-844) launched pytest and make test\
    \ processes outside the durable lease introduced by OOMPAH-816. The enforcement\
    \ is path-dependent\u2014some command paths respect the lease, others bypass it.\n\
    \n**Scope**: Universally install fail-closed validation-resource guards before\
    \ process launch across all provider/native worker shell paths (Codex/Claude/OpenCode/API/ACP).\n\
    \n## Examining Active (Non-Terminal) Peer Tasks\n\n### OOMPAH-816 (Done) \u2014\
    \ Foundational but Different Scope\n- Introduced `validation_resource_lease` for\
    \ **exact quality gates and auditors only**\n- Addressed heavyweight auditor validation\
    \ concurrency with exact gates\n- Does not cover spawned worker commands\u2014\
    this is the gap OOMPAH-846 addresses\n- Not a duplicate; this is the prerequisite\
    \ that revealed the regression\n\n### OOMPAH-841 (Done) \u2014 Related but Opposite\
    \ Problem  \n- \"Keep native validation guards **off** provider bootstrap processes\"\
    \n- Prevents guards from falsely capturing Codex bootstrap processes\n- Different\
    \ concern: ensuring guards are placed correctly, not universally enforcing them\n\
    - Not a duplicate; complements validation-guard placement\n\n### OOMPAH-809 (Open)\
    \ \u2014 Scheduler Lanes, Not Validation Guards\n- \"Reserve workflow-repair capacity\
    \ while terminal audits drain\"\n- Addresses agent/provider slot starvation and\
    \ scheduler lane reservation\n- Separate from per-command validation-resource\
    \ enforcement mechanism\n- Not a duplicate\n\n### OOMPAH-808 (In Progress) \u2014\
    \ Named in the Bug, Not the Fix\n- OOMPAH-808 worker is mentioned as launching\
    \ raw pytest **outside the lease**\n- This task is about fencing nested-epic dispatch\
    \ prerequisites\n- Not addressing validation-resource enforcement itself\n- Not\
    \ a duplicate\n\n### OOMPAH-"
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 3a919a74-56ca-4c55-a4cb-78911933ff4f
oompah.work_branch: epic-OOMPAH-763--task-OOMPAH-846
oompah.integration:
  version: 2
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-763--task-OOMPAH-846
  base_branch: epic-OOMPAH-763
  base_sha: 93cc4c85664bfba06c82ac04ab66329c7f378832
  updated_at: '2026-08-06T04:19:23.648706+00:00'
oompah.task_costs:
  total_input_tokens: 10
  total_output_tokens: 2309
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 10
      output_tokens: 2309
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 2309
    cost_usd: 0.0
    recorded_at: '2026-08-06T04:17:28.840681+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-846__20260806T041358Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: epic-OOMPAH-763--task-OOMPAH-846
    source_sha: 93cc4c85664bfba06c82ac04ab66329c7f378832
    completed_at: '2026-08-06T04:17:28.863316+00:00'
---
## Summary

Live regression on 2026-08-06 after OOMPAH-816 reached Done: while the exact OOMPAH-831 gate owned the sole validation-resource slot, the OOMPAH-808 worker launched raw focused pytest and the OOMPAH-844 worker launched a raw make test process outside the durable lease. OOMPAH-844 make test remained alive when the scheduler started OOMPAH-791 exact gate, recreating the host saturation that OOMPAH-816 promised to prevent. OOMPAH-784/O845 commands used the mediated path and waited, proving command-path-dependent enforcement. Implementation scope: trace every spawned provider/native worker shell path (Codex/Claude/OpenCode/API/ACP) and install one fail-closed validation-resource guard before process launch; classify full Make targets and substantial pytest commands consistently; ensure exact gates own priority, queue time does not consume runtime deadline, cancellation/restart/fencing are preserved, and no environment/path variation can bypass the guard. Reuse OOMPAH-816 validation_resource_lease rather than building a parallel lock. Surface normal waits as informational and make bypass attempts observable without leaking command contents. Required tests: provider-native command execution from every backend while an exact gate owns capacity; raw make test, python -m pytest, uv run pytest, multi-file and compound commands; bounded node/small-file policy; cancellation/restart/owner death; prove at the process table boundary that no heavyweight child is spawned until lease acquisition; exact gate begins immediately after an earlier worker release. Acceptance: at configured capacity 1, no combination of server-spawned worker/auditor commands and exact gates can produce two concurrent heavyweight pytest trees, and all existing OOMPAH-816 security, timeout, fairness, and evidence-reuse tests remain green.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-06 04:13
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-06 04:13
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-06 04:16
---
Second live reproduction at 04:14-04:17 UTC: OOMPAH-808 provider-native command spawned PYTHONPATH=. ... python -m pytest over tests/test_integration_record.py, tests/test_parallel_epic_children.py, and tests/test_epic_strategy.py while OOMPAH-791 exact gate was the sole recorded validation owner. No worker waiter/owner existed for OOMPAH-808. The exact sandbox process tree confirmed concurrent pytest. Operator terminated only the stray sandbox PID 2783035 after coordination; OOMPAH-808 edits and agent session remain intact. This three-file shape must classify heavyweight and must be blocked before spawn.
---
author: oompah
created: 2026-08-06 04:17
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 2.3K out [2.3K total]
- Cost: $0.0000
- Exit: normal, Duration: 3m 58s
- Log: OOMPAH-846__20260806T041358Z.jsonl
---
author: oompah
created: 2026-08-06 04:19
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-06 04:19
---
Focus: Oompah Tests Auth Specialist
---
author: oompah
created: 2026-08-06 04:20
---
Third live reproduction at 04:20 UTC: OOMPAH-795 provider-native Codex paths concurrently spawned absolute /home/shedwards/src/oompah/.venv/bin/python pytest commands over three files (retry_authority_generation/auto_concurrency/default_first_dispatch) and two files (submit_queue_concurrency/stall_to_dispatch_recovery) while OOMPAH-791 owned capacity=1. Neither appeared in validation-resource owners/waiters. Operator terminated only top-level sandboxes 2871518/2871522; worker and dirty worktree were preserved. Enforcement must cover parallel tool calls and absolute interpreter paths before spawn.
---
author: oompah
created: 2026-08-06 04:31
---
Live reproduction at 2026-08-06T04:29Z: OOMPAH-847 spawned two provider-native command sandboxes (top PIDs 2957672 and 2961523) running absolute-venv pytest against tests/test_epic_strategy.py and tests/test_dispatch_lane_contract.py while the authoritative OOMPAH-791 make test gate was starting. Both bypassed the validation-resource lease. I terminated only those two test sandboxes; their implementation edits remain intact. This is direct evidence that worker command_execution paths must acquire the same lease as gates/auditors.
---
<!-- COMMENTS:END -->
