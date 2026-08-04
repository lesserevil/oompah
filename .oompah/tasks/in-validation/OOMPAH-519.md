---
id: OOMPAH-519
type: task
status: In Validation
priority: null
title: Recognize rebased child commits in epic review coverage
parent: OOMPAH-502
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-28T17:46:48.581634Z'
updated_at: '2026-08-04T21:03:38.376688Z'
work_branch: epic-OOMPAH-502
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.work_branch: epic-OOMPAH-502
oompah.terminal_audit:
  queued_comment_posted: true
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-5c4756acf882
    project_id: proj-14849f1b
    task_id: OOMPAH-519
    target_state: Archived
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 4f97b1e80afe23eb3b2bc6eae0f230068723c24a0790fc94a157daf0db07965c
    attempts:
    - version: 1
      attempt_id: attempt-21562b45ef77
      target_state: Archived
      request_state: in_progress
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 4f97b1e80afe23eb3b2bc6eae0f230068723c24a0790fc94a157daf0db07965c
      created_at: '2026-08-04T21:03:31.044179+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-04T21:03:31.044179+00:00'
      branch_key: epic-OOMPAH-502
    requested_by:
      version: 1
      identity: oompah
      source: auto_archive
    previous_state: Merged
    created_at: '2026-08-04T18:29:27.983166+00:00'
    updated_at: '2026-08-04T21:03:31.044179+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-21562b45ef77
    target_state: Archived
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 4f97b1e80afe23eb3b2bc6eae0f230068723c24a0790fc94a157daf0db07965c
    created_at: '2026-08-04T21:03:31.044179+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-04T21:03:31.044179+00:00'
    branch_key: epic-OOMPAH-502
---
## Summary

Problem: after PR #564 was created for epic-OOMPAH-502, review reconciliation reopened Done children OOMPAH-503, OOMPAH-504, and OOMPAH-507 because their implementation commit subjects did not contain the task identifier. Their Oompah-authored completion comments recorded the pre-rebase commit SHAs, and git cherry proves those patches are present on the rebased epic branch. The current _done_review_child_has_epic_branch_work check in oompah/orchestrator.py only searches commit subjects, so a normal epic rebase invalidates otherwise valid child coverage and can dispatch duplicate agents. Implementation: extend shared-epic review coverage to read only trusted Oompah-authored completion comments, extract explicitly reported commit/checkpoint SHAs, and prove exact ancestry or patch equivalence against the current epic review ref with bounded Git commands. When coverage is proven, persist the canonical epic work branch on the child so later reconciliation remains stable after unreachable objects are pruned. Do not accept arbitrary human-comment hashes and continue to reopen a Done child when no affirmative branch, subject, or verified patch evidence exists. Tests: add regressions in tests/test_epic_strategy.py using a generic-subject commit rebased to a different SHA; cover trusted evidence, untrusted evidence rejection, missing/unverifiable SHAs, durable work-branch persistence, and the existing missing-work reopen path. Run the focused epic strategy suite and the exact-head full branch gate. Acceptance criteria: rebased patch-equivalent child work remains Done, no duplicate agent is dispatched, missing work still reopens, coverage evidence is tracker-neutral and fail-closed, PR #564 remains blocked until the repair and all children are Done.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-28 17:46
---
Claimed by the current Codex session after reproducing the live PR #564 rollback. Held out of dispatch while I implement and validate the repair directly on epic-OOMPAH-502.
---
author: oompah
created: 2026-07-28 17:53
---
Implemented and pushed in commit e654aad1b. Review coverage now reads only Oompah-authored completion commit evidence, proves exact ancestry or git-cherry patch equivalence against the current epic ref, rejects human/unverifiable SHAs, and persists the canonical epic work branch after proof. Live reproducer SHAs 91d6c4344, 85be456eb, and 8e9455a92 each resolve as patch-equivalent to the rebased PR branch. Focused epic suite passed 202 tests; exact-head full suite later passed 12,618 with 7 skipped.
---
author: oompah
created: 2026-07-28 17:54
---
Made epic review coverage rebase-stable with trusted patch-equivalence evidence and durable canonical branch metadata.
---
author: oompah
created: 2026-07-28 18:02
---
Landed in merged epic PR #564 on main.
---
author: oompah
created: 2026-08-04 18:29
---
Queued Archived audit: Aged Merged auto-archive (closed 7 days ago). An auditor will review before the task is retired.
---
author: oompah
created: 2026-08-04 21:03
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
<!-- COMMENTS:END -->
