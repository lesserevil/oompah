---
id: OOMPAH-1332
type: task
status: In Validation
priority: null
title: Completion auditor tool-policy denies OpenCode auditor commands, so verdicts
  never finalize (endless candidate rotation)
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-24T18:33:39.522330Z'
updated_at: '2026-08-24T19:32:32.405827Z'
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
  creation_marker: f80c8a4d-456e-4dc5-88c6-a7725441f855
  request_fingerprint: c29c97a4dfda34f0e6b56c3ddf7f6f5f47382026e7f9f9e40565d8343a8c7b3e
oompah.terminal_audit:
  queued_comment_posted: true
  oompah.terminal_audit_tracker_projections:
  - version: 1
    audit_id: audit-c8f74b306247
    project_id: proj-14849f1b
    task_id: OOMPAH-1332
    digest: f31d714cbc165f0d4ac3c606c3cc2c21c211fc42eac14aa4c42b145d22ad9a4b
  - version: 1
    audit_id: audit-129d64b0ef60
    project_id: proj-14849f1b
    task_id: OOMPAH-1332
    digest: f31d714cbc165f0d4ac3c606c3cc2c21c211fc42eac14aa4c42b145d22ad9a4b
  applied_result_attempts:
    '["proj-14849f1b","OOMPAH-1332","audit-c8f74b306247","attempt-547ec9a85c56"]': '2026-08-24T19:30:51.752580+00:00'
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-1332
    target_state: Done
    evidence_fingerprint: f31d714cbc165f0d4ac3c606c3cc2c21c211fc42eac14aa4c42b145d22ad9a4b
    workflow_revision: null
    selected_ref: origin/OOMPAH-1332
    selected_sha: fc7a63a31c23e49d4fb5d51d5ea5880e5c90d58a
    landing_revision: null
    audit_ids:
    - audit-c8f74b306247
    kind: result
    applied: true
    retired_at: '2026-08-24T19:30:51.752597+00:00'
  oompah.terminal_audit_result_intents:
  - project_id: proj-14849f1b
    task_id: OOMPAH-1332
    audit_id: audit-c8f74b306247
    attempt_id: attempt-547ec9a85c56
    target_state: Done
    evidence_fingerprint: f31d714cbc165f0d4ac3c606c3cc2c21c211fc42eac14aa4c42b145d22ad9a4b
    status: In Validation
    audit_ids:
    - audit-c8f74b306247
    kind: result
    applied: true
    created_at: '2026-08-24T19:30:51.752608+00:00'
    applied_at: '2026-08-24T19:30:59.248960+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-c8f74b306247
    project_id: proj-14849f1b
    task_id: OOMPAH-1332
    target_state: Done
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: f31d714cbc165f0d4ac3c606c3cc2c21c211fc42eac14aa4c42b145d22ad9a4b
    attempts:
    - version: 1
      attempt_id: attempt-547ec9a85c56
      target_state: Done
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: f31d714cbc165f0d4ac3c606c3cc2c21c211fc42eac14aa4c42b145d22ad9a4b
      created_at: '2026-08-24T19:26:41.954806+00:00'
      provider_id: prov-651d553c
      model: haiku
      started_at: '2026-08-24T19:26:41.954806+00:00'
      branch_key: OOMPAH-1332
      selected_ref: origin/OOMPAH-1332
      selected_sha: fc7a63a31c23e49d4fb5d51d5ea5880e5c90d58a
      verdict: pass
      completed_at: '2026-08-24T19:30:51.752412+00:00'
      ended_at: '2026-08-24T19:30:51.752412+00:00'
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: Backlog
    created_at: '2026-08-24T19:04:36.599774+00:00'
    eligible_at: '2026-08-24T19:04:36.599774+00:00'
    selected_ref: origin/OOMPAH-1332
    selected_sha: fc7a63a31c23e49d4fb5d51d5ea5880e5c90d58a
    updated_at: '2026-08-24T19:30:51.752412+00:00'
  - version: 1
    audit_id: audit-129d64b0ef60
    project_id: proj-14849f1b
    task_id: OOMPAH-1332
    target_state: Merged
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: f31d714cbc165f0d4ac3c606c3cc2c21c211fc42eac14aa4c42b145d22ad9a4b
    attempts:
    - version: 1
      attempt_id: attempt-8fe2a2bd6e4e
      target_state: Merged
      request_state: in_progress
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: f31d714cbc165f0d4ac3c606c3cc2c21c211fc42eac14aa4c42b145d22ad9a4b
      created_at: '2026-08-24T19:32:29.778657+00:00'
      provider_id: prov-651d553c
      model: haiku
      started_at: '2026-08-24T19:32:29.778657+00:00'
      branch_key: OOMPAH-1332
      selected_ref: origin/OOMPAH-1332
      selected_sha: fc7a63a31c23e49d4fb5d51d5ea5880e5c90d58a
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: Backlog
    created_at: '2026-08-24T19:04:36.599774+00:00'
    prerequisite_audit_id: audit-c8f74b306247
    selected_ref: origin/OOMPAH-1332
    selected_sha: fc7a63a31c23e49d4fb5d51d5ea5880e5c90d58a
    updated_at: '2026-08-24T19:32:29.778657+00:00'
    eligible_at: '2026-08-24T19:30:51.752412+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-547ec9a85c56
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: f31d714cbc165f0d4ac3c606c3cc2c21c211fc42eac14aa4c42b145d22ad9a4b
    created_at: '2026-08-24T19:26:41.954806+00:00'
    provider_id: prov-651d553c
    model: haiku
    started_at: '2026-08-24T19:26:41.954806+00:00'
    branch_key: OOMPAH-1332
    selected_ref: origin/OOMPAH-1332
    selected_sha: fc7a63a31c23e49d4fb5d51d5ea5880e5c90d58a
  - version: 1
    attempt_id: attempt-8fe2a2bd6e4e
    target_state: Merged
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: f31d714cbc165f0d4ac3c606c3cc2c21c211fc42eac14aa4c42b145d22ad9a4b
    created_at: '2026-08-24T19:32:29.778657+00:00'
    provider_id: prov-651d553c
    model: haiku
    started_at: '2026-08-24T19:32:29.778657+00:00'
    branch_key: OOMPAH-1332
    selected_ref: origin/OOMPAH-1332
    selected_sha: fc7a63a31c23e49d4fb5d51d5ea5880e5c90d58a
