---
id: OOMPAH-348
type: epic
status: Archived
priority: 1
title: Eliminate Oompah service wedge failure modes
parent: null
children:
- OOMPAH-349
- OOMPAH-350
- OOMPAH-351
- OOMPAH-352
blocked_by: []
labels:
- reliability
- service-wedge
assignee: null
created_at: '2026-07-22T00:56:17.834972Z'
updated_at: '2026-08-02T01:38:33.406103Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.terminal_audit:
  queued_comment_posted: true
  applied_result_attempts:
    attempt-ca7274bb7555: '2026-08-02T01:38:30.631003+00:00'
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-348
    target_state: Archived
    evidence_fingerprint: 019e7f713efd2c0524db538b89e053c4f37dea2387e5a8c6a0bdcc82b735c98f
    audit_ids:
    - audit-2977f93aea96
    kind: result
    applied: true
    retired_at: '2026-08-02T01:38:30.631011+00:00'
  oompah.terminal_audit_result_intents:
  - project_id: proj-14849f1b
    task_id: OOMPAH-348
    audit_id: audit-2977f93aea96
    attempt_id: attempt-ca7274bb7555
    target_state: Archived
    evidence_fingerprint: 019e7f713efd2c0524db538b89e053c4f37dea2387e5a8c6a0bdcc82b735c98f
    status: Archived
    audit_ids:
    - audit-2977f93aea96
    applied: false
    created_at: '2026-08-02T01:38:30.631024+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-2977f93aea96
    project_id: proj-14849f1b
    task_id: OOMPAH-348
    target_state: Archived
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 019e7f713efd2c0524db538b89e053c4f37dea2387e5a8c6a0bdcc82b735c98f
    attempts:
    - version: 1
      attempt_id: attempt-ca7274bb7555
      target_state: Archived
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 019e7f713efd2c0524db538b89e053c4f37dea2387e5a8c6a0bdcc82b735c98f
      created_at: '2026-08-02T01:26:16.227144+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-02T01:26:16.227144+00:00'
      branch_key: OOMPAH-348
      verdict: pass
      completed_at: '2026-08-02T01:38:30.630895+00:00'
      ended_at: '2026-08-02T01:38:30.630895+00:00'
    requested_by:
      version: 1
      identity: oompah
      source: auto_archive
    previous_state: Merged
    created_at: '2026-08-02T01:12:18.712838+00:00'
    updated_at: '2026-08-02T01:38:30.630895+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-ca7274bb7555
    target_state: Archived
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 019e7f713efd2c0524db538b89e053c4f37dea2387e5a8c6a0bdcc82b735c98f
    created_at: '2026-08-02T01:26:16.227144+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-02T01:26:16.227144+00:00'
    branch_key: OOMPAH-348
---
## Summary

Implement and verify the durable reliability fixes identified from production wedge incidents: enforce real tracker timeouts, separate scheduler work from HTTP serving, bound shutdown, and capture diagnostics for any future stall. Child tasks define the independently testable implementation units. Success means a slow or hung tracker/git operation cannot make the UI/API unresponsive or prevent a restart.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-22 01:16
---
Completed and pushed the durable scheduler wedge fixes; Exocomp state branch migration is complete.
---
author: oompah
created: 2026-07-26 00:27
---
Delivery reconciled: the aggregate scheduler wedge fixes is present on origin/main in commit 6dd2cdfcf. This task was Done rather than waiting for an agent; it is now being aligned with the delivered repository state.
---
author: oompah
created: 2026-07-26 00:27
---
Verified delivered on origin/main in 6dd2cdfcf and reconciled stale Done state.
---
author: oompah
created: 2026-08-02 01:12
---
Queued Archived audit: Aged Merged auto-archive (closed 7 days ago). An auditor will review before the task is retired.
---
author: oompah
created: 2026-08-02 01:26
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-08-02 01:26
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-02 01:38
---
Audit PASS — Archived

[REDACTED]

Safe evidence:
- delivery_commit: 6dd2cdfcf
- delivery_on_main: true
- previous_state: Merged
- children_count: 4
- children_state: all In Validation, previous Merged, all cite 6dd2cdfcf
- delivery_age_days_approx: 11
- changed_paths_touched: .env.example, oompah/__main__.py, oompah/config.py, oompah/orchestrator.py, oompah/server.py, tests/test_dispatch_loop_heartbeat.py, tests/test_orchestrator_handlers.py, tests/test_task_cost_telemetry.py
- config_knobs_added: project_refresh_timeout_ms, project_refresh_max_concurrent, project_stale_cache_ttl_ms, worker_termination_timeout_ms, dispatch_loop_stale_factor
---
<!-- COMMENTS:END -->
