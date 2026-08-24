---
id: OOMPAH-1333
type: task
status: Merged
priority: null
title: OpenCode auditor cannot call submit_audit_result (oompah tools not injected
  into opencode run), so verdicts never finalize
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-24T21:06:31.866816Z'
updated_at: '2026-08-24T22:11:03.908750Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.create_once:
  version: 1
  project_id: proj-14849f1b
  operation_kind: api_task_create
  creation_marker: aa0aa824-890f-4f81-8ef4-0c789e2d39af
  request_fingerprint: 20e48022221d5b75041780a786cbfbd171aefb30c6edf0543eb5b5506a5fdd9d
oompah.terminal_audit:
  queued_comment_posted: true
  oompah.terminal_audit_tracker_projections:
  - version: 1
    audit_id: audit-c1f37653fa90
    project_id: proj-14849f1b
    task_id: OOMPAH-1333
    digest: 474cb59977283fd5b430a2c4f489b6f2dc26fb5d8ac6f0f8466d59391202fdf8
  - version: 1
    audit_id: audit-614c1a9275da
    project_id: proj-14849f1b
    task_id: OOMPAH-1333
    digest: 474cb59977283fd5b430a2c4f489b6f2dc26fb5d8ac6f0f8466d59391202fdf8
  applied_result_attempts:
    '["proj-14849f1b","OOMPAH-1333","audit-c1f37653fa90","attempt-375614fa1c9e"]': '2026-08-24T22:04:30.145440+00:00'
    '["proj-14849f1b","OOMPAH-1333","audit-614c1a9275da","attempt-0de4f27287ac"]': '2026-08-24T22:10:53.520957+00:00'
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-1333
    target_state: Done
    evidence_fingerprint: 474cb59977283fd5b430a2c4f489b6f2dc26fb5d8ac6f0f8466d59391202fdf8
    workflow_revision: null
    selected_ref: origin/OOMPAH-1333
    selected_sha: f988367829192e6c7658af1d97a3da849ca96fab
    landing_revision: null
    audit_ids:
    - audit-c1f37653fa90
    kind: result
    applied: true
    retired_at: '2026-08-24T22:04:30.145456+00:00'
  - project_id: proj-14849f1b
    task_id: OOMPAH-1333
    target_state: Merged
    evidence_fingerprint: 474cb59977283fd5b430a2c4f489b6f2dc26fb5d8ac6f0f8466d59391202fdf8
    workflow_revision: null
    selected_ref: origin/OOMPAH-1333
    selected_sha: f988367829192e6c7658af1d97a3da849ca96fab
    landing_revision: null
    audit_ids:
    - audit-614c1a9275da
    kind: result
    applied: true
    retired_at: '2026-08-24T22:10:53.520978+00:00'
  oompah.terminal_audit_result_intents:
  - project_id: proj-14849f1b
    task_id: OOMPAH-1333
    audit_id: audit-c1f37653fa90
    attempt_id: attempt-375614fa1c9e
    target_state: Done
    evidence_fingerprint: 474cb59977283fd5b430a2c4f489b6f2dc26fb5d8ac6f0f8466d59391202fdf8
    status: In Validation
    audit_ids:
    - audit-c1f37653fa90
    kind: result
    applied: true
    created_at: '2026-08-24T22:04:30.145467+00:00'
    applied_at: '2026-08-24T22:04:37.631512+00:00'
  - project_id: proj-14849f1b
    task_id: OOMPAH-1333
    audit_id: audit-614c1a9275da
    attempt_id: attempt-0de4f27287ac
    target_state: Merged
    evidence_fingerprint: 474cb59977283fd5b430a2c4f489b6f2dc26fb5d8ac6f0f8466d59391202fdf8
    status: Merged
    audit_ids:
    - audit-614c1a9275da
    kind: result
    applied: true
    created_at: '2026-08-24T22:10:53.520993+00:00'
    applied_at: '2026-08-24T22:11:02.107654+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-c1f37653fa90
    project_id: proj-14849f1b
    task_id: OOMPAH-1333
    target_state: Done
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 474cb59977283fd5b430a2c4f489b6f2dc26fb5d8ac6f0f8466d59391202fdf8
    attempts:
    - version: 1
      attempt_id: attempt-375614fa1c9e
      target_state: Done
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 474cb59977283fd5b430a2c4f489b6f2dc26fb5d8ac6f0f8466d59391202fdf8
      created_at: '2026-08-24T21:53:38.049534+00:00'
      provider_id: prov-651d553c
      model: haiku
      started_at: '2026-08-24T21:53:38.049534+00:00'
      branch_key: OOMPAH-1333
      selected_ref: origin/OOMPAH-1333
      selected_sha: f988367829192e6c7658af1d97a3da849ca96fab
      verdict: pass
      completed_at: '2026-08-24T22:04:30.145281+00:00'
      ended_at: '2026-08-24T22:04:30.145281+00:00'
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: Backlog
    created_at: '2026-08-24T21:34:47.082570+00:00'
    eligible_at: '2026-08-24T21:34:47.082570+00:00'
    selected_ref: origin/OOMPAH-1333
    selected_sha: f988367829192e6c7658af1d97a3da849ca96fab
    updated_at: '2026-08-24T22:04:30.145281+00:00'
  - version: 1
    audit_id: audit-614c1a9275da
    project_id: proj-14849f1b
    task_id: OOMPAH-1333
    target_state: Merged
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 474cb59977283fd5b430a2c4f489b6f2dc26fb5d8ac6f0f8466d59391202fdf8
    attempts:
    - version: 1
      attempt_id: attempt-0de4f27287ac
      target_state: Merged
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 474cb59977283fd5b430a2c4f489b6f2dc26fb5d8ac6f0f8466d59391202fdf8
      created_at: '2026-08-24T22:05:00.043086+00:00'
      provider_id: prov-651d553c
      model: haiku
      started_at: '2026-08-24T22:05:00.043086+00:00'
      branch_key: OOMPAH-1333
      selected_ref: origin/OOMPAH-1333
      selected_sha: f988367829192e6c7658af1d97a3da849ca96fab
      verdict: pass
      completed_at: '2026-08-24T22:10:53.520771+00:00'
      ended_at: '2026-08-24T22:10:53.520771+00:00'
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: Backlog
    created_at: '2026-08-24T21:34:47.082570+00:00'
    prerequisite_audit_id: audit-c1f37653fa90
    selected_ref: origin/OOMPAH-1333
    selected_sha: f988367829192e6c7658af1d97a3da849ca96fab
    updated_at: '2026-08-24T22:10:53.520771+00:00'
    eligible_at: '2026-08-24T22:04:30.145281+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-375614fa1c9e
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 474cb59977283fd5b430a2c4f489b6f2dc26fb5d8ac6f0f8466d59391202fdf8
    created_at: '2026-08-24T21:53:38.049534+00:00'
    provider_id: prov-651d553c
    model: haiku
    started_at: '2026-08-24T21:53:38.049534+00:00'
    branch_key: OOMPAH-1333
    selected_ref: origin/OOMPAH-1333
    selected_sha: f988367829192e6c7658af1d97a3da849ca96fab
  - version: 1
    attempt_id: attempt-0de4f27287ac
    target_state: Merged
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 474cb59977283fd5b430a2c4f489b6f2dc26fb5d8ac6f0f8466d59391202fdf8
    created_at: '2026-08-24T22:05:00.043086+00:00'
    provider_id: prov-651d553c
    model: haiku
    started_at: '2026-08-24T22:05:00.043086+00:00'
    branch_key: OOMPAH-1333
    selected_ref: origin/OOMPAH-1333
    selected_sha: f988367829192e6c7658af1d97a3da849ca96fab
