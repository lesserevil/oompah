---
id: OOMPAH-235
type: task
status: Done
priority: null
title: Recover native tracker writes after concurrent default-branch advancement
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-18T22:26:05.196480Z'
updated_at: '2026-07-18T22:28:00.056535Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Implement the native Markdown tracker write path so concurrent tracker commits and remote default-branch advances do not fail user updates.

Scope:
- Keep the current fetch + fast-forward path for clean checkouts.
- When the checkout has local tracker commits and origin/default branch has advanced, rebase the local commits onto the fetched remote branch, then continue the write/push flow.
- On a non-overlapping push rejection, fetch, rebase, and retry once.
- If a rebase conflicts, abort it, preserve the checkout state, and raise a precise TrackerError with remediation; never use reset --hard.
- Preserve unrelated dirty working-tree changes with autostash or an equivalent safe mechanism.

Tests:
- Add unit tests for pre-write divergence recovery, push-race recovery, and failed-rebase cleanup/remediation.
- Preserve existing clean-checkout fast-forward behavior.

Acceptance criteria:
- A local task-metadata commit plus a remote PR merge can be reconciled and pushed without a UI update failure.
- No local tracker commit or unrelated working-tree edit is lost.
- Conflicts leave no rebase in progress and give an actionable error.
- Relevant tests and make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-18 22:27
---
Implemented and pushed in fdd61e4a. Native tracker sync now retries divergent default-branch writes with git rebase --autostash origin/<branch>, preserving unrelated working-tree edits. Failed rebases abort safely and report remediation; the reset --hard fallback was removed. Regression tests cover successful recovery, push-race recovery, and conflict preservation. make test passed (9,274 tests).
---
<!-- COMMENTS:END -->
