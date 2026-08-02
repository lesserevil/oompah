---
id: OOMPAH-423
type: bug
status: Archived
priority: 2
title: Keep normal epic branch drift out of alerts
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-23T20:25:33.664332Z'
updated_at: '2026-08-02T01:32:07.652138Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.terminal_audit:
  queued_comment_posted: true
  applied_result_attempts:
    attempt-cbb9b75f3a7b: '2026-08-02T01:32:02.174460+00:00'
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-423
    target_state: Archived
    evidence_fingerprint: 5d7ebf36cbf1542970a406e09386c26530e975bff039d00297afb59d0eaa7644
    audit_ids:
    - audit-d55809fc1544
    kind: result
    applied: true
    retired_at: '2026-08-02T01:32:02.174471+00:00'
  oompah.terminal_audit_result_intents:
  - project_id: proj-14849f1b
    task_id: OOMPAH-423
    audit_id: audit-d55809fc1544
    attempt_id: attempt-cbb9b75f3a7b
    target_state: Archived
    evidence_fingerprint: 5d7ebf36cbf1542970a406e09386c26530e975bff039d00297afb59d0eaa7644
    status: Archived
    audit_ids:
    - audit-d55809fc1544
    applied: false
    created_at: '2026-08-02T01:32:02.174484+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-d55809fc1544
    project_id: proj-14849f1b
    task_id: OOMPAH-423
    target_state: Archived
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 5d7ebf36cbf1542970a406e09386c26530e975bff039d00297afb59d0eaa7644
    attempts:
    - version: 1
      attempt_id: attempt-cbb9b75f3a7b
      target_state: Archived
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 5d7ebf36cbf1542970a406e09386c26530e975bff039d00297afb59d0eaa7644
      created_at: '2026-08-02T01:26:07.177474+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-02T01:26:07.177474+00:00'
      branch_key: OOMPAH-423
      verdict: pass
      completed_at: '2026-08-02T01:32:02.174303+00:00'
      ended_at: '2026-08-02T01:32:02.174303+00:00'
    requested_by:
      version: 1
      identity: oompah
      source: auto_archive
    previous_state: Merged
    created_at: '2026-08-02T01:13:44.969941+00:00'
    updated_at: '2026-08-02T01:32:02.174303+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-cbb9b75f3a7b
    target_state: Archived
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 5d7ebf36cbf1542970a406e09386c26530e975bff039d00297afb59d0eaa7644
    created_at: '2026-08-02T01:26:07.177474+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-02T01:26:07.177474+00:00'
    branch_key: OOMPAH-423
---
## Summary

Demote policy-compliant epic branch staleness (an unfinished epic behind its target branch) from the Oompah alert stream to informational epic-health state. Preserve actionable alerts for failed rebases, merge-blocking conflicts, credential failures, and human intervention. Add regression tests verifying normal drift does not populate alerts while the staleness state remains observable. Run make test.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-23 20:27
---
Demoted ordinary epic branch drift from the alert stream while preserving it in epic rebase/branch-health state. Failed rebases continue to emit actionable alerts. Added regression coverage and ran make test successfully.
---
author: oompah
created: 2026-07-23 20:27
---
Removed normal drift alerts; retained actionable failed-rebase alerts.
---
author: oompah
created: 2026-07-26 00:28
---
Delivery reconciled: normal epic drift alert suppression is present on origin/main in commit c57a02648. This task was Done rather than waiting for an agent; it is now being aligned with the delivered repository state.
---
author: oompah
created: 2026-07-26 00:28
---
Verified delivered on origin/main in c57a02648 and reconciled stale Done state.
---
author: oompah
created: 2026-08-02 01:13
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
created: 2026-08-02 01:32
---
Audit PASS — Archived

[REDACTED]

Safe evidence:
- delivering_commit: c57a0264852b5ae859851b21d5856bd6da9b7e87
- commit_on_origin_main: yes
- commit_authored: 2026-07-23T20:27:12Z
- days_since_merge: 10
- files_changed: oompah/config.py, oompah/orchestrator.py, tests/test_epic_rebase_state.py
- regression_test: tests/test_epic_rebase_state.py::TestEpicStaleAlert::test_normal_staleness_does_not_create_an_alert
- actionable_alert_test: tests/test_epic_rebase_state.py::TestEpicStaleAlert::test_failed_rebase_state_explains_failed_run
- informational_state_preserved: EpicRebaseState.STALE still surfaced in oompah/orchestrator.py (line 12335, 12356, 13848, 30792)
- aged_merge_policy: 7-day aged-Merged auto-archive; commit is ~10 days old
---
<!-- COMMENTS:END -->
