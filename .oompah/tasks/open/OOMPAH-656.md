---
id: OOMPAH-656
type: task
status: Open
priority: null
title: Rebase epic-OOMPAH-619 onto main
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-31T10:41:57.043640Z'
updated_at: '2026-07-31T10:42:03.827746Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 0cbfaf6fd7ca2a2039c78db44944fbad9d8b962f0a0fd574d2a5afe200b4658f
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: a4246b70-e94c-4737-beb0-36462dc436ff
  claim_owner: f6d86559-4e9d-42bf-ac66-416781dbb14f
  claimed_at: '2026-07-31T10:42:02.984723+00:00'
  claim_expires_at: '2026-07-31T11:12:02.984723+00:00'
  retry_count: 0
  retry_after: null
---
## Summary

Explicit operator-required base repair for active epic OOMPAH-619. The remote epic branch is at 0dc7d0f7caeea06a6eceb55ea2e58cf16554f0a4 and origin/main is at or after ec0ec7d89fb8804571fcf7e780558e6d979b73ea, which contains merged OOMPAH-652 test-lifecycle isolation. Preserved child branches OOMPAH-623 and OOMPAH-650 must not resume or run gates until their shared base contains that safety prerequisite. Work directly on epic-OOMPAH-619; do not create a feature branch or PR. Fetch origin, validate the expected old remote head, rebase the epic's accepted OOMPAH-620/621/624 commits onto current origin/main, resolve conflicts without dropping accepted scope, verify origin/main is an ancestor and the epic-only diff still contains the three intended child changes, then publish with exact git push --force-with-lease against the observed old remote head. Do not alter or delete child branches. Acceptance: origin/epic-OOMPAH-619 contains current main/OOMPAH-652, accepted epic commits are preserved, no unrelated commits are added, the direct epic worktree is clean, and the task records old/new SHAs plus topology evidence. No full test is required for a topology-only rebase; do not execute candidate gates before the safety base is present.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

