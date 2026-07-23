---
id: OOMPAH-423
type: bug
status: Backlog
priority: 2
title: Keep normal epic branch drift out of alerts
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-23T20:25:33.664332Z'
updated_at: '2026-07-23T20:25:33.664332Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Demote policy-compliant epic branch staleness (an unfinished epic behind its target branch) from the Oompah alert stream to informational epic-health state. Preserve actionable alerts for failed rebases, merge-blocking conflicts, credential failures, and human intervention. Add regression tests verifying normal drift does not populate alerts while the staleness state remains observable. Run make test.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

