---
id: OOMPAH-248
type: task
status: Backlog
priority: null
title: Fix Release Delivery discovery when merged task branches were deleted
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-19T18:24:37.584983Z'
updated_at: '2026-07-19T18:24:37.584983Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Problem

The Release Delivery backlog for Trickle release/0.11 currently returns zero primary items while reporting 7,513 unassociated commits, despite main being ahead and containing substantive task work. OOMPAH-237/OOMPAH-238 added tracker-sourced discovery, but it resolves a Merged issue only by running git rev-list against refs/remotes/origin/<work_branch>. Oompah normally deletes the task branch after its PR merges, so that ref is absent and the candidate is silently excluded.

Required implementation

- Replace work-branch existence as the primary proof with durable native tracker merge evidence: merged PR number/head+merge SHA, recorded merge commit SHA, or another persisted merge-to-default-branch field available after branch deletion.
- Resolve every resulting source commit set against origin/<default_branch>; include only commits that are reachable there.
- Retain work-branch history only as an optional enrichment/fallback when the ref still exists; missing/deleted branch must not exclude a genuinely merged task or epic.
- Keep release-delivery ledger and selected-release ancestry solely for delivery state, not candidate eligibility.
- Ensure the endpoint can return primary candidates before (or independently of) unassociated diagnostics.

Tests

- Unit regression: a Merged task with no ledger entry, a deleted/missing work_branch ref, and a persisted merge commit reachable from main appears once as Not selected.
- Unit regression: same task with a merge SHA not reachable from main is excluded.
- Unit regression: optional live work branch can add associated commits without being required.
- API/fixture regression representing Trickle release/0.11 demonstrates a selectable primary candidate after the task branch has been deleted.

Acceptance criteria

- Release Delivery for Trickle release/0.11 shows eligible merged task/epic changes that have never been queued, even if their original work branches no longer exist.
- An empty primary list is not returned merely because merged task branches were cleaned up.
- make test passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

