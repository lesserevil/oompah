---
id: OOMPAH-951
type: task
status: Merged
priority: 0
title: Align ACP auditor result tool schema with its advertised contract
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-09T10:46:27.644873Z'
updated_at: '2026-08-09T16:32:47.640409Z'
work_branch: OOMPAH-951
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/759
review_number: '759'
review_head: 5defaaa424e9a1303ee292ad523369e53e1b08e1
merged_at: null
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: standalone
  task_branch: OOMPAH-951
  head_sha: 5defaaa424e9a1303ee292ad523369e53e1b08e1
  submitted_at: '2026-08-09T10:52:11.207142+00:00'
  updated_at: '2026-08-09T10:52:11.207142+00:00'
oompah.work_branch: OOMPAH-951
oompah.review_url: https://github.com/lesserevil/oompah/pull/759
oompah.review_number: '759'
oompah.target_branch: main
oompah.review_head: 5defaaa424e9a1303ee292ad523369e53e1b08e1
oompah.terminal_audit:
  queued_comment_posted: true
  oompah.terminal_audit_tracker_projections:
  - version: 1
    audit_id: audit-9389c2e1c479
    project_id: proj-14849f1b
    task_id: OOMPAH-951
    digest: b517d9c92a02d37b7df7aa7fc3a1d6fc4b2fd5e54f8493da3d34a63b9c0db2f4
  - version: 1
    audit_id: audit-a6c6f33031c8
    project_id: proj-14849f1b
    task_id: OOMPAH-951
    digest: b517d9c92a02d37b7df7aa7fc3a1d6fc4b2fd5e54f8493da3d34a63b9c0db2f4
  applied_result_attempts:
    '["proj-14849f1b","OOMPAH-951","audit-9389c2e1c479","attempt-0c04e1f707a5"]': '2026-08-09T13:02:56.343300+00:00'
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-951
    target_state: Done
    evidence_fingerprint: b517d9c92a02d37b7df7aa7fc3a1d6fc4b2fd5e54f8493da3d34a63b9c0db2f4
    audit_ids:
    - audit-9389c2e1c479
    kind: result
    applied: true
    retired_at: '2026-08-09T13:02:56.343328+00:00'
  oompah.terminal_audit_result_intents:
  - project_id: proj-14849f1b
    task_id: OOMPAH-951
    audit_id: audit-9389c2e1c479
    attempt_id: attempt-0c04e1f707a5
    target_state: Done
    evidence_fingerprint: b517d9c92a02d37b7df7aa7fc3a1d6fc4b2fd5e54f8493da3d34a63b9c0db2f4
    status: In Validation
    audit_ids:
    - audit-9389c2e1c479
    kind: result
    applied: true
    created_at: '2026-08-09T13:02:56.343346+00:00'
    applied_at: '2026-08-09T13:03:05.953144+00:00'
  oompah.terminal_override_records:
  - version: 1
    override_id: override-fb3d96855fde
    project_id: proj-14849f1b
    task_id: OOMPAH-951
    target_state: Merged
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: b517d9c92a02d37b7df7aa7fc3a1d6fc4b2fd5e54f8493da3d34a63b9c0db2f4
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: 'Project-owner override after exact task head 5defaaa424e9a1303ee292ad523369e53e1b08e1
      was proven to be PR #759 head and contained in main; PR #759 merged as 54dafeef05f236821f6ef676c97fe882ffb42385
      with hosted Python 3.11/3.12/3.13 checks successful; the independent terminal
      auditor also recorded PASS.'
    created_at: '2026-08-09T16:32:43.694774+00:00'
    selected_ref: 5defaaa424e9a1303ee292ad523369e53e1b08e1
    selected_sha: 5defaaa424e9a1303ee292ad523369e53e1b08e1
    applied: false
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-9389c2e1c479
    project_id: proj-14849f1b
    task_id: OOMPAH-951
    target_state: Done
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: b517d9c92a02d37b7df7aa7fc3a1d6fc4b2fd5e54f8493da3d34a63b9c0db2f4
    attempts:
    - version: 1
      attempt_id: attempt-0c04e1f707a5
      target_state: Done
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: b517d9c92a02d37b7df7aa7fc3a1d6fc4b2fd5e54f8493da3d34a63b9c0db2f4
      created_at: '2026-08-09T12:58:05.672669+00:00'
      provider_id: prov-651d553c
      model: haiku
      started_at: '2026-08-09T12:58:05.672669+00:00'
      branch_key: OOMPAH-951
      selected_ref: 5defaaa424e9a1303ee292ad523369e53e1b08e1
      selected_sha: 5defaaa424e9a1303ee292ad523369e53e1b08e1
      verdict: pass
      completed_at: '2026-08-09T13:02:56.342985+00:00'
      ended_at: '2026-08-09T13:02:56.342985+00:00'
    source_generation: 1
    requested_by:
      version: 1
      identity: lesserevil
      source: forge
    previous_state: Ready to Integrate
    created_at: '2026-08-09T12:15:34.848664+00:00'
    selected_ref: 5defaaa424e9a1303ee292ad523369e53e1b08e1
    selected_sha: 5defaaa424e9a1303ee292ad523369e53e1b08e1
    updated_at: '2026-08-09T13:02:56.342985+00:00'
  - version: 1
    audit_id: audit-a6c6f33031c8
    project_id: proj-14849f1b
    task_id: OOMPAH-951
    target_state: Merged
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: b517d9c92a02d37b7df7aa7fc3a1d6fc4b2fd5e54f8493da3d34a63b9c0db2f4
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: lesserevil
      source: forge
    previous_state: Ready to Integrate
    created_at: '2026-08-09T12:15:34.848664+00:00'
    selected_ref: 5defaaa424e9a1303ee292ad523369e53e1b08e1
    selected_sha: 5defaaa424e9a1303ee292ad523369e53e1b08e1
  attempt_history:
  - version: 1
    attempt_id: attempt-0c04e1f707a5
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: b517d9c92a02d37b7df7aa7fc3a1d6fc4b2fd5e54f8493da3d34a63b9c0db2f4
    created_at: '2026-08-09T12:58:05.672669+00:00'
    provider_id: prov-651d553c
    model: haiku
    started_at: '2026-08-09T12:58:05.672669+00:00'
    branch_key: OOMPAH-951
    selected_ref: 5defaaa424e9a1303ee292ad523369e53e1b08e1
    selected_sha: 5defaaa424e9a1303ee292ad523369e53e1b08e1
