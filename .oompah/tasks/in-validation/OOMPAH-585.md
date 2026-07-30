---
id: OOMPAH-585
type: epic
status: In Validation
priority: 1
title: Restore terminal-audit execution and truthful health reporting
parent: OOMPAH-584
children:
- OOMPAH-589
- OOMPAH-590
- OOMPAH-591
- OOMPAH-592
- OOMPAH-604
- OOMPAH-616
- OOMPAH-618
- OOMPAH-622
- OOMPAH-625
- OOMPAH-626
- OOMPAH-627
- OOMPAH-628
- OOMPAH-629
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-30T14:13:32.577860Z'
updated_at: '2026-07-30T23:32:31.823258Z'
work_branch: epic-OOMPAH-585
target_branch: epic-OOMPAH-584
review_url: https://github.com/lesserevil/oompah/pull/596
review_number: '596'
merged_at: null
oompah.review_url: https://github.com/lesserevil/oompah/pull/596
oompah.review_number: '596'
oompah.work_branch: epic-OOMPAH-585
oompah.target_branch: epic-OOMPAH-584
oompah.terminal_audit:
  queued_comment_posted: true
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-0b310adb4fa7
    project_id: proj-14849f1b
    task_id: OOMPAH-585
    target_state: Done
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 0cfb98eafc768e5e2b01af3fc05a46d57c2174f15a248e0583518caca77a559e
    attempts: []
    requested_by:
      version: 1
      identity: lesserevil
      source: forge
    previous_state: In Review
    created_at: '2026-07-30T23:32:29.243227+00:00'
  - version: 1
    audit_id: audit-6806c4fdb604
    project_id: proj-14849f1b
    task_id: OOMPAH-585
    target_state: Merged
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 0cfb98eafc768e5e2b01af3fc05a46d57c2174f15a248e0583518caca77a559e
    attempts: []
    requested_by:
      version: 1
      identity: lesserevil
      source: forge
    previous_state: In Review
    created_at: '2026-07-30T23:32:29.243227+00:00'
  attempt_history: []
---
## Summary

Goal

Make terminal auditing reliable and honestly observable from candidate selection through final tracker transition. Repair the malformed auditor-provider launch path, add bounded recovery, drain the current backlog, and ensure alerts represent execution failures rather than only metadata-enforcement failures.

Relevant context

Completion-auditor sessions for OOMPAH-580 and OOMPAH-582 failed with unknown URL type /chat/completions. The service reported 54 pending audits while the alert list was empty. Existing OOMPAH-460 covers terminal-audit product/UI work; this epic is limited to the uncovered runtime recovery and health-truth gap.

Acceptance criteria

Eligible auditors launch against validated absolute endpoints; invalid candidates fail closed with actionable safe diagnostics; pending requests retry without duplication; stale In Validation records reconcile; backlog age and launch failures generate durable alerts; recovered health clears alerts; focused and complete Makefile gates pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-30 23:31
---
Branch quality gate passed for `4510fb912aebc99dce90df1dc55e8ee952408401` using `make test` in 255.7s. Review creation may proceed.
---
author: oompah
created: 2026-07-30 23:32
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
<!-- COMMENTS:END -->
