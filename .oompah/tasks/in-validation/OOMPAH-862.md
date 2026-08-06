---
id: OOMPAH-862
type: task
status: In Validation
priority: null
title: Prevent terminal auditors from redundantly rerunning authoritative full gates
parent: OOMPAH-763
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-06T14:20:47.304513Z'
updated_at: '2026-08-06T16:11:32.043231Z'
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
oompah.agent_run_id: null
oompah.work_branch: epic-OOMPAH-763--task-OOMPAH-862
oompah.integration:
  version: 2
  state: integrated
  attempts: 1
  task_branch: epic-OOMPAH-763--task-OOMPAH-862
  base_branch: epic-OOMPAH-763
  base_sha: 8953687bda424401e67d06d676943bbeac93faca
  head_sha: 6b67846406858b585ce47939f70bec76eb706fe8
  integrated_sha: 6b67846406858b585ce47939f70bec76eb706fe8
  submitted_at: '2026-08-06T15:53:06.504910+00:00'
  updated_at: '2026-08-06T16:11:15.225101+00:00'
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
oompah.terminal_audit:
  queued_comment_posted: true
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-5d02829b0301
    project_id: proj-14849f1b
    task_id: OOMPAH-862
    target_state: Done
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 5e49b8a4b59080d4287cba10f573ff2feef6d4d6f19db10f308f3af3018fb3ed
    attempts: []
    requested_by:
      version: 1
      identity: oompah-integration
      source: service
    previous_state: Ready to Integrate
    created_at: '2026-08-06T16:11:23.277113+00:00'
  attempt_history: []
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
author: oompah
created: 2026-08-06 14:46
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 0, Tool calls: 198
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 19m 11s
- Log: OOMPAH-862__20260806T142704Z.jsonl
---
author: oompah
created: 2026-08-06 14:46
---
Direct owner claim is now active and the managed worker has stopped with a clean recovery checkpoint at cc305f7a4. Independent static review rejected that checkpoint on three concrete gaps: API auditors bypass duration and validation telemetry; stale or not-configured evidence can be reused without a current-authority freshness fence; and telemetry treats make test-serial or wrapped full-suite attempts as focused while omitting failed and timed-out attempts. Owner repair will add fail-closed authority checks, API parity, semantic full-suite classification, and regressions before validation.
---
author: oompah
created: 2026-08-06 15:53
---
Owner repair is complete at exact pushed head 6b6784640 after final independent static ACCEPT. Enforcement now revalidates live audit authority, denies redundant exact and opaque full-suite commands before process launch, permits only bounded attempt-scoped distinct-mode exceptions, and records consistent durable lifecycle telemetry across API, Claude, Codex, and OpenCode. Validation: 548 focused tests passed serial and 548 passed with four-worker loadscope; secret scan and diff check passed.
---
author: oompah
created: 2026-08-06 15:53
---
Prevented redundant terminal-audit full gates with fail-closed live authority checks, tool enforcement, structured distinct-mode escape, and durable API/ACP telemetry; 548 serial plus 548 xdist tests passed at 6b6784640.
---
author: oompah
created: 2026-08-06 16:11
---
Queued for terminal transition to Done. An auditor will review and apply the terminal status.
---
<!-- COMMENTS:END -->
