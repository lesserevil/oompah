---
id: OOMPAH-820
type: bug
status: In Progress
priority: 1
title: Bootstrap exact-head review-generation fence on main
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels:
- human-only
assignee: null
created_at: '2026-08-05T03:09:46.087231Z'
updated_at: '2026-08-05T03:10:26.713813Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Triggered by: OOMPAH-819

Bootstrap delivery for the live stale-review-generation regression discovered while re-submitting OOMPAH-818. OOMPAH-819 is correctly attached to systemic epic OOMPAH-768 for program accounting, but that nested epic branch cannot repair the currently running main-based integration path needed to land the fix. Implement the OOMPAH-819 exact-head review fence on a standalone branch targeting main first, using the same code/tests: standalone Ready reconciliation must never reuse a merged/closed/open review whose forge head differs from the current accepted oompah.integration head; terminal staging requires exact reviewed-head landing proof; stale review history is preserved; concurrent resubmit/webhook/restart paths are fenced. Required regressions include the exact OOMPAH-818 e3140b65 versus PR #716 old-head sequence and current-head controls. Acceptance: the fix passes focused and configured exact-head gates, deploys to main, and OOMPAH-818 can then be re-submitted to a new gate/review without stale terminalization. After deployment, the same patch may be recorded on OOMPAH-819's epic lineage for program rollup.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

