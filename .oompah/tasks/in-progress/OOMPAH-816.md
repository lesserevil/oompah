---
id: OOMPAH-816
type: task
status: In Progress
priority: null
title: Serialize heavyweight auditor validation with exact quality gates
parent: OOMPAH-763
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-05T00:38:32.940940Z'
updated_at: '2026-08-05T06:32:15.505092Z'
work_branch: epic-OOMPAH-763--task-OOMPAH-816
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: a3b09053b57c13511868aae9880d1dd498d09e7a9890e0decc3294148e57bf88
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-05T00:40:25.702491+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: OOMPAH-809 covers scheduler/provider lane reservation,\
    \ while OOMPAH-816 specifically addresses host CPU/disk serialization between\
    \ heavyweight quality gates and auditor commands. OOMPAH-810 covers result delivery,\
    \ and OOMPAH-814 covers fixture determinism; neither duplicates this resource-lease\
    \ problem.\nFocus handoff: duplicate_detector  \nDuplicate preflight verdict:\
    \ no_duplicate  \nMatches: none  \n\nEvidence: OOMPAH-809 covers scheduler/provider\
    \ lane reservation, while OOMPAH-816 specifically addresses host CPU/disk serialization\
    \ between heavyweight quality gates and auditor commands. OOMPAH-810 covers result\
    \ delivery, and OOMPAH-814 covers fixture determinism; neither duplicates this\
    \ resource-lease problem."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: eb00bf05-76d8-4991-8cb3-a53c8784bca9
oompah.work_branch: epic-OOMPAH-763--task-OOMPAH-816
oompah.integration:
  version: 2
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-763--task-OOMPAH-816
  base_branch: epic-OOMPAH-763
  base_sha: 30dc2b2075a48c6c542da55a46ad0285f492d527
  updated_at: '2026-08-05T00:43:34.229499+00:00'
oompah.task_costs:
  total_input_tokens: 47030
  total_output_tokens: 474
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 47030
      output_tokens: 474
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 46376
    output_tokens: 297
    cost_usd: 0.0
    recorded_at: '2026-08-05T00:40:25.700464+00:00'
  - profile: default
    model: haiku
    input_tokens: 654
    output_tokens: 177
    cost_usd: 0.0
    recorded_at: '2026-08-05T00:57:56.002637+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-816__20260805T004004Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: epic-OOMPAH-763--task-OOMPAH-816
    source_sha: 30dc2b2075a48c6c542da55a46ad0285f492d527
    completed_at: '2026-08-05T00:40:25.929743+00:00'
---
## Summary

Live reproduction on 2026-08-05: while the exact OOMPAH-813 four-worker combined-tree gate was running in isolated gate root oompah-quality-gate-cnd_e1it, the OOMPAH-508 completion auditor independently launched make test-serial in its audit attempt worktree. Both full pytest trees then had workers/processes blocked in jbd2_log_wait_commit. The preceding OOMPAH-807 and OOMPAH-814 gates each passed more than 15,000 tests but lost one unrelated five-second fixture under similar load. OOMPAH-814 fixes concrete leaky fixtures and OOMPAH-809 reserves scheduler/provider lanes; neither arbitrates host CPU/disk consumed by heavyweight commands after agents launch. Implementation scope: introduce a process-safe, restart-safe host/project validation resource lease shared by BranchQualityGate and auditor MCP run_command execution. Classify full Makefile gates/test/test-serial and equivalent complete-suite commands as heavyweight without blocking bounded read-only/focused audit checks. Exact integration/review gates should own the authoritative lane; auditor heavyweight work waits with durable informational state and resumes fairly, or reuses exact compatible gate evidence when policy permits. Preserve command timeouts, cancellation, output delivery, audit independence, multi-project fairness, and never terminate an unrelated running gate. Expose current owner, waiter count/age, and capacity disposition without actionable warnings for normal waits. Required tests: auditor full suite concurrent with exact gate; two projects; restart with held/waiting lease; owner crash/expiry; cancellation; focused commands continue; exact compatible evidence reuse; fairness/no starvation; and proof no concurrent heavyweight pytest trees launch. Acceptance: the service never oversubscribes configured heavyweight validation capacity, exact gates cannot fail because a completion auditor launched a competing full suite, and normal capacity waits clear automatically.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-05 00:39
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-05 00:39
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-05 00:40
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 46.4K in / 297 out [46.7K total]
- Cost: $0.0000
- Exit: normal, Duration: 49s
- Log: OOMPAH-816__20260805T004004Z.jsonl
---
author: oompah
created: 2026-08-05 00:43
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-05 00:43
---
Focus: Oompah Tests Auth Specialist
---
author: oompah
created: 2026-08-05 00:49
---
**Understanding**: The issue requires implementing a process-safe, restart-safe resource lease mechanism to serialize heavyweight validation commands (like 'make test', 'make test-serial') between BranchQualityGate and auditor MCP run_command execution.

**Problem**: When both run concurrently, host CPU/disk resources become exhausted, causing I/O blocking (jbd2_log_wait_commit) and fixture timeouts.

