---
id: OOMPAH-784
type: task
status: Open
priority: 1
title: Add workflow liveness SLO metrics and evidence-backed recovery health
parent: OOMPAH-770
children: []
blocked_by: []
start_blocked_by: &id001
- OOMPAH-796
labels: []
assignee: null
created_at: '2026-08-04T13:59:04.299718Z'
updated_at: '2026-08-06T03:19:39.067085Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.start_blocked_by: *id001
---
## Summary

Instrument time-to-owner/explanation for Open, Ready, In Validation, In Review, recovery, and post-restart reconstruction. Track decision age, reassessment lateness, lease/retry deadlines, recoveries, escalations, and unexplained divergences with bounded cardinality. Add health thresholds via OOMPAH_* .env configuration and expose project/global summaries. Required tests: fake-clock boundaries, resets on progress, no false overdue during active jobs, restart timestamp handling, cardinality bounds, and health/alert integration. Acceptance: configured SLO violations are measurable and attributable; healthy means every nonterminal task satisfies the liveness invariant, not merely that the server loop responds.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-06 03:19
---
Promoted from Backlog to Open after hard-start prerequisite OOMPAH-796 reached Done. Project is temporarily paused for the graceful cutover; dispatch normally on resume.
---
<!-- COMMENTS:END -->
