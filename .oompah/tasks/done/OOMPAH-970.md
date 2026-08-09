---
id: OOMPAH-970
type: task
status: Done
priority: null
title: Make detached workflow heartbeat proof deterministic under loaded CI
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-09T19:37:32.521266Z'
updated_at: '2026-08-09T19:59:13.120915Z'
work_branch: OOMPAH-970
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: standalone
  task_branch: OOMPAH-970
  head_sha: 23a28b1f02319faff905d2733ef290c26d7cb097
  submitted_at: '2026-08-09T19:46:50.424122+00:00'
  updated_at: '2026-08-09T19:46:50.424122+00:00'
oompah.work_branch: OOMPAH-970
oompah.terminal_audit:
  queued_comment_posted: true
  oompah.terminal_audit_tracker_projections:
  - version: 1
    audit_id: audit-dbc0ee15412c
    project_id: proj-14849f1b
    task_id: OOMPAH-970
    digest: 8a4300fa26305215ba607ef34385de5d9b0e9805a4906d3b923535d44d04aa35
  - version: 1
    audit_id: audit-1cef3482ca27
    project_id: proj-14849f1b
    task_id: OOMPAH-970
    digest: 8a4300fa26305215ba607ef34385de5d9b0e9805a4906d3b923535d44d04aa35
  oompah.terminal_override_records:
  - version: 1
    override_id: override-51ad4e37e0db
    project_id: proj-14849f1b
    task_id: OOMPAH-970
    target_state: Done
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 8a4300fa26305215ba607ef34385de5d9b0e9805a4906d3b923535d44d04aa35
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: '[REDACTED]'
    created_at: '2026-08-09T19:58:50.122021+00:00'
    selected_ref: 23a28b1f02319faff905d2733ef290c26d7cb097
    selected_sha: 23a28b1f02319faff905d2733ef290c26d7cb097
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-970
    target_state: Done
    evidence_fingerprint: 8a4300fa26305215ba607ef34385de5d9b0e9805a4906d3b923535d44d04aa35
    audit_ids:
    - audit-dbc0ee15412c
    - audit-1cef3482ca27
    kind: override
    applied: true
    retired_at: '2026-08-09T19:58:58.381915+00:00'
  oompah.terminal_audit_result_intents: []
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-dbc0ee15412c
    project_id: proj-14849f1b
    task_id: OOMPAH-970
    target_state: Done
    request_state: cancelled
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 8a4300fa26305215ba607ef34385de5d9b0e9805a4906d3b923535d44d04aa35
    attempts:
    - version: 1
      attempt_id: attempt-a159950819f6
      target_state: Done
      request_state: in_progress
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 8a4300fa26305215ba607ef34385de5d9b0e9805a4906d3b923535d44d04aa35
      created_at: '2026-08-09T19:57:33.700776+00:00'
      provider_id: prov-651d553c
      model: haiku
      started_at: '2026-08-09T19:57:33.700776+00:00'
      branch_key: OOMPAH-970
      selected_ref: 23a28b1f02319faff905d2733ef290c26d7cb097
      selected_sha: 23a28b1f02319faff905d2733ef290c26d7cb097
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: Ready to Integrate
    created_at: '2026-08-09T19:55:53.568484+00:00'
    selected_ref: 23a28b1f02319faff905d2733ef290c26d7cb097
    selected_sha: 23a28b1f02319faff905d2733ef290c26d7cb097
    updated_at: '2026-08-09T19:58:58.381870+00:00'
  - version: 1
    audit_id: audit-1cef3482ca27
    project_id: proj-14849f1b
    task_id: OOMPAH-970
    target_state: Merged
    request_state: cancelled
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 8a4300fa26305215ba607ef34385de5d9b0e9805a4906d3b923535d44d04aa35
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: Ready to Integrate
    created_at: '2026-08-09T19:55:53.568484+00:00'
    selected_ref: 23a28b1f02319faff905d2733ef290c26d7cb097
    selected_sha: 23a28b1f02319faff905d2733ef290c26d7cb097
    updated_at: '2026-08-09T19:58:58.381899+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-a159950819f6
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 8a4300fa26305215ba607ef34385de5d9b0e9805a4906d3b923535d44d04aa35
    created_at: '2026-08-09T19:57:33.700776+00:00'
    provider_id: prov-651d553c
    model: haiku
    started_at: '2026-08-09T19:57:33.700776+00:00'
    branch_key: OOMPAH-970
    selected_ref: 23a28b1f02319faff905d2733ef290c26d7cb097
    selected_sha: 23a28b1f02319faff905d2733ef290c26d7cb097