**Solution approach**: 
1. Create a resource lease manager (ValidationResourceLease) with process-safe locking and durable state persistence
2. Classify full Makefile gates/test commands as heavyweight, allow focused/bounded checks to bypass
3. Integrate with api_agent._exec_run_command() and quality_gate.py subprocess execution
4. Implement fair queueing: exact gates get priority, auditor work waits with informational status
5. Add status exposure (current owner, waiter count/age, capacity) without actionable warnings
6. Tests: concurrent auditor+gate, restart scenarios, cancellation, evidence reuse, no starvation

**Files to modify**: Create `oompah/validation_resource_lease.py`, modify `oompah/api_agent.py` (run_command path), `oompah/quality_gate.py` (gate execution), add `tests/test_validation_resource_lease.py`
---
author: oompah
created: 2026-08-05 00:54
---
Acceptance blocker in the initial lease draft: fcntl is imported but the lock file is never opened/locked, so separate processes can both acquire and race/lost-update JSON; restart reloads a durable owner forever with no PID/start-time/heartbeat/expiry/fencing token and never prunes recovered waiters; configured capacity is ignored; strict priority can starve auditors; and sorting with self._waiters.index(x) inside list.sort can raise because the list appears empty during key evaluation. Redesign before integration. Carry exact owner scope: auditor run_command gets audit attempt/audit/project/task from _exec_tool, while BranchQualityGate already has QualityGateOwner. Gate acquire belongs after cache/authority checks but before Popen; lease wait must not consume command timeout and must observe cancellation. Release in the same process-cleanup finally; cancellation removes only its own waiter/lease and never broadly terminates another gate. Add real multiprocess mutual exclusion/lost-update, crash/expiry/fencing, restart/pruning, capacity, fairness, cancellation, and exact-owner regressions.
---
author: oompah
created: 2026-08-05 00:55
---
Further acceptance constraints: heavyweight classification must be fail-closed per every shell segment; a lightweight token anywhere cannot bypass 'echo x; make test' or 'make test && git status'. Cover uv run pytest, python -m pytest, options, tests paths, node IDs, and compound commands. BranchQualityGate must acquire unconditionally for its configured exact command after exact cache lookup, not use arbitrary-agent classification. Wire OOMPAH_HEAVYWEIGHT_CAPACITY through ServiceConfig and .env.example with validated parsing; no module-global os.environ initialization or Path.home state. Use service-owned configured state root with safe permissions, schema/version, fsync/atomic replace, corruption quarantine, and actual interprocess lock. Tool liveness/command timeout begins only after lease acquisition; queued auditors observe cancellation/session liveness separately. Compatible evidence reuse must key repo identity + exact SHA + exact command/gate version and never reuse failed/interrupted evidence.
---
author: oompah
created: 2026-08-05 00:57
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 0, Tool calls: 37
- Tokens: 654 in / 177 out [831 total]
- Cost: $0.0000
- Exit: terminated, Duration: 14m 31s
- Log: OOMPAH-816__20260805T004341Z.jsonl
---
author: oompah
created: 2026-08-05 01:14
---
Additional live acceptance evidence: during OOMPAH-814's exact gate, OOMPAH-505 launched python -m pytest -q over five broad subsystem files (acp_backends, providers, providers_ui, acp_agent, orchestrator_handlers). It owned 11 managed processes and hundreds of SQLite/WAL handles; dm-0 reached 98-99% utilization and both that command plus all four gate workers blocked in jbd2_log_wait_commit. Heavyweight classification cannot rely only on make test/test-serial or a claim that any explicit file list is focused. Treat substantial multi-file pytest commands as heavyweight; permit only genuinely bounded node/small-file checks to bypass, with regressions for this exact five-file shape.
---
author: oompah
created: 2026-08-05 06:11
---
Rebased the accepted validation-resource lease onto reconciled systemic parent ceafd8e14. New exact clean pushed head is 990a9856db25cff6cd3b8165b5e55b18444aff39. In the branch-isolated environment, the focused lease/quality-gate/native-wrapper/Codex/config/liveness/API matrix passes 482/482; the earlier four wrapper import failures were reproduced as a shared-main-venv artifact and pass in the correct branch environment. Holding final submission until OOMPAH-814 lands; its tests-only delta is conflict-free and will be the last base refresh before this resource-arbitration task gates.
---
author: oompah
created: 2026-08-05 06:32
---
Independent exact-head review rejected 990a9856 as unsafe. Blocking defects: evidence key-lock/validation-lease inversion deadlocks a queued gate against a successful auditor callback; queued waits have no stall-protection liveness; cancellation is ignored after acquisition and native sessions can escape backend termination; multiline/opaque/native bypasses remain fail-open; transient release persistence can leak a fence and wedge capacity; native runtime deadline starts at guard installation rather than post-acquire; launcher imports through untrusted ambient PYTHONPATH; and descendant-held flock state can falsely report free capacity. I am repairing these on the claimed branch with deterministic regressions before any submission.
---
<!-- COMMENTS:END -->
