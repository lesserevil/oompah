---
id: OOMPAH-411
type: task
status: Archived
priority: null
title: Unblock clean GitHub PRs with no CI checks
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-22T21:26:04.166626Z'
updated_at: '2026-08-02T01:29:55.786782Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.terminal_audit:
  queued_comment_posted: true
  applied_result_attempts:
    attempt-4dcd1469ec98: '2026-08-02T01:29:49.889015+00:00'
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-411
    target_state: Archived
    evidence_fingerprint: 7159e5752aee10089ad9fb965b4df9d4dcce2c47f386f340af157ddf7c46fee2
    audit_ids:
    - audit-5545580be785
    kind: result
    applied: true
    retired_at: '2026-08-02T01:29:49.889023+00:00'
  oompah.terminal_audit_result_intents:
  - project_id: proj-14849f1b
    task_id: OOMPAH-411
    audit_id: audit-5545580be785
    attempt_id: attempt-4dcd1469ec98
    target_state: Archived
    evidence_fingerprint: 7159e5752aee10089ad9fb965b4df9d4dcce2c47f386f340af157ddf7c46fee2
    status: Archived
    audit_ids:
    - audit-5545580be785
    applied: true
    created_at: '2026-08-02T01:29:49.889035+00:00'
    applied_at: '2026-08-02T01:29:54.864935+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-5545580be785
    project_id: proj-14849f1b
    task_id: OOMPAH-411
    target_state: Archived
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 7159e5752aee10089ad9fb965b4df9d4dcce2c47f386f340af157ddf7c46fee2
    attempts:
    - version: 1
      attempt_id: attempt-4dcd1469ec98
      target_state: Archived
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 7159e5752aee10089ad9fb965b4df9d4dcce2c47f386f340af157ddf7c46fee2
      created_at: '2026-08-02T01:16:16.416277+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-02T01:16:16.416277+00:00'
      branch_key: OOMPAH-411
      verdict: pass
      completed_at: '2026-08-02T01:29:49.888885+00:00'
      ended_at: '2026-08-02T01:29:49.888885+00:00'
    requested_by:
      version: 1
      identity: oompah
      source: auto_archive
    previous_state: Merged
    created_at: '2026-08-02T01:13:34.196829+00:00'
    updated_at: '2026-08-02T01:29:49.888885+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-4dcd1469ec98
    target_state: Archived
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 7159e5752aee10089ad9fb965b4df9d4dcce2c47f386f340af157ddf7c46fee2
    created_at: '2026-08-02T01:16:16.416277+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-02T01:16:16.416277+00:00'
    branch_key: OOMPAH-411
---
## Summary

Fix YOLO review handling so a GitHub PR whose status and check-run APIs are successfully read but report no checks is classified as an explicit no-checks verdict and can be merged when clean. Preserve unknown CI as non-mergeable when status/check data is unavailable. Update CI status contracts and GitHub provider mapping as needed, add unit coverage for no-checks versus unavailable CI and an orchestrator regression proving a clean no-checks GitHub PR is merged, and run make test. Acceptance: PR #540-style clean no-checks reviews no longer remain In Review indefinitely; unknown/unavailable CI remains fail-safe.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-22 21:29
---
Implemented and pushed edf4bc481. GitHub now treats successfully observed zero status/check runs as CI-passed, while unavailable CI remains unknown. Added SCM and YOLO regression coverage. make test passed.
---
author: oompah
created: 2026-07-22 21:30
---
Classified successfully observed zero GitHub checks as CI-passed, added regressions, restarted the service, and verified YOLO merged PR #540.
---
author: oompah
created: 2026-07-26 00:28
---
Delivery reconciled: clean GitHub PR handling when no CI checks exist is present on origin/main in commit edf4bc481. This task was Done rather than waiting for an agent; it is now being aligned with the delivered repository state.
---
author: oompah
created: 2026-07-26 00:28
---
Verified delivered on origin/main in edf4bc481 and reconciled stale Done state.
---
author: oompah
created: 2026-08-02 01:13
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
created: 2026-08-02 01:29
---
Audit PASS — Archived

[REDACTED]

Safe evidence:
- delivery_commit: edf4bc48116e56c3601a78531fe19b8b6cece81f
- delivery_commit_summary: Unblock clean PRs without CI checks
- delivery_files: oompah/scm.py; tests/test_scm.py; tests/test_orchestrator_merged.py
- ancestor_of_main: yes (edf4bc481 is ancestor of origin/main HEAD 6252b5434)
- scm_change_marker: oompah/scm.py:1124 comment 'Both CI APIs were read successfully and neither reports a check for this commit.'
- unit_test: tests/test_scm.py::TestFetchCiStatus::test_no_statuses_and_no_check_runs_are_eligible_to_merge PASSED locally
- orchestrator_test: tests/test_orchestrator_merged.py::TestYoloReviewSerializationByProject::test_no_check_pr_is_merged_after_github_classifies_it_as_passed PASSED locally
- aging_days: ~11 days between merge (2026-07-22) and archive request (2026-08-02)
- audit_metadata_at_head: task file records audit_id audit-5545580be785, target_state Archived, previous_state Merged, digest 7159e5752aee10089ad9fb965b4df9d4dcce2c47f386f340af157ddf7c46fee2
---
<!-- COMMENTS:END -->
