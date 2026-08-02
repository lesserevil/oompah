---
id: OOMPAH-440
type: task
status: Archived
priority: null
title: Count claimed shared-epic children in branch serialization
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-24T16:07:22.198190Z'
updated_at: '2026-08-02T01:24:11.975028Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.terminal_audit:
  queued_comment_posted: true
  applied_result_attempts:
    attempt-7ea8e5abcca8: '2026-08-02T01:24:05.151959+00:00'
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-440
    target_state: Archived
    evidence_fingerprint: 0c2d0c972091153ddfcabfa8f158cb9dbb77e09001c3e642d47a17138ab3e57e
    audit_ids:
    - audit-2df4dfc46584
    kind: result
    applied: true
    retired_at: '2026-08-02T01:24:05.151973+00:00'
  oompah.terminal_audit_result_intents:
  - project_id: proj-14849f1b
    task_id: OOMPAH-440
    audit_id: audit-2df4dfc46584
    attempt_id: attempt-7ea8e5abcca8
    target_state: Archived
    evidence_fingerprint: 0c2d0c972091153ddfcabfa8f158cb9dbb77e09001c3e642d47a17138ab3e57e
    status: Archived
    audit_ids:
    - audit-2df4dfc46584
    applied: true
    created_at: '2026-08-02T01:24:05.151992+00:00'
    applied_at: '2026-08-02T01:24:11.085393+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-2df4dfc46584
    project_id: proj-14849f1b
    task_id: OOMPAH-440
    target_state: Archived
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 0c2d0c972091153ddfcabfa8f158cb9dbb77e09001c3e642d47a17138ab3e57e
    attempts:
    - version: 1
      attempt_id: attempt-7ea8e5abcca8
      target_state: Archived
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 0c2d0c972091153ddfcabfa8f158cb9dbb77e09001c3e642d47a17138ab3e57e
      created_at: '2026-08-02T01:16:39.459255+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-02T01:16:39.459255+00:00'
      branch_key: OOMPAH-440
      verdict: pass
      completed_at: '2026-08-02T01:24:05.151737+00:00'
      ended_at: '2026-08-02T01:24:05.151737+00:00'
    requested_by:
      version: 1
      identity: oompah
      source: auto_archive
    previous_state: Merged
    created_at: '2026-08-02T01:14:12.083684+00:00'
    updated_at: '2026-08-02T01:24:05.151737+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-7ea8e5abcca8
    target_state: Archived
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 0c2d0c972091153ddfcabfa8f158cb9dbb77e09001c3e642d47a17138ab3e57e
    created_at: '2026-08-02T01:16:39.459255+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-02T01:16:39.459255+00:00'
    branch_key: OOMPAH-440
---
## Summary

The shared-epic dispatch gate documents that it serializes running and claimed children, but _epic_in_flight_count currently counts only running entries. Include claimed direct children when evaluating the parent epic branch, without changing the existing P0 bypass behavior. Add regression coverage for a claimed sibling blocking dispatch and for nonmatching claims not blocking it. Run make test and deploy.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-24 16:09
---
Deployed shared-epic claim serialization. Claimed siblings now count as in-flight before their worker is registered, closing the event-driven dispatch race; P0 behavior is unchanged. Added same-epic and different-epic claim regression coverage; make test passed (12,316 tests). Commit 0e5fb0632 pushed to main.
---
author: oompah
created: 2026-07-26 00:29
---
Delivery reconciled: shared-epic claim serialization before worker startup is present on origin/main in commit 0e5fb0632. This task was Done rather than waiting for an agent; it is now being aligned with the delivered repository state.
---
author: oompah
created: 2026-07-26 00:29
---
Verified delivered on origin/main in 0e5fb0632 and reconciled stale Done state.
---
author: oompah
created: 2026-08-02 01:14
---
Queued Archived audit: Aged Merged auto-archive (closed 7 days ago). An auditor will review before the task is retired.
---
author: oompah
created: 2026-08-02 01:16
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-08-02 01:16
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-02 01:24
---
Audit PASS — Archived

[REDACTED]

Safe evidence:
- delivery_commit: 0e5fb0632781a90e4e10fb3afad1ba39e7a86bb9
- delivery_commit_date: 2026-07-24 16:09:24 +0000
- audit_queued_date: 2026-08-02
- age_days_since_merge: 9
- implementation_file: oompah/orchestrator.py
- implementation_function: _epic_in_flight_count (line 9732)
- state_field_file: oompah/models.py
- state_field_line: 1461
- regression_tests_file: tests/test_epic_strategy.py
- regression_test_same_epic_line: 877
- regression_test_different_epic_line: 893
- test_evidence_note: Prior delivery comment records make test 12,316 tests passing at time of merge
---
<!-- COMMENTS:END -->