oompah.lifecycle_revision: 1
oompah.task_costs:
  total_input_tokens: 114
  total_output_tokens: 7142
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 114
      output_tokens: 7142
      cost_usd: 0.0
  runs:
  - profile: auditor
    model: unknown
    input_tokens: 114
    output_tokens: 7142
    cost_usd: 0.0
    recorded_at: '2026-08-24T19:31:15.741770+00:00'
---
## Summary

### Problem
Completion audits dispatched to the OpenCode/Switchyard provider run tool calls but never reach a verdict. The audit log shows the auditor session is configured with tool_policy 'strict_allowlist:mcp__oompah__*' (only mcp__oompah__* tools allowed), while the OpenCode auditor issues ordinary read-only shell/git commands (e.g. 'git show -s', 'git status', 'git log --oneline -5', 'make help', 'uv run pytest ...'). Every such call is policy-denied, the attempt ends with 'Auditor attempt was stopped after repeated policy denials; a different independent candidate will be tried', and the audit rotates candidates forever.

### Live evidence (build 09b06bfab, main)
- terminal_audit_health: degraded=true, finalization_failure_count=1, in_progress_count=6, transport_failure_count=0, retry_exhausted_count=0, policy_incompatibility_count fluctuates.
- audits: dispatch_count and rotation_count climb continuously (e.g. 17->19, 7->9) while running audits stay at turn_count=0 and never produce completed verdicts.
- Running audits: OOMPAH-1201, OOMPAH-1206, OOMPAH-1213, OOMPAH-1217, OOMPAH-1224, OOMPAH-1266 (all provider 'Opencode/Switchyard'), last_event=acp_tool_use, turns=0.
- Agent log OOMPAH-1330__20260824T173652Z.jsonl contains: '"tool_policy": "strict_allowlist:mcp__oompah__*"' and denied plain 'command' tool calls (git show/status/log, make help, uv run pytest), then 'policy denied' / 'disallowed'.