oompah.task_costs:
  total_input_tokens: 150
  total_output_tokens: 42
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 150
      output_tokens: 42
      cost_usd: 0.0
  runs:
  - profile: auditor
    model: unknown
    input_tokens: 150
    output_tokens: 42
    cost_usd: 0.0
    recorded_at: '2026-08-09T19:59:02.069921+00:00'
---
## Summary

Hosted PR #776 exact head 6f3ee4170 reproduced a timing race in Python 3.12 after 19,176 tests passed: tests/test_workflow_runtime.py::test_detached_effect_heartbeats_and_drains_without_duplicate_apply sleeps 220ms against a 150ms real-time lease and then requires lease_expires_at > time.time(); under loaded CI the most recent heartbeat missed that narrow observation by about 63ms. Python 3.11/3.13 passed and the failure is unrelated to the OOMPAH-968 production diff, but a race-dependent test is a bug.\n\nImplementation scope: replace wall-clock sleep/hope with a deterministic synchronization or injectable clock/renewal observation that proves the actual detached worker heartbeat renews the exact job lease while apply remains blocked; then prove drain does not duplicate the effect and completion occurs once. Do not weaken lease-expiry production behavior or merely widen sleeps/timeouts. Relevant files: tests/test_workflow_runtime.py and narrow WorkflowRuntime/DurableWorkflowWorker test seams only if necessary. Search and preserve OOMPAH-957 deterministic timing conventions.\n\nRequired tests: the heartbeat proof passes repeatedly under loaded scheduling without wall-clock races; it still fails if the heartbeat does not renew; exact lease ownership, drain false-while-blocked, single apply, and final completion remain asserted. Acceptance: repeated focused runs pass, workflow runtime module passes, Ruff/diff checks pass, and protected Python 3.11/3.12/3.13 CI passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-09 19:37
---
Accepted for direct-owner repair from PR #776 Python 3.12. The protected job is rerunning; this task removes the underlying sleep-based race regardless of retry outcome.
---
author: oompah
created: 2026-08-09 19:46
---
Final rebased head 23a28b1f02319faff905d2733ef290c26d7cb097 is pushed on merged OOMPAH-968 main. Stable patch-id is unchanged from independently reviewed head 13dffed48. Post-rebase validation: full workflow-runtime module 101 passed; Ruff error rules and diff checks pass.
---
author: oompah
created: 2026-08-09 19:47
---
Replace the loaded-CI lease-heartbeat sleep race with deterministic exact-token renewal barriers. Final head 23a28b1f02319faff905d2733ef290c26d7cb097; 20/20 repeated regression runs, 101 post-rebase runtime tests, and independent review are green.
---
author: oompah
created: 2026-08-09 19:52
---
Branch quality gate blocked review creation.

Branch: `OOMPAH-970`
Target: `main`
Head: `23a28b1f02319faff905d2733ef290c26d7cb097`
Command: `make test`
Result: `infrastructure_error`
Process: ended without subprocess exit evidence

Infrastructure action required: repair or replace the operator-owned quality-gate runtime. No candidate CI-fix status was applied because the candidate command did not run.

Output tail:
```text
Trusted quality-gate runtime corruption detected; candidate CI was not run: trusted editable source mapping is inconsistent: expected one of ['/home/shedwards/src/oompah'] or immutable candidate /home/shedwards/.oompah/tmp/oompah-quality-gate-7tvpz6ed/run/workspace; actual /home/shedwards/src/oompah-967. Repair or replace the service test runtime before rerunning the branch gate.
```
---
author: oompah
created: 2026-08-09 19:55
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-09 19:57
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/haiku)
---
author: oompah
created: 2026-08-09 19:57
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-09 19:58
---
Override by oompah-cli: terminal transition to Done applied by project owner.

Reason: [REDACTED]
---
author: oompah
created: 2026-08-09 19:59
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/haiku]
- Turns: 0, Tool calls: 8
- Tokens: 150 in / 42 out [192 total]
- Cost: $0.0000
- Exit: terminated, Duration: 1m 23s
- Log: OOMPAH-970__20260809T195756Z.jsonl
---
author: oompah
created: 2026-08-09 19:59
---
Deterministic detached-heartbeat coverage is merged via PR #777 with the full hosted matrix green; detached-auditor harness portability is tracked separately in OOMPAH-971.
---
<!-- COMMENTS:END -->