oompah.lifecycle_revision: 2
oompah.task_costs:
  total_input_tokens: 282
  total_output_tokens: 8514
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 282
      output_tokens: 8514
      cost_usd: 0.0
  runs:
  - profile: auditor
    model: unknown
    input_tokens: 282
    output_tokens: 8514
    cost_usd: 0.0
    recorded_at: '2026-08-24T22:04:51.428637+00:00'
---
## Summary

### Problem
After OOMPAH-1332 fixed the policy-denial loop (opencode 'run --auto' now auto-approves the auditor's read-only inspection, and native denials escalate through policy_denial_handler), OpenCode-provider completion audits still never finalize a verdict. The auditor now runs its inspection successfully (dozens of bash/read tool calls, no denials, transport_failure_count=0, policy_incompatibility_count=0) but then 'exits (normal) without a result', is classified as a finalization_failure, and retries indefinitely — keeping workflow_liveness in restart_overdue and fencing all non-terminal work (64 Ready to Integrate, etc.).

### Root cause
The OpenCode ACP backend builds the oompah tool catalog (including the result tool 'submit_audit_result' plus read_file/list_files/search_files/read_command_output/run_command) but NEVER injects those tools into the 'opencode run' subprocess. In oompah/acp_backends/opencode.py the catalog is only emitted as an observability label ('tool_policy': 'opencode:tool_catalog', 'tool_catalog': tool_names) and the actual command is:
    opencode run --format json --auto [--model M] <prompt>
So the opencode agent only has opencode's OWN native tools; the oompah tools are not callable. The auditor therefore cannot invoke submit_audit_result and instead hallucinates a nonexistent submission path.

### Live evidence (build 0682f1e8e)
Agent log OOMPAH-1201__20260824T205215Z.jsonl:
- session_start tool_catalog lists ['read_file','list_files','search_files','read_command_output','run_command','submit_audit_result'] but these are labels only.
- The auditor emits a native 'task' tool call trying to 'Submit auditor verdict', then acp_text: 'I can't submit the auditor verdict: in this environment there's no submit_audit_result/completion-auditor submission command available (the tool call failed with "No oompah completion-auditor CLI command exists").'
- Task comments: 'Auditor attempt ended: auditor exited (normal) without a result. A different independent auditor will be tried on the next scheduler tick.' (repeats)
- terminal_audit_health: degraded=true, finalization_failure_count>0, transport_failure_count=0, policy_incompatibility_count=0.

Contrast: Claude bridges oompah tools via an in-process MCP server (create_sdk_mcp_server, mcp__oompah__*), and Codex via its bridged catalog / native read-only sandbox; both can call the result tool. OpenCode's one-shot 'run' has no equivalent tool injection.

### Investigation scope
- Determine how to expose oompah's tool callables (especially submit_audit_result and the read-only inspection tools) to the opencode agent. Options to evaluate:
  (a) Run an oompah MCP server and use 'opencode run --attach <server>' / opencode MCP config so mcp__oompah__* tools (incl. submit_audit_result) are callable, mirroring the Claude bridge.
  (b) Provide an oompah CLI/command the opencode agent can invoke to submit the verdict (e.g. a real 'oompah completion-auditor submit ...' path bound to audit_result_handler), since the agent already tried a CLI.
  (c) If neither is feasible, make the OpenCode backend ineligible for the auditor role (auditor candidate selector skips backend=opencode) and fail closed with an actionable configuration error instead of infinite finalization_failure retries.
- Ensure a bounded outcome: an auditor that cannot emit a verdict must escalate (policy/config incompatibility, action_required) rather than loop as transient finalization_failure forever.

### Tests
- OpenCode auditor session can call submit_audit_result (or the chosen submission path) and the verdict is accepted/finalized.
- If OpenCode is made ineligible for auditor, candidate selection excludes it and a clear configuration alert is raised; no infinite retry.
- Regression: 'exited normal without a result' does not loop unbounded; after N such attempts the audit escalates action_required.

### Acceptance Criteria
- OpenCode-provider completion audits either finalize a real verdict (submit_audit_result callable) or the backend is cleanly excluded from the auditor role with an actionable alert.
- terminal_audit_health.finalization_failure_count stops climbing; audits no longer loop 'without a result'.
- With verdicts finalizing (or an independent non-OpenCode auditor selected), restart reconstruction converges (scan_complete=true) and fenced non-terminal work is admitted.
- No regression for Claude/Codex auditors.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-24 21:34
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-24 21:53
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/haiku)
---
author: oompah
created: 2026-08-24 21:53
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-24 22:04
---
Audit PASS — Done

