---
id: OOMPAH-519
type: task
status: Backlog
priority: null
title: Recognize rebased child commits in epic review coverage
parent: OOMPAH-502
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-28T17:46:48.581634Z'
updated_at: '2026-07-28T17:53:53.995569Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
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
<!-- COMMENTS:END -->
