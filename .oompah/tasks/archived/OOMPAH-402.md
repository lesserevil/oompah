---
id: OOMPAH-402
type: task
status: Archived
priority: null
title: Advance focus after completed agent handoffs
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-22T05:27:02.143073Z'
updated_at: '2026-08-02T01:22:42.269578Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.terminal_audit:
  queued_comment_posted: true
  applied_result_attempts:
    attempt-636f51cc7643: '2026-08-02T01:22:39.587255+00:00'
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-402
    target_state: Archived
    evidence_fingerprint: c28cd5319bac2b11e945fe0c05ee5e25886b758250caec37db54974f4f07d033
    audit_ids:
    - audit-7ca8172a31f3
    kind: result
    applied: true
    retired_at: '2026-08-02T01:22:39.587269+00:00'
  oompah.terminal_audit_result_intents:
  - project_id: proj-14849f1b
    task_id: OOMPAH-402
    audit_id: audit-7ca8172a31f3
    attempt_id: attempt-636f51cc7643
    target_state: Archived
    evidence_fingerprint: c28cd5319bac2b11e945fe0c05ee5e25886b758250caec37db54974f4f07d033
    status: Archived
    audit_ids:
    - audit-7ca8172a31f3
    applied: false
    created_at: '2026-08-02T01:22:39.587288+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-7ca8172a31f3
    project_id: proj-14849f1b
    task_id: OOMPAH-402
    target_state: Archived
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: c28cd5319bac2b11e945fe0c05ee5e25886b758250caec37db54974f4f07d033
    attempts:
    - version: 1
      attempt_id: attempt-636f51cc7643
      target_state: Archived
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: c28cd5319bac2b11e945fe0c05ee5e25886b758250caec37db54974f4f07d033
      created_at: '2026-08-02T01:15:48.103448+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-02T01:15:48.103448+00:00'
      branch_key: OOMPAH-402
      verdict: pass
      completed_at: '2026-08-02T01:22:39.587062+00:00'
      ended_at: '2026-08-02T01:22:39.587062+00:00'
    requested_by:
      version: 1
      identity: oompah
      source: auto_archive
    previous_state: Merged
    created_at: '2026-08-02T01:13:12.552453+00:00'
    updated_at: '2026-08-02T01:22:39.587062+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-636f51cc7643
    target_state: Archived
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: c28cd5319bac2b11e945fe0c05ee5e25886b758250caec37db54974f4f07d033
    created_at: '2026-08-02T01:15:48.103448+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-02T01:15:48.103448+00:00'
    branch_key: OOMPAH-402
---
## Summary

Fix scheduler behavior where a normally completed agent handoff is retried as unfinished and the next run re-selects the same non-implementation focus. Use task comments and/or persisted focus state to recognize completed focus handoffs, advance to the next applicable focus, and avoid retrying solely because the task remains non-terminal when the handoff records productive completion. Cover OOMPAH-339's repeated Test Engineer routing with regression tests. Acceptance: a completed handoff advances focus; a no-op completion still retries; OOMPAH-339-like implementation tasks do not loop through completed investigation/test foci; relevant tests pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-22 05:31
---
Implemented and verified two scheduler fixes: (1) a durable Focus handoff comment now backfills its focus-complete label and advances focus instead of falling into completed-without-closing retries; (2) Test Engineer no longer wins solely from a generic Tests acceptance section, while explicit test routing and test-oriented titles still select it. Added regression coverage and ran make test.
---
author: oompah
created: 2026-07-22 05:31
---
Fixed handoff retry loops and test-focus preemption; added regression coverage; make test passed.
---
author: oompah
created: 2026-07-26 00:28
---
Delivery reconciled: focus advancement from durable handoff comments is present on origin/main in commit de48457e8. This task was Done rather than waiting for an agent; it is now being aligned with the delivered repository state.
---
author: oompah
created: 2026-07-26 00:28
---
Verified delivered on origin/main in de48457e8 and reconciled stale Done state.
---
author: oompah
created: 2026-08-02 01:13
---
Queued Archived audit: Aged Merged auto-archive (closed 7 days ago). An auditor will review before the task is retired.
---
author: oompah
created: 2026-08-02 01:15
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-08-02 01:15
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-02 01:22
---
Audit PASS — Archived

[REDACTED]

Safe evidence:
- delivery_commits: de48457e8 orchestrator + test; b9ec91b8f focus + test
- commit_dates_utc: 2026-07-22T05:29:11Z, 2026-07-22T05:30:52Z
- orchestrator_focus_advance_present: oompah/orchestrator.py:23459 _handoff_completed_focus with label backfill comment at 23493
- focus_regression_test_present: tests/test_orchestrator_duplicate_detection.py:251 test_handoff_comment_without_label_advances_focus
- focus_selection_fix_present: oompah/focus.py changes on main (18 lines added) + tests/test_focus.py new cases (28 lines added)
- closure_age_days: ~7 days since reconciled closure (2026-07-26) vs today 2026-08-02
---
<!-- COMMENTS:END -->
