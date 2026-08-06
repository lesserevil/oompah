---
id: OOMPAH-569
type: task
status: Archived
priority: null
title: Sanitize credentials from branch quality-gate subprocesses
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-29T23:26:15.028867Z'
updated_at: '2026-08-06T00:58:15.108627Z'
work_branch: OOMPAH-569
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/585
review_number: '585'
merged_at: null
oompah.integration:
  version: 1
  state: ready
  attempts: 0
  task_branch: OOMPAH-569
  head_sha: 52619c962f88860534bdc858e79728e6f12db606
  submitted_at: '2026-07-29T23:34:16.246990+00:00'
  updated_at: '2026-07-29T23:34:16.246990+00:00'
oompah.review_url: https://github.com/lesserevil/oompah/pull/585
oompah.review_number: '585'
oompah.work_branch: OOMPAH-569
oompah.target_branch: main
oompah.terminal_audit:
  queued_comment_posted: true
  applied_result_attempts:
    attempt-72712cbbdb7f: '2026-08-06T00:56:21.172383+00:00'
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-569
    target_state: Archived
    evidence_fingerprint: 9313d092850089e39f1d2a0def72aa464f31fb2ca9f1bd370eaee0d9d64c2923
    audit_ids:
    - audit-fbb0069d7349
    kind: result
    applied: true
    retired_at: '2026-08-06T00:56:21.172390+00:00'
  oompah.terminal_audit_result_intents:
  - project_id: proj-14849f1b
    task_id: OOMPAH-569
    audit_id: audit-fbb0069d7349
    attempt_id: attempt-72712cbbdb7f
    target_state: Archived
    evidence_fingerprint: 9313d092850089e39f1d2a0def72aa464f31fb2ca9f1bd370eaee0d9d64c2923
    status: Archived
    audit_ids:
    - audit-fbb0069d7349
    applied: true
    created_at: '2026-08-06T00:56:21.172399+00:00'
    applied_at: '2026-08-06T00:56:31.432938+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-fbb0069d7349
    project_id: proj-14849f1b
    task_id: OOMPAH-569
    target_state: Archived
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 9313d092850089e39f1d2a0def72aa464f31fb2ca9f1bd370eaee0d9d64c2923
    attempts:
    - version: 1
      attempt_id: attempt-72712cbbdb7f
      target_state: Archived
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 9313d092850089e39f1d2a0def72aa464f31fb2ca9f1bd370eaee0d9d64c2923
      created_at: '2026-08-06T00:24:47.202368+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-06T00:24:47.202368+00:00'
      branch_key: OOMPAH-569
      verdict: pass
      completed_at: '2026-08-06T00:56:21.172276+00:00'
      ended_at: '2026-08-06T00:56:21.172276+00:00'
    requested_by:
      version: 1
      identity: oompah
      source: auto_archive
    previous_state: Merged
    created_at: '2026-08-06T00:24:24.808263+00:00'
    updated_at: '2026-08-06T00:56:21.172276+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-72712cbbdb7f
    target_state: Archived
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 9313d092850089e39f1d2a0def72aa464f31fb2ca9f1bd370eaee0d9d64c2923
    created_at: '2026-08-06T00:24:47.202368+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-06T00:24:47.202368+00:00'
    branch_key: OOMPAH-569
oompah.task_costs:
  total_input_tokens: 6
  total_output_tokens: 553
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 6
      output_tokens: 553
      cost_usd: 0.0
  runs:
  - profile: auditor
    model: unknown
    input_tokens: 6
    output_tokens: 553
    cost_usd: 0.0
    recorded_at: '2026-08-06T00:58:11.180971+00:00'
---
## Summary

Implementation scope: update BranchQualityGate so configured review and integration commands inherit a sanitized environment with OOMPAH_SERVER_USERNAME, OOMPAH_SERVER_PASSWORD, and OOMPAH_SERVER_PASSWORD_FILE removed, reusing the existing client_auth.agent_environment helper. This prevents server operator credentials from leaking into test/build subprocesses and removes the deterministic tests/test_client_auth.py failure seen in fresh integration worktrees. Relevant files: oompah/quality_gate.py and tests/test_quality_gate.py. Tests: add a regression command that records whether all client-auth variables are absent even when the parent process defines them; run focused quality-gate/client-auth tests and make test. Acceptance criteria: quality gates receive ordinary environment settings but no client auth secrets, the regression fails on the old behavior and passes with the fix, and the complete branch gate passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-29 23:34
---
Sanitized branch quality-gate subprocess environments and versioned cached evidence so pre-fix failures rerun. Complete gate: 13,602 passed, 7 skipped.
---
author: oompah
created: 2026-07-29 23:41
---
YOLO: merged PR #585.
---
author: oompah
created: 2026-08-06 00:24
---
Queued Archived audit: Aged Merged auto-archive (closed 7 days ago). An auditor will review before the task is retired.
---
author: oompah
created: 2026-08-06 00:24
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-08-06 00:25
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-06 00:56
---
Audit PASS — Archived

[REDACTED]

Safe evidence:
- merge_commit: 8483db2e3e718c1f5f6476018d954574ce5d42f9
- task_commit: 52619c962f88860534bdc858e79728e6f12db606
- pr: #585
- quality_gate_import: from oompah.client_auth import agent_environment (oompah/quality_gate.py:17)
- quality_gate_popen: env=agent_environment() (oompah/quality_gate.py:215)
- client_auth_stripped_vars: OOMPAH_SERVER_USERNAME, OOMPAH_SERVER_PASSWORD, OOMPAH_SERVER_PASSWORD_FILE
- regression_test: tests/test_quality_gate.py::test_gate_subprocess_strips_client_credentials_only
- evidence_version_test: tests/test_quality_gate.py::test_pre_sanitization_evidence_is_invalidated
- focused_test_results: test_quality_gate.py 9 passed; test_client_auth.py 60 passed
- ancestry: merge commit 8483db2e3 is an ancestor of main and origin/main
- aging_basis: closed 2026-07-29; today 2026-08-06 (>=7 days)
---
author: oompah
created: 2026-08-06 00:58
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/opus]
- Turns: 42, Tool calls: 26
- Tokens: 6 in / 553 out [559 total]
- Cost: $0.0000
- Exit: normal, Duration: 33m 20s
- Log: OOMPAH-569__20260806T002510Z.jsonl
---
<!-- COMMENTS:END -->
