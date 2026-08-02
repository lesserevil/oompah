---
id: OOMPAH-422
type: bug
status: Archived
priority: 1
title: Require actionable handoffs for Needs Human transitions
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-23T20:10:29.633604Z'
updated_at: '2026-08-02T01:42:26.933601Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.terminal_audit:
  queued_comment_posted: true
  applied_result_attempts:
    attempt-fee6cb43254f: '2026-08-02T01:42:23.762979+00:00'
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-422
    target_state: Archived
    evidence_fingerprint: a30bc12eef642fb1bfa4550424fc867c90465f95e43f5ca133a9a7c1ae9a1bca
    audit_ids:
    - audit-f05e417ec06e
    kind: result
    applied: true
    retired_at: '2026-08-02T01:42:23.762991+00:00'
  oompah.terminal_audit_result_intents:
  - project_id: proj-14849f1b
    task_id: OOMPAH-422
    audit_id: audit-f05e417ec06e
    attempt_id: attempt-fee6cb43254f
    target_state: Archived
    evidence_fingerprint: a30bc12eef642fb1bfa4550424fc867c90465f95e43f5ca133a9a7c1ae9a1bca
    status: Archived
    audit_ids:
    - audit-f05e417ec06e
    applied: false
    created_at: '2026-08-02T01:42:23.763007+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-f05e417ec06e
    project_id: proj-14849f1b
    task_id: OOMPAH-422
    target_state: Archived
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: a30bc12eef642fb1bfa4550424fc867c90465f95e43f5ca133a9a7c1ae9a1bca
    attempts:
    - version: 1
      attempt_id: attempt-fee6cb43254f
      target_state: Archived
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: a30bc12eef642fb1bfa4550424fc867c90465f95e43f5ca133a9a7c1ae9a1bca
      created_at: '2026-08-02T01:36:08.392094+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-02T01:36:08.392094+00:00'
      branch_key: OOMPAH-422
      verdict: pass
      completed_at: '2026-08-02T01:42:23.762790+00:00'
      ended_at: '2026-08-02T01:42:23.762790+00:00'
    requested_by:
      version: 1
      identity: oompah
      source: auto_archive
    previous_state: Merged
    created_at: '2026-08-02T01:13:39.528291+00:00'
    updated_at: '2026-08-02T01:42:23.762790+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-fee6cb43254f
    target_state: Archived
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: a30bc12eef642fb1bfa4550424fc867c90465f95e43f5ca133a9a7c1ae9a1bca
    created_at: '2026-08-02T01:36:08.392094+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-02T01:36:08.392094+00:00'
    branch_key: OOMPAH-422
---
## Summary

Enforce the tracker invariant that every transition to Needs Human is followed by a final oompah comment containing actionable human instructions or one or more explicit questions. Route all orchestrator transition paths through the shared helper and reject empty/non-actionable handoffs at the tracker boundary. Add native-tracker, GitHub-tracker, and orchestration regression tests that verify the final comment is the required human handoff. Run make test.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-23 20:13
---
Implemented tracker-boundary validation for Needs Human handoffs, routed all orchestrator transition paths through the shared handoff helper, and added native/GitHub regression coverage. Full make test passed. Live audit found zero tasks currently in Needs Human.
---
author: oompah
created: 2026-07-23 20:13
---
Enforced actionable final handoffs for Needs Human and verified the suite.
---
author: oompah
created: 2026-07-26 00:28
---
Delivery reconciled: actionable Needs Human handoff enforcement is present on origin/main in commit 296895829. This task was Done rather than waiting for an agent; it is now being aligned with the delivered repository state.
---
author: oompah
created: 2026-07-26 00:28
---
Verified delivered on origin/main in 296895829 and reconciled stale Done state.
---
author: oompah
created: 2026-08-02 01:13
---
Queued Archived audit: Aged Merged auto-archive (closed 7 days ago). An auditor will review before the task is retired.
---
author: oompah
created: 2026-08-02 01:36
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-08-02 01:36
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-02 01:42
---
Audit PASS — Archived

[REDACTED]

Safe evidence:
- delivery_commit: 296895829 on origin/main
- helper_location: oompah/tracker.py:72 validate_needs_human_comment
- native_tracker_use: oompah/oompah_md_tracker.py:791
- github_tracker_use: oompah/github_tracker.py:2169
- orchestrator_shared_helper: oompah/orchestrator.py:22679 _mark_needs_human (called from 8 sites)
- native_tests: tests/test_oompah_md_tracker.py -k needs_human: 5 passed
- github_tests: tests/test_github_tracker.py -k needs_human: 2 passed
- orchestrator_tests: tests/test_orchestrator_github_lifecycle.py -k needs_human: 3 passed
- epic_strategy_tests: tests/test_epic_strategy.py -k needs_human: 2 passed
- aging: Task Merged 7 days ago; auto-archive queued 2026-08-02
---
<!-- COMMENTS:END -->