### Impact
- Terminal audits never finalize on the OpenCode auditor path, so restart reconstruction never converges (workflow_liveness stays restart_overdue, scan_complete=false, restart reconstruction pending), and worker admission stays fenced ('workflow publication requires reconciliation before durable admission').
- All inactive non-terminal work (e.g. 64 Ready to Integrate, In Review, Open, In Progress) cannot be admitted/drained while these audits churn.
- Distinct from OOMPAH-1330 (transport crash on >64KiB lines, fixed) and OOMPAH-1331 (publication-deferred reconstruction finalization, fixed); transport_failure_count is now 0, so this is purely a tool-policy/verdict-finalization incompatibility.

### Investigation scope
- Determine why the auditor tool catalog/policy for the OpenCode backend is 'strict_allowlist:mcp__oompah__*' while the auditor still emits plain shell/git 'command' tool calls. Either (a) the OpenCode auditor should route its read-only inspection through the approved mcp__oompah__* tool surface (as Claude/Codex auditors do), or (b) the auditor allowlist for read-only completion auditing must permit the necessary read-only inspection commands (git show/status/log/diff, make help, test invocation) on the OpenCode backend.
- Compare how claude.py / codex.py auditor sessions expose read-only inspection vs opencode.py, and where build_tool_catalog / action_policy / read_only auditor wiring diverges for OpenCode.
- Ensure a completion auditor that cannot use any permitted tool fails fast with an actionable configuration error instead of rotating candidates indefinitely (bounded rotation / clear policy-incompatibility escalation).

### Tests
- An OpenCode auditor session on a read-only completion audit can execute its required inspection via permitted tools and reach a PASS/FAIL/NEEDS_HUMAN verdict.
- Regression: repeated policy denials do not loop forever; after N denials the audit records a policy-incompatibility escalation rather than infinite rotation.

### Acceptance Criteria
- OpenCode-provider completion audits finalize a verdict instead of stopping on repeated policy denials.
- terminal_audit_health.finalization_failure_count returns to 0 and audits stop endlessly rotating.
- With verdicts finalizing, restart reconstruction converges (scan_complete=true) and fenced non-terminal work is admitted.
- No regression for Claude/Codex auditor providers.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-24 19:04
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-24 19:26
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/haiku)
---
author: oompah
created: 2026-08-24 19:26
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-24 19:30
---
Audit PASS — Done

[REDACTED]

Safe evidence:
- commit_sha: fc7a63a31c23e49d4fb5d51d5ea5880e5c90d58a
- files_changed[0]: oompah/acp_backends/opencode.py
- files_changed[1]: tests/test_acp_opencode_backend.py
- test_coverage[0]: test_run_turn_uses_auto_permission_flag - verifies --auto in command
- test_coverage[1]: test_repeated_native_denials_escalate_policy_incompatibility - verifies escalation after 3 denials
- quality_gate.command: make test
- quality_gate.status: passed
- quality_gate.duration_seconds: 186.88
- acceptance_criteria[0]: OpenCode audits finalize verdicts - achieved via --auto flag
- acceptance_criteria[1]: No infinite rotation - bounded escalation at _MAX_NATIVE_DENIALS=3
- acceptance_criteria[2]: No regression for Claude/Codex - isolated to opencode.py only
- acceptance_criteria[3]: Proper safety net - policy_denial_handler escalation
---
author: oompah
created: 2026-08-24 19:31
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/haiku]
- Turns: 32, Tool calls: 13
- Tokens: 114 in / 7.1K out [7.3K total]
- Cost: $0.0000
- Exit: normal, Duration: 4m 30s
- Log: OOMPAH-1332__20260824T192713Z.jsonl
---
<!-- COMMENTS:END -->
