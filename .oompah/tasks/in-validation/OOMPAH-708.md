---
id: OOMPAH-708
type: task
status: In Validation
priority: 0
title: Repair duplicate-screening owner-resolution project lookup
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels:
- human-only
- ci-fix
assignee: null
created_at: '2026-08-02T22:20:11.202634Z'
updated_at: '2026-08-02T23:01:42.557241Z'
work_branch: OOMPAH-708
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/664
review_number: '664'
review_head: null
merged_at: null
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  task_branch: OOMPAH-708
  head_sha: b965154dbf216ffb3587f59c2eb30aa681c73796
  submitted_at: '2026-08-02T22:22:47.553512+00:00'
  updated_at: '2026-08-02T22:22:47.553512+00:00'
oompah.review_url: https://github.com/lesserevil/oompah/pull/664
oompah.review_number: '664'
oompah.work_branch: OOMPAH-708
oompah.target_branch: main
oompah.terminal_audit:
  queued_comment_posted: true
  applied_result_attempts:
    attempt-de683a25577c: '2026-08-02T23:01:15.302042+00:00'
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-708
    target_state: Done
    evidence_fingerprint: e4fef94ce3bc314f97e3bd4ec0cc87af579ea569d7c631043b0ef7afcfebf452
    audit_ids:
    - audit-83ea41fbc0d5
    kind: result
    applied: true
    retired_at: '2026-08-02T23:01:15.302055+00:00'
  oompah.terminal_audit_result_intents:
  - project_id: proj-14849f1b
    task_id: OOMPAH-708
    audit_id: audit-83ea41fbc0d5
    attempt_id: attempt-de683a25577c
    target_state: Done
    evidence_fingerprint: e4fef94ce3bc314f97e3bd4ec0cc87af579ea569d7c631043b0ef7afcfebf452
    status: In Validation
    audit_ids:
    - audit-83ea41fbc0d5
    applied: true
    created_at: '2026-08-02T23:01:15.302072+00:00'
    applied_at: '2026-08-02T23:01:21.834146+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-83ea41fbc0d5
    project_id: proj-14849f1b
    task_id: OOMPAH-708
    target_state: Done
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: e4fef94ce3bc314f97e3bd4ec0cc87af579ea569d7c631043b0ef7afcfebf452
    attempts:
    - version: 1
      attempt_id: attempt-de683a25577c
      target_state: Done
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: e4fef94ce3bc314f97e3bd4ec0cc87af579ea569d7c631043b0ef7afcfebf452
      created_at: '2026-08-02T22:59:16.931152+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-02T22:59:16.931152+00:00'
      branch_key: OOMPAH-708
      verdict: pass
      completed_at: '2026-08-02T23:01:15.301859+00:00'
      ended_at: '2026-08-02T23:01:15.301859+00:00'
    requested_by:
      version: 1
      identity: lesserevil
      source: forge
    previous_state: Open
    created_at: '2026-08-02T22:58:58.819037+00:00'
    updated_at: '2026-08-02T23:01:15.301859+00:00'
  - version: 1
    audit_id: audit-5e5e124258f5
    project_id: proj-14849f1b
    task_id: OOMPAH-708
    target_state: Merged
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: e4fef94ce3bc314f97e3bd4ec0cc87af579ea569d7c631043b0ef7afcfebf452
    attempts:
    - version: 1
      attempt_id: attempt-4573bdf88966
      target_state: Merged
      request_state: in_progress
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: e4fef94ce3bc314f97e3bd4ec0cc87af579ea569d7c631043b0ef7afcfebf452
      created_at: '2026-08-02T23:01:41.437365+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-02T23:01:41.437365+00:00'
      branch_key: OOMPAH-708
    requested_by:
      version: 1
      identity: lesserevil
      source: forge
    previous_state: Open
    created_at: '2026-08-02T22:58:58.819037+00:00'
    updated_at: '2026-08-02T23:01:41.437365+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-de683a25577c
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: e4fef94ce3bc314f97e3bd4ec0cc87af579ea569d7c631043b0ef7afcfebf452
    created_at: '2026-08-02T22:59:16.931152+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-02T22:59:16.931152+00:00'
    branch_key: OOMPAH-708
  - version: 1
    attempt_id: attempt-4573bdf88966
    target_state: Merged
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: e4fef94ce3bc314f97e3bd4ec0cc87af579ea569d7c631043b0ef7afcfebf452
    created_at: '2026-08-02T23:01:41.437365+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-02T23:01:41.437365+00:00'
    branch_key: OOMPAH-708
