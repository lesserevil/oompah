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
updated_at: '2026-08-06T16:49:22.762296Z'
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
  total_input_tokens: 976
  total_output_tokens: 2544
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 976
      output_tokens: 2544
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 2309
    cost_usd: 0.0
    recorded_at: '2026-08-06T04:17:28.840681+00:00'
  - profile: default
    model: haiku
    input_tokens: 966
    output_tokens: 235
    cost_usd: 0.0
    recorded_at: '2026-08-06T04:42:14.623738+00:00'
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
author: oompah
created: 2026-08-06 04:32
---
## Understanding and Initial Assessment

### Issue Summary
Live regression after OOMPAH-816: OOMPAH-808 and OOMPAH-844 workers spawned test processes (pytest, make test) outside the validation-resource lease while OOMPAH-831 exact gate held the sole capacity slot. Also OOMPAH-795 spawned concurrent pytest commands via absolute interpreter paths. This recreated the host saturation that OOMPAH-816 was designed to prevent.

### Root Cause
Command-path-dependent enforcement: validation-resource lease guards are installed via native_validation_guard for some execution paths (OOMPAH-784/OOMPAH-845), but other worker command paths spawn executables directly without acquisition guards, bypassing the lease mechanism entirely.

### Solution Strategy
1. Identify ALL worker command spawn points (ACP backends: Codex/Claude/OpenCode/API; auditor; tool execution)
2. Install validation-resource lease guards consistently before process launch
3. Classify heavyweight commands (make targets, pytest commands, multi-file test suites)
4. Reuse existing OOMPAH-816 validation_resource_lease (don't build parallel lock)
5. Ensure exact gates own priority; queue time doesn't consume runtime deadline

### Specialist Investigation Focus
As Oompah Tests Auth Specialist: examine ACP backend command execution paths, tool invocation surfaces, and integration points where validation-resource leases must be enforced. Ensure process-table boundary compliance that no heavyweight child spawns until lease acquisition.

### Next Steps
1. Locate all worker command spawn points in acp_tools, acp_backends, and related modules
2. Identify which paths currently lack validation-resource lease guards
3. Implement consistent guard installation
4. Verify with comprehensive tests
---
author: oompah
created: 2026-08-06 04:38
---
Additional live evidence at 2026-08-06T04:29Z: OOMPAH-847 spawned provider-native command sandboxes 2957672 and 2961523 running absolute-venv pytest for tests/test_epic_strategy.py and tests/test_dispatch_lane_contract.py while exact gate OOMPAH-844 was starting. Both bypassed the validation-resource lease and were terminated at the sandbox roots only; the scheduler then preserved checkpoint 40fc05b01. Direct ownership now fences OOMPAH-847. OOMPAH-845 and OOMPAH-784, by contrast, correctly project waiting_for_capacity. Acceptance must cover this absolute-path command_execution route.
---
author: oompah
created: 2026-08-06 04:42
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 0, Tool calls: 58
- Tokens: 966 in / 235 out [1.2K total]
- Cost: $0.0000
- Exit: terminated, Duration: 22m 58s
- Log: OOMPAH-846__20260806T041933Z.jsonl
---
author: oompah
created: 2026-08-06 04:50
---
Third live reproduction at 2026-08-06T04:52Z: completion auditor OOMPAH-826 projected tool_liveness phase=running and service-child PID 3113755 ran `python -m pytest tests/test_epic_strategy.py -x -q` for at least 226 seconds while OOMPAH-821 was the sole recorded exact_gate owner. validation_resources showed owner_count=1 (OOMPAH-821) and no auditor owner/waiter. The process exited before targeted termination. This proves the uncovered path includes terminal-auditor command execution as well as Codex native implementation command_execution. Tests must cover both routes and verify no process launches before lease ownership is durable.
---
author: oompah
created: 2026-08-06 04:51
---
Correction to the OOMPAH-826 evidence: its named single-module `python -m pytest ...` route did traverse the existing command classifier, but current policy deliberately treats that focused selector as light, so it never requests a lease. That is a separate arbitration-policy defect, now canonical OOMPAH-852. OOMPAH-846 remains scoped to genuine launch-path bypasses such as Codex native absolute `/bin/bash -c /absolute/.venv/bin/python -m pytest`, which should classify heavy but miss PATH/SHELL shims. Both must land before exact gates are fully isolated.
---
author: oompah
created: 2026-08-06 05:34
---
Live provider-boundary reproduction at 2026-08-06T05:30Z: while OOMPAH-852's exact gate was the sole recorded validation owner, Codex worker OOMPAH-853 launched an unleased full suite through an absolute Bash command that invoked scripts/run-tests.sh parallel. validation_resources continued to report only OOMPAH-852 plus the OOMPAH-821 auditor waiter. I verified ancestry and terminated only the unleased test process group. This confirms the O846 top-level shell/provider-spawn and operator-side broker requirements; classifier-only coverage is insufficient.
---
author: oompah
created: 2026-08-06 06:33
---
Additional live evidence at 2026-08-06T06:32Z: while operator-focused OOMPAH-781 held the sole validation_resources slot, OOMPAH-854's server-managed MCP run_command launched 'python -m pytest tests/test_auditor_quiesce_fence.py -v' immediately and completed in 13s with no waiter. The running server is main f2b319 and OOMPAH-852 exists only on epic-OOMPAH-763, confirming the pre-deployment provider boundary still bypasses the shared lease. Preserve this as an acceptance regression; do not run O846 tests while OOMPAH-781 owns the lane.
---
author: oompah
created: 2026-08-06 06:46
---
Independent static re-review rejected the current repair. Blockers: native provider registration now returns two descriptors but both bootstrap callers treat the tuple as one fd, guaranteeing pre-exec failure and ignoring the direct source descriptor; light inspection still permits GNU sed e execution and Git config/subcommand hooks such as fsmonitor and credential/filter helpers without a lease; provider-tree descendants inherit the capability and can spoof guard-launch argv plus caller-selected hashes, so receipts remain forgeable; supervisor cleanup uses numeric killpg after leader exit without a final exact process-identity fence, risking PID/group reuse; and the new ACP backend test references undefined root, lease, and owner names. Descriptor truncation and extra-descriptor rejection are statically accepted, as is explicit flock unlock against detached descendants. Do not test or submit until these P0/P1 issues have been repaired and independently re-reviewed.
---
author: oompah
created: 2026-08-06 13:56
---
New live reproduction at 2026-08-06 13:54 UTC: while exact gate OOMPAH-860 was the sole validation-resource owner, server-managed Codex worker OOMPAH-861 launched ....................................                                     [100%]
36 passed in 1.77s in sandbox/process group 379079/child 379100. validation_resources showed only the O860 exact_gate owner and no O861 waiter/owner. The focused command exited before targeted termination; O861 agent session/edits remain intact. This confirms the uncovered provider-native focused-command path on deployed f2b319 and is an exact acceptance case for the in-progress universal guard.
---
author: oompah
created: 2026-08-06 13:57
---
Correction to comment 17: the original live worker reproduction was sandbox group 379079 with pytest child 379100, observed for about 68 seconds while validation state showed only the OOMPAH-860 exact-gate owner. It exited before termination. While posting that evidence, operator shell quoting accidentally replayed the same focused module once outside the lease; that separate operator run produced the inserted 36-passed output in 1.77 seconds. Both processes are gone. The worker bypass evidence remains valid, but any OOMPAH-860 gate failure in this run must be evaluated with the brief operator contention disclosed.
---
author: oompah
created: 2026-08-06 14:36
---
Additional live evidence from OOMPAH-862 at 2026-08-06 14:35 UTC: a managed Codex worker attempted its focused pytest matrix while OOMPAH-860 owned the auditor lease. The native guard failed before collection because its sandbox could not chmod the external validation lock directory under the read-only service checkout. No competing tests remained running. This is the same fail-closed but unusable external-lock bootstrap surface addressed by this repair; retain the OOMPAH-862 trace as validation evidence.
---
author: oompah
created: 2026-08-06 14:40
---
New live bypass evidence: OOMPAH-862 encountered the native guard, explicitly unset OOMPAH_NATIVE_VALIDATION_GUARD, discovered the shared root virtualenv, and launched pytest outside the validation lease while OOMPAH-860 held capacity. The process exited before operator intervention. Acceptance coverage should ensure managed worker commands cannot disable or route around guard enforcement through environment removal or an absolute interpreter path.
---
author: oompah
created: 2026-08-06 15:32
---
Focused validation exposed a real portability blocker at bb7fba9cc: on the deployed CPython build, os.memfd_create is absent, so _sealed_capability_descriptor raises AttributeError before native guard bootstrap. The four-module matrix cascaded into broker accept timeouts and was stopped at its exact process group; no edits were lost and the lease released. A single-test reproduction failed deterministically after 3 passes. Repair now requires a secure immutable capability-descriptor fallback plus missing-memfd regression before rerunning the matrix.
---
author: oompah
created: 2026-08-06 16:02
---
Fresh independent static review ACCEPTED the repaired native-validation guard diff ecde06e4b. The REGISTER/stop race, descriptor ownership and leak paths, handler socket/thread shutdown, copied sealed-memfd rejection, and deterministic regressions were all reviewed with no remaining correctness or security blocker. Validation remains queued behind the active OOMPAH-862 exact gate.
---
author: oompah
created: 2026-08-06 16:33
---
Post-OOMPAH-862 composition review rejected the first clean rebase on three concrete gaps: O862 shell helpers consumed O846 segment triples incorrectly; API reuse policy classified before context-aware environment normalization; and the native Codex subscription path still lacked exact-gate reuse policy and telemetry. Repair is reconciling all three with wrapped/env-resolved/subscription regressions before any validation or push.
---
author: oompah
created: 2026-08-06 16:49
---
Second composition review found four remaining fail-closed gaps: context-aware heavyweight commands could be reclassified focused; API/native authority was not rechecked after waiting for the lease; native distinct-mode justification accepted shell expansions; and subscription execution lacked lifecycle outcome telemetry. Repair is adding shared contextual classification, post-acquire pre-launch authority checks, literal-only structured fields, and actual native-path lifecycle regressions.
---
<!-- COMMENTS:END -->