oompah.task_costs:
  total_input_tokens: 338
  total_output_tokens: 10278
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 338
      output_tokens: 10278
      cost_usd: 0.0
  runs:
  - profile: auditor
    model: unknown
    input_tokens: 338
    output_tokens: 10278
    cost_usd: 0.0
    recorded_at: '2026-08-09T13:03:17.834682+00:00'
---
## Summary

Triggered by OOMPAH-939 live terminal audit attempt audit-4827a2c0df9f. The ACP/MCP auditor catalog advertises the canonical top-level AUDITOR_RESULT_TOOL_SCHEMA (audit_id, target_state, evidence_fingerprint, verdict, message), but both MCP @tool builders in oompah/acp_tools.py register {result: dict}. Claude correctly called the advertised top-level contract repeatedly and the transport rejected every call with Input validation error: 'result' is a required property, leaving OOMPAH-939 In Validation after a 26-minute full gate. Scope: make every auditor transport expose the same canonical top-level input schema and continue accepting only server-validated target-bound fields; remove obsolete envelope ambiguity; add provider-shaped MCP catalog/schema and end-to-end submission tests for both project-aware builders plus regression coverage proving a top-level result reaches the coordinator exactly once. Work around audit-4827a2c0df9f after deployment or through the exact authenticated audit authority without weakening its verdict/gate requirements. Acceptance: advertised and enforced schemas are identical across auditor transports, a valid top-level submission is accepted, envelope/schema drift fails tests, and OOMPAH-939 resumes naturally.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-09 10:52
---
Implemented and pushed exact head 5defaaa42. Claude/OpenCode MCP tools now register the canonical top-level AUDITOR_RESULT_TOOL_SCHEMA, Codex uses the same explicit FunctionTool schema, and the obsolete nested result envelope is rejected. Provider-shaped tests prove schema equality and exactly one accepted coordinator submission. Verification: 191 auditor contract/API/bridge/deadline/output tests passed; terminal mutation, secret, diff, and fatal/static scans passed.
---
author: oompah
created: 2026-08-09 10:52
---
Aligned ACP auditor result contract at 5defaaa42
---
author: oompah
created: 2026-08-09 11:51
---
Branch quality gate passed for `5defaaa424e9a1303ee292ad523369e53e1b08e1` using `make test` in 161.1s. Review creation may proceed.
---
author: oompah
created: 2026-08-09 12:15
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-09 12:58
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/haiku)
---
author: oompah
created: 2026-08-09 12:58
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-09 13:03
---
Audit PASS — Done

OOMPAH-951 implementation complete. Canonical top-level AUDITOR_RESULT_TOOL_SCHEMA now exposed identically across Claude, OpenCode, and Codex ACP backends. Obsolete MCP envelope fallback removed and rejected by tests. Schema equality, top-level submission acceptance, and exact-once coordinator submission verified. All 191+ tests passed including new provider-shaped coverage in test_auditor_contract.py.

Safe evidence:
- implementation_commit: 5defaaa424e9a1303ee292ad523369e53e1b08e1
- commit_message: Align auditor result schemas across transports
- canonical_schema_location: oompah/auditor.py line 921
- required_fields: audit_id, target_state, evidence_fingerprint, verdict, message
- optional_fields: failure_classification, safe_evidence, questions, instructions, attempt_id
- obsolete_envelope: result field - REMOVED and rejected by tests
- claude_transport: Uses _auditor_result_input_schema() with @tool decorator
- opencode_transport: Uses _auditor_result_input_schema() with @tool decorator
- codex_transport: Uses _auditor_result_input_schema() with @function_tool and FunctionTool
- test_method: test_all_auditor_catalogs_expose_canonical_top_level_result_contract
- test_coverage: Schema equality verification, envelope rejection, exact-once submission
- quality_gate_status: passed
- quality_gate_command: make test
- quality_gate_duration: 161.13 seconds
- files_modified: oompah/acp_tools.py, tests/test_auditor_contract.py, test_acp_auditor_result_bridge.py, test_acp_tool_output_bounds.py
---
author: oompah
created: 2026-08-09 13:03
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/haiku]
- Turns: 89, Tool calls: 41
- Tokens: 338 in / 10.3K out [10.6K total]
- Cost: $0.0000
- Exit: normal, Duration: 5m 9s
- Log: OOMPAH-951__20260809T125816Z.jsonl
---
<!-- COMMENTS:END -->