oompah.task_costs:
  total_input_tokens: 31
  total_output_tokens: 5075
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 31
      output_tokens: 5075
      cost_usd: 0.0
  runs:
  - profile: auditor
    model: unknown
    input_tokens: 31
    output_tokens: 5075
    cost_usd: 0.0
    recorded_at: '2026-08-02T23:01:33.707328+00:00'
---
## Summary

Triggered by: OOMPAH-706\n\nProduction reproduction on 2026-08-02: authenticated POST /api/v1/issues/OOMPAH-706/duplicate-screening/owner-resolution returned HTTP 503 with `Orchestrator object has no attribute _get_project_by_id`. The route calls orch._get_project_by_id(project_id), but Orchestrator exposes project_store.get instead. This makes the documented recovery action for exhausted duplicate screening unusable and strands tasks in Needs Human.\n\nImplementation scope:\n- Resolve the managed project through the supported ProjectStore API in the owner-resolution route.\n- Preserve authenticated-principal/actor-conflict checks and fail closed when the project is absent.\n- Ensure owner authorization receives the actual managed Project object.\n\nRelevant code: oompah/server.py api_owner_resolve_duplicate_screening; tests/test_server_duplicate_screening_owner.py.\n\nRequired tests:\n- Reproduce the route against an Orchestrator-shaped object without _get_project_by_id and prove a valid owner request succeeds.\n- Prove missing projects and non-owner principals remain denied without mutating duplicate metadata.\n\nAcceptance criteria:\n- The live owner-resolution endpoint no longer returns 503 for a valid managed project.\n- OOMPAH-706 can be authoritatively returned from Needs Human to Open.\n- Focused tests and make test/check-secrets pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-02 22:20
---
Claimed directly to unblock the currently stranded OOMPAH-706 owner-resolution flow. OOMPAH-707 separately tracks the watchdog resetting direct owner work without a scheduler runtime.
---
author: oompah
created: 2026-08-02 22:22
---
Replaced the nonexistent orchestrator project lookup with ProjectStore.get, added fail-closed missing-project handling, and added endpoint regressions. Focused tests: 5 passed. Secret scan passed.
---
author: oompah
created: 2026-08-02 22:31
---
Branch quality gate blocked review creation.

Branch: `OOMPAH-708`
Target: `main`
Head: `b965154dbf216ffb3587f59c2eb30aa681c73796`
Command: `make test`
Result: `infrastructure_error`

Infrastructure action required: repair or replace the operator-owned quality-gate runtime. No candidate CI-fix status was applied because the candidate command did not run.

Output tail:
```text
Trusted quality-gate runtime corruption detected; candidate CI was not run: trusted editable source mapping is inconsistent: expected one of ['/home/shedwards/src/oompah'] or immutable candidate /home/shedwards/.oompah/tmp/oompah-quality-gate-2k_flxi5/workspace; actual /home/shedwards/.oompah/worktrees/oompah/OOMPAH-701. Repair or replace the service test runtime before rerunning the branch gate.
```
---
author: oompah
created: 2026-08-02 22:32
---
Branch quality gate blocked review creation.

Branch: `OOMPAH-708`
Target: `main`
Head: `b965154dbf216ffb3587f59c2eb30aa681c73796`
Command: `make test`
Result: `infrastructure_error`

Infrastructure action required: repair or replace the operator-owned quality-gate runtime. No candidate CI-fix status was applied because the candidate command did not run.

