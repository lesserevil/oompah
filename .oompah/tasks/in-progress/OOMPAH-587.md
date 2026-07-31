---
id: OOMPAH-587
type: epic
status: In Progress
priority: 1
title: Drain integration queues and prevent stranded delivery states
parent: OOMPAH-584
children:
- OOMPAH-596
- OOMPAH-597
- OOMPAH-598
- OOMPAH-599
- OOMPAH-617
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-30T14:13:38.093049Z'
updated_at: '2026-07-31T01:00:15.310889Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Goal

Recover the current OOMPAH-460 integration chain and eliminate silent stranded Ready to Integrate or In Validation states. Conflict repair, standalone delivery, terminal verification, and epic closure must progress automatically or surface an explicit human-action state.

Relevant context

OOMPAH-484 and OOMPAH-487 have real rebase conflicts and no active repair worker; OOMPAH-485, OOMPAH-488, and OOMPAH-489 wait downstream. OOMPAH-574, OOMPAH-575, OOMPAH-576, and OOMPAH-581 are standalone Ready to Integrate work with no open PRs.

Acceptance criteria

Blocked conflict repairs can be rearmed after recoverable infrastructure/auth failures; exhausted repairs become explicit actionable states; every standalone Ready task obtains a valid delivery path or an alert; current work drains in dependency order; terminal audits finish; OOMPAH-460 closes; no review-ready work remains invisible.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-30 14:18
---
Project-owner-approved green recovery work; dispatch under recorded dependencies and acceptance criteria.
---
author: oompah
created: 2026-07-31 01:00
---
Operator recovery for the live nested-epic queue deadlock: rebased origin/epic-OOMPAH-587 from a678afc20 onto current parent origin/epic-OOMPAH-584 d62dd4cff and force-pushed with an exact lease at 8a875b1c3. Resolved the OOMPAH-576 overlap with later OOMPAH-629 by preserving the refined expected-branch validation, wrong-worktree no-reset fence, and ProjectStore pre-reset branch identity check. Focused conflict-repair/integration/project/task-handoff/worker/parallel queue verification: 181 passed; terminal mutation scan passed.
---
<!-- COMMENTS:END -->
