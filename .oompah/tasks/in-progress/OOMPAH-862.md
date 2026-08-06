---
id: OOMPAH-862
type: task
status: In Progress
priority: null
title: Prevent terminal auditors from redundantly rerunning authoritative full gates
parent: OOMPAH-763
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-06T14:20:47.304513Z'
updated_at: '2026-08-06T14:40:48.229024Z'
work_branch: epic-OOMPAH-763--task-OOMPAH-862
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: ea3892ed7b4cfc880dc90345a4c9b957196bea269515ae7e63fb268c0e15c60f
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-06T14:25:18.865551+00:00'
  matched_identifiers: []
  evidence: Owner reviewed the live project corpus and found no existing task that
    prevents Completion Auditors from rerunning a current authoritative exact full
    gate. Related OOMPAH-847 through OOMPAH-861 tasks address test isolation, resource
    fencing, dependency flow, and branch authority, not redundant terminal-audit gate
    reuse.
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: '2026-08-06T14:25:18.865551+00:00'
  owner_login: oompah-cli
  owner_resolution_reason: Owner reviewed the live project corpus and found no existing
    task that prevents Completion Auditors from rerunning a current authoritative
    exact full gate. Related OOMPAH-847 through OOMPAH-861 tasks address test isolation,
    resource fencing, dependency flow, and branch authority, not redundant terminal-audit
    gate reuse.
oompah.agent_run_id: 8517ca93-c711-4906-9cf4-de73c5fba4dd
oompah.work_branch: epic-OOMPAH-763--task-OOMPAH-862
oompah.integration:
  version: 2
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-763--task-OOMPAH-862
  base_branch: epic-OOMPAH-763
  base_sha: d5edb84f121e08b04d3bd4a7d1e937f3233d5b4c
  updated_at: '2026-08-06T14:26:53.282139+00:00'
oompah.task_costs:
  total_input_tokens: 10
  total_output_tokens: 2503
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 10
      output_tokens: 2503
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 2503
    cost_usd: 0.0
    recorded_at: '2026-08-06T14:22:37.992370+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-862__20260806T142200Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: epic-OOMPAH-763--task-OOMPAH-862
    source_sha: d5edb84f121e08b04d3bd4a7d1e937f3233d5b4c
    completed_at: '2026-08-06T14:22:38.017861+00:00'
---
## Summary

Live OOMPAH-860 regression on 2026-08-06: the exact accepted head completed the configured 16k-test make test gate successfully, and the terminal auditor then launched make test-serial across the entire suite before rendering its independent verdict. This serializes the only validation lane for a long second full run and delays unrelated accepted repairs without adding missing exact-head evidence. Implementation scope: include authoritative exact-head quality-gate command, result, head SHA, duration, and relevant focused evidence in the terminal-audit prompt/evidence bundle; tell auditors to verify the patch and run only narrowly targeted missing checks when the exact configured gate is already current and passing; keep auditors free to request or run a full gate when evidence is missing, stale, failed, mismatched, or the task specifically requires a distinct execution mode. Add observability distinguishing reused authoritative gate evidence, focused supplemental commands, and auditor-initiated full-suite runs. Relevant code: auditor prompt construction and dispatch in oompah/orchestrator.py and oompah/auditor_dispatch.py, quality-gate evidence lookup, terminal audit telemetry, and Completion Auditor focus instructions. Required tests: a current passing exact gate is embedded and suppresses redundant make test or make test-serial guidance; stale/different-head/failed evidence does not suppress a needed gate; focused warning or race checks remain allowed; telemetry records the decision; restart retains the evidence decision. Acceptance criteria: the OOMPAH-860 sequence reaches an independent terminal verdict without a second full-suite run when the exact accepted head already has a passing configured gate, while fail-closed audit behavior remains intact.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-06 14:21
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-06 14:21
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-06 14:22
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 2.5K out [2.5K total]
- Cost: $0.0000
- Exit: normal, Duration: 54s
- Log: OOMPAH-862__20260806T142200Z.jsonl
---
author: oompah
created: 2026-08-06 14:22
---
Duplicate screening stopped with an actionable corpus diagnostic: Required structural peers could not fit the bounded duplicate corpus. Omitted peer identifiers: OOMPAH-847, OOMPAH-848, OOMPAH-850, OOMPAH-851, OOMPAH-852, OOMPAH-853, OOMPAH-854, OOMPAH-855, OOMPAH-856, OOMPAH-858, OOMPAH-860, OOMPAH-861. Increase the duplicate corpus task/byte budget or have a project owner review the authoritative tracker corpus, then use the authenticated duplicate-screening owner-resolution action with a conclusive verdict.
---
author: oompah
created: 2026-08-06 14:26
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-06 14:27
---
Focus: Oompah Tests Auth Specialist
---
author: oompah
created: 2026-08-06 14:27
---
Understanding: terminal auditors should reuse a current passing authoritative exact-head gate, while retaining fail-closed behavior for missing, stale, failed, or mismatched evidence. I’ll trace gate evidence/prompt/telemetry flow, implement the decision and observability, and add focused regression tests.
---
author: oompah
created: 2026-08-06 14:29
---
Discovery: BranchQualityGate persists exact-key gate outcomes in quality_gates.json, and auditors currently only contribute compatible passes through record_auditor_quality_evidence after a successful heavyweight command. The prompt builder receives only pending-target/archive data, so it cannot tell a current authoritative full gate from a missing one; telemetry also lacks the reuse/supplemental/full-run decision. I’ll add a read-only exact evidence lookup, dispatch-time evidence bundle/guidance, duration propagation, and durable decision telemetry with restart restoration.
---
author: oompah
created: 2026-08-06 14:36
---
Operator coordination: OOMPAH-860 currently owns the validation lease for its terminal audit. Your focused pytest attempts failed before collection on the known read-only external-lock bootstrap defect and did not contend with the audit. Preserve implementation and tests, continue static checks only, and defer further validation until the operator releases the lane.
---
author: oompah
created: 2026-08-06 14:40
---
Coordination correction: the managed worker explicitly removed OOMPAH_NATIVE_VALIDATION_GUARD and launched focused pytest from the shared root environment while OOMPAH-860 owned the only validation slot. That unleased pytest has now exited; do not launch any more test or gate commands until the validation lease is free. Preserve current edits and restrict further work to static inspection.
---
<!-- COMMENTS:END -->