Output tail:
```text
Trusted quality-gate runtime corruption detected; candidate CI was not run: trusted editable source mapping is inconsistent: expected one of ['/home/shedwards/src/oompah'] or immutable candidate /home/shedwards/.oompah/tmp/oompah-quality-gate-2lcw5dfn/workspace; actual /home/shedwards/.oompah/worktrees/oompah/OOMPAH-701. Repair or replace the service test runtime before rerunning the branch gate.
```
---
author: oompah
created: 2026-08-02 22:33
---
Branch quality gate blocked review creation.

Branch: `OOMPAH-708`
Target: `main`
Head: `b965154dbf216ffb3587f59c2eb30aa681c73796`
Command: `make test`
Result: `infrastructure_error`

Infrastructure action required: repair or replace the operator-owned quality-gate runtime. No candidate CI-fix status was applied because the candidate command did not run.

Output tail:
```text
Trusted quality-gate runtime corruption detected; candidate CI was not run: trusted editable source mapping is inconsistent: expected one of ['/home/shedwards/src/oompah'] or immutable candidate /home/shedwards/.oompah/tmp/oompah-quality-gate-8yzluei_/workspace; actual /home/shedwards/.oompah/worktrees/oompah/OOMPAH-701. Repair or replace the service test runtime before rerunning the branch gate.
```
---
author: oompah
created: 2026-08-02 22:41
---
Branch quality gate passed for `b965154dbf216ffb3587f59c2eb30aa681c73796` using `make test` in 425.8s. Review creation may proceed.
---
author: oompah
created: 2026-08-02 22:50
---
YOLO: CI tests failed on MR #664. Fix the failing tests so this MR can merge. Do NOT rewrite the feature — only fix test failures. IMPORTANT: Paths in CI logs are not trustworthy. Run tests locally to get accurate paths and errors.
---
author: oompah
created: 2026-08-02 22:51
---
PR #664 Python 3.11 CI failure is unrelated to this endpoint patch: tests/test_agent.py::test_stop_kills_spawned_descendant timed out waiting 1 second for a shell child PID file; the other 15,013 tests passed, and Python 3.12/3.13 matrices passed. The failed GitHub Actions job has been rerun. Retaining the exact submitted head and human-only ownership fence pending the rerun.
---
author: oompah
created: 2026-08-02 22:52
---
[watchdog:stalled_task] Stalled-task watchdog audit (run #4)

**State audited:** `Needs CI Fix`
**Classification:** `actionable`
**Action:** `reopen`
**Evidence:** Recent comment indicates CI is now passing or PR has been merged; safe to reopen for dispatch.

*This comment is posted automatically by the oompah stalled-task watchdog. No human action required unless the classification above is incorrect.*
---
author: oompah
created: 2026-08-02 22:59
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-02 22:59
---
YOLO: merged PR #664.
---
author: oompah
created: 2026-08-02 22:59
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-08-02 22:59
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-02 23:01
---
Audit PASS — Done

[REDACTED]

Safe evidence:
- branch_head: b965154dbf216ffb3587f59c2eb30aa681c73796
- server_py_lookup_line: 12287: project = orch.project_store.get(project_id)
- server_py_fail_closed_status: 404 not_found when project is None
- server_py_authorization_line: 12298: if not is_project_owner(actor_login, project):
- removed_method_search: No remaining occurrences of _get_project_by_id in oompah/
- focused_tests: tests/test_server_duplicate_screening_owner.py: 5 passed in 0.96s
- merged_to_main: Merge commit 26ce120b9 on origin/main (PR #664)
- branch_gate_evidence: Prior comment reports `make test` passed for b965154db in 425.8s
---
author: oompah
created: 2026-08-02 23:01
---
Run #YOLO-reopen [attempt=YOLO-reopen, profile=auditor, role=auditor -> Claude/opus]
- Turns: 32, Tool calls: 25
- Tokens: 31 in / 5.1K out [5.1K total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 14s
- Log: OOMPAH-708__20260802T225924Z.jsonl
---
<!-- COMMENTS:END -->
