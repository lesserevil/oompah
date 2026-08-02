---
id: OOMPAH-696
type: bug
status: Backlog
priority: 1
title: Honor integrated SHA evidence after epic child branches are pruned
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-02T16:18:38.337420Z'
updated_at: '2026-08-02T16:18:38.337420Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Triggered by: OOMPAH-691

After epic OOMPAH-691 merged to main, OOMPAH-692 through OOMPAH-695 were moved from audited Done to Needs Human even though every integration.integrated_sha is an ancestor of origin/main. The post-merge child reconciler refreshes missing private branch refs, then _child_landing_evidence_block_reason fails closed solely because child.work_branch differs from the epic branch and the already-landed private branch has been pruned. It ignores the durable integration record, causing a Needs Human/reopen/re-escalate loop and misleading missing-work instructions.

Implementation scope:
- In merged-epic child reconciliation, treat a persisted integration record in state integrated with integrated_sha/head_sha reachable from the authoritative epic container or landed target branch as affirmative landing evidence.
- Check durable commit evidence before requiring a live child branch ref; branch cleanup after successful integration must not invalidate completed work.
- Preserve fail-closed behavior when the recorded SHA is absent, unreachable, or cannot be checked because authoritative target refs are stale/unavailable.
- Keep incomplete Open/In Progress/repair-state children visible and do not promote genuinely stranded commits.
- Suppress repeated Needs Human/watchdog churn once landing is proven, and allow the normal coordinator path to mark the child Merged.
- Review cleanup ordering so integration evidence remains usable after local/remote worktree and branch pruning.

Relevant code: oompah/orchestrator.py _mark_epic_merged, _child_landing_evidence_block_reason, candidate-ref refresh/cleanup helpers, integration queue metadata, and tests/test_epic_strategy.py.

Required tests:
- A Done child with a pruned private branch and integrated_sha contained in the merged epic/main target is promoted rather than moved to Needs Human.
- The exact OOMPAH-692..695 pattern remains idempotently terminal across repeated reconciliation/watchdog passes.
- An integrated_sha not reachable from the container still yields actionable Needs Human recovery instructions.
- Authoritative fetch/transport failure defers reconciliation without asserting success or missing work.
- An incomplete child and a child with genuinely unlanded commits remain non-terminal.

Acceptance criteria:
- Successful branch pruning cannot erase durable landing proof.
- No completed epic child cycles Done -> Needs Human -> Open -> Needs Human solely because its private branch was deleted.
- Existing stranded-work safety tests and the complete Makefile gate pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

