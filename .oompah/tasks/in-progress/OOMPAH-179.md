---
id: OOMPAH-179
type: task
status: In Progress
priority: 2
title: Reconcile release-addendum pull-request outcomes and controls
parent: OOMPAH-172
children: []
blocked_by:
- OOMPAH-178
labels: []
assignee: null
created_at: '2026-07-13T02:35:55.903478Z'
updated_at: '2026-07-13T05:20:34.420800Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: f666b1cb-d09b-4d75-9975-0a1875b8abb4
---
## Summary

Read sections 6 and 8 of plans/release-branch-addendums.md. Add PR polling that changes an in_review addendum to merged only after its target PR is merged and records completion evidence. A closed-unmerged PR must remain nonterminal until explicit retry; retry may change blocked or closed-unmerged in_review to open without changing commits. Add archive support for open/blocked only. Implement the retry/archive API endpoints, transition validation, cache invalidation, and oompah-authored source-task comments for state changes and errors. Tests: merged/open/closed PR outcomes; retry and archive authorization/transition errors; immutable snapshots across retries; duplicate poll idempotency; and comments. Acceptance: lifecycle controls are explicit and no replacement PR is opened automatically after a close.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-13 05:19
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-13 05:19
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-13 05:20
---
Understanding: OOMPAH-179 is NOT a duplicate. Searched all 13 OOMPAH-172 epic children and other tasks. No other task covers PR polling (in_review→merged on PR merge, closed-unmerged handling), retry/archive API endpoints, or lifecycle controls. OOMPAH-178 covers execution (creating PRs), OOMPAH-177 covers queue claiming. OOMPAH-179 covers what happens AFTER a PR is created: polling its outcome, explicit retry/archive controls, and oompah-authored source-task comments for all state changes. Proceeding with implementation.
---
<!-- COMMENTS:END -->
