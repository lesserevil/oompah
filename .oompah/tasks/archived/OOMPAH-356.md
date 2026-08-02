---
id: OOMPAH-356
type: epic
status: Archived
priority: 1
title: Reduce unfinished epic branch synchronization churn
parent: null
children:
- OOMPAH-357
- OOMPAH-358
- OOMPAH-359
blocked_by: []
labels:
- reliability
- workflow
assignee: null
created_at: '2026-07-22T01:23:32.887223Z'
updated_at: '2026-08-02T01:43:54.867856Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.terminal_audit:
  queued_comment_posted: true
  applied_result_attempts:
    attempt-50c3d6991111: '2026-08-02T01:43:49.023643+00:00'
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-356
    target_state: Archived
    evidence_fingerprint: afe4a724470fb72d93d5fc3e6ef18e8d543f1b54864f887b84c39a678efa8e3f
    audit_ids:
    - audit-609917f758c9
    kind: result
    applied: true
    retired_at: '2026-08-02T01:43:49.023655+00:00'
  oompah.terminal_audit_result_intents:
  - project_id: proj-14849f1b
    task_id: OOMPAH-356
    audit_id: audit-609917f758c9
    attempt_id: attempt-50c3d6991111
    target_state: Archived
    evidence_fingerprint: afe4a724470fb72d93d5fc3e6ef18e8d543f1b54864f887b84c39a678efa8e3f
    status: Archived
    audit_ids:
    - audit-609917f758c9
    applied: true
    created_at: '2026-08-02T01:43:49.023672+00:00'
    applied_at: '2026-08-02T01:43:53.947630+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-609917f758c9
    project_id: proj-14849f1b
    task_id: OOMPAH-356
    target_state: Archived
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: afe4a724470fb72d93d5fc3e6ef18e8d543f1b54864f887b84c39a678efa8e3f
    attempts:
    - version: 1
      attempt_id: attempt-50c3d6991111
      target_state: Archived
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: afe4a724470fb72d93d5fc3e6ef18e8d543f1b54864f887b84c39a678efa8e3f
      created_at: '2026-08-02T01:30:43.014536+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-02T01:30:43.014536+00:00'
      branch_key: OOMPAH-356
      verdict: pass
      completed_at: '2026-08-02T01:43:49.023480+00:00'
      ended_at: '2026-08-02T01:43:49.023480+00:00'
    requested_by:
      version: 1
      identity: oompah
      source: auto_archive
    previous_state: Merged
    created_at: '2026-08-02T01:12:44.770084+00:00'
    updated_at: '2026-08-02T01:43:49.023480+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-50c3d6991111
    target_state: Archived
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: afe4a724470fb72d93d5fc3e6ef18e8d543f1b54864f887b84c39a678efa8e3f
    created_at: '2026-08-02T01:30:43.014536+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-02T01:30:43.014536+00:00'
    branch_key: OOMPAH-356
---
## Summary

Change Oompah's branch-maintenance policy so incomplete epic branches do not receive routine merges or rebases from main, and never synchronize directly with other epic branches. Integration must occur through main. Rebase work is permitted only for an actionable condition: preparing or refreshing an epic PR, a merge-blocking conflict, an explicit user request, or a configured long-lived/stale branch threshold. Default behavior must detect and surface staleness without changing the branch.\n\nAcceptance criteria:\n- No automatic main-to-epic merge/rebase occurs merely because main advanced.\n- No epic-to-epic merge/rebase is scheduled.\n- The UI/API exposes detected branch staleness and the actionable reason for any scheduled rebase.\n- Existing projects migrate to the conservative default without configuration changes.\n- Child tasks implement policy, scheduling, and test coverage.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-22 01:30
---
Completed, tested, pushed, and restarted the conservative epic synchronization policy.
---
author: oompah
created: 2026-07-26 00:27
---
Delivery reconciled: the conservative unfinished-epic synchronization policy is present on origin/main in commit 2ba37886b. This task was Done rather than waiting for an agent; it is now being aligned with the delivered repository state.
---
author: oompah
created: 2026-07-26 00:27
---
Verified delivered on origin/main in 2ba37886b and reconciled stale Done state.
---
author: oompah
created: 2026-08-02 01:12
---
Queued Archived audit: Aged Merged auto-archive (closed 7 days ago). An auditor will review before the task is retired.
---
author: oompah
created: 2026-08-02 01:30
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-08-02 01:30
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-02 01:43
---
Audit PASS — Archived

[REDACTED]

Safe evidence:
- delivery_commit: 2ba37886b2f190fbfe84da6689e4a4f5877437fa
- delivery_commit_on_main: yes
- focused_tests_epic_rebase_state: 33 passed
- focused_tests_orchestrator_handlers: 277 passed
- children: OOMPAH-357, OOMPAH-358, OOMPAH-359 (all In Validation per parent listing)
- merged_duration_days: ~7 (reconciled 2026-07-26, archive queued 2026-08-02)
- archive_trigger: auto_archive (aged Merged)
---
<!-- COMMENTS:END -->