OpenCode auditor issue resolved. Implementation cleanly excludes OpenCode from completion auditor candidates (fails closed, not infinite retry). Root cause addressed: OpenCode subprocess lacks submit_audit_result tool. Fallback logic verifies Claude/per-token Codex remain eligible. All 57 tests pass including 2 new OpenCode-specific tests. Acceptance criteria met: audits no longer loop on finalization_failure; capable auditors can finalize verdicts; no regressions.

Safe evidence:
- tests_passed: 57 of 57
- new_tests: test_opencode_is_skipped_for_claude_candidate, test_opencode_only_reports_missing_capability
- code_impact: auditor_candidate_selector.py + tests only
- root_cause_fix: Exclude OpenCode from auditor candidates, use existing missing_audit_capability diagnostic
---
author: oompah
created: 2026-08-24 22:04
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/haiku]
- Turns: 78, Tool calls: 34
- Tokens: 282 in / 8.5K out [8.8K total]
- Cost: $0.0000
- Exit: normal, Duration: 11m 10s
- Log: OOMPAH-1333__20260824T215405Z.jsonl
---
author: oompah
created: 2026-08-24 22:05
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/haiku)
---
author: oompah
created: 2026-08-24 22:05
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-24 22:11
---
Audit PASS — Merged

[REDACTED]

Safe evidence:
- tests_passed.auditor_candidate_selector: 57/57 (includes test_opencode_is_skipped_for_claude_candidate, test_opencode_only_reports_missing_capability)
- tests_passed.auditor_dispatch: 37/37
- tests_passed.terminal_audit_observability: 111/111
- tests_passed.done_merged_archived_lifecycle: 53/53
- tests_passed.epic_terminal_audit_contract: 20/21 (2 xfailed expected)
- code_changes.files_modified: oompah/auditor_candidate_selector.py, tests/test_auditor_candidate_selector.py
- code_changes.key_implementation: _supports_audit_verdict() returns False for backend=opencode, filtering from eligible candidates in _eligible_candidates()
- code_changes.diagnostic_used: missing_audit_capability (existing infrastructure)
- code_changes.line_changes: 13 lines in selector, 60 lines in tests
- acceptance_criteria_met.opencode_excluded: Yes - policy filter at selection time
- acceptance_criteria_met.root_cause_addressed: OpenCode catalog not injected into opencode run subprocess
- acceptance_criteria_met.claude_codex_eligible: Yes - remain eligible
- acceptance_criteria_met.no_infinite_retry: Yes - filtered before launch
- acceptance_criteria_met.clean_failure_mode: Actionable missing_audit_capability diagnostic
- commit_verification.sha: f988367829192e6c7658af1d97a3da849ca96fab
- commit_verification.message: OOMPAH-1333: require auditor verdict capability
- commit_verification.attribution: Proper oompah trailer
---
<!-- COMMENTS:END -->
