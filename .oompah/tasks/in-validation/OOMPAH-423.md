---
id: OOMPAH-423
type: bug
status: In Validation
priority: 2
title: Keep normal epic branch drift out of alerts
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-23T20:25:33.664332Z'
updated_at: '2026-08-02T01:13:48.765860Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.terminal_audit:
  queued_comment_posted: true
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-d55809fc1544
    project_id: proj-14849f1b
    task_id: OOMPAH-423
    target_state: Archived
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 5d7ebf36cbf1542970a406e09386c26530e975bff039d00297afb59d0eaa7644
    attempts: []
    requested_by:
      version: 1
      identity: oompah
      source: auto_archive
    previous_state: Merged
    created_at: '2026-08-02T01:13:44.969941+00:00'
  attempt_history: []
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
<!-- COMMENTS:END -->
