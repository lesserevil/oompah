---
id: OOMPAH-697
type: bug
status: Open
priority: 1
title: Requeue branches that advance after their recorded review merges
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-02T16:21:00.027506Z'
updated_at: '2026-08-02T16:21:47.181024Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 3d4dcd1225d01ef9a3fa6c3277b48ee6432c055f7096368737892a5afa9b5bf8
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: c64df9cb-e0d1-4521-ac31-dfff8a0115aa
  claim_owner: 8ed25388-a2c2-4d5e-b302-5705d6f379a6
  claimed_at: '2026-08-02T16:21:38.795718+00:00'
  claim_expires_at: '2026-08-02T16:51:38.795718+00:00'
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 786244c4-3519-4523-887c-92983dee0d6a
---
## Summary

Triggered by: OOMPAH-680

Observed production failure on OOMPAH-680 and OOMPAH-682: each task is shown as In Review while the live review cache and forge report zero open reviews. PR #643 and PR #645 merged successfully, but each task branch later advanced by one commit (OOMPAH-680 head d08a8da59; OOMPAH-682 head 71f87859f). Neither current head is an ancestor of main and neither has a new PR. The task metadata retained the obsolete merged review, so reconciliation routed the newer branch generation to In Review instead of running the normal exact-head gate and opening a fresh review.

Implementation scope:
- In standalone review creation and _reconcile_stale_in_review_tasks, bind review evidence to the exact source branch head/generation it reviewed, not only branch name or persisted review_url/review_number.
- Treat a recorded review that is merged or closed at an older head as historical evidence, never as an active review for a newer branch head.
- When the current remote branch is ahead of the reviewed/merged head and not contained in the target branch, clear or supersede active review metadata, restore the task to Ready to Integrate, run the exact-head branch quality gate, and create a new PR/MR through the normal capacity-controlled path.
- Ensure reviews_summary/open_reviews_by_project and the In Review task state agree: a task may remain In Review only when the forge has a currently open review covering its current submitted head.
- Preserve old review history for auditability, handle webhook/poll races idempotently, and avoid duplicate PR creation when a current-head review already exists.

Relevant code: oompah/orchestrator.py _ensure_review_exists, _reconcile_stale_in_review_tasks, standalone Ready-to-Integrate delivery/review metadata persistence, forge review lookup helpers, and tests/test_orchestrator_merged.py plus review/quality-gate tests.

Required tests:
- Reproduce OOMPAH-680: old PR merged, branch advances one commit, stale review metadata exists; reconciliation returns the task to integration, gates the new SHA, opens one new review, and refreshes active review metadata.
- Reproduce OOMPAH-682 with recovery/resubmission metadata and prove the same outcome.
- A merged review whose reviewed head is already in main remains terminal and does not reopen.
- An open review at the exact current head remains In Review and no duplicate is created.
- Closed-unmerged, merged-old-head, webhook-lag, restart, and concurrent reconciliation paths remain idempotent.
- Dashboard review counts and task lifecycle cannot disagree after reconciliation.

Acceptance criteria:
- OOMPAH-680 and OOMPAH-682 cannot remain In Review with zero active forge reviews while their current heads are unmerged.
- Every post-merge branch advance receives fresh exact-head gate evidence and a new review before it can return to In Review.
- Stale merged review metadata cannot strand future branch generations or cause duplicate reviews.
- Focused review/reconciliation tests and the complete Makefile gate pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-02 16:21
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-02 16:21
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
