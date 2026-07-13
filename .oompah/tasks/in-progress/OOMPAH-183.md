---
id: OOMPAH-183
type: task
status: In Progress
priority: 1
title: Migrate release picks and retire child-backport workflow
parent: OOMPAH-172
children: []
blocked_by:
- OOMPAH-179
- OOMPAH-180
- OOMPAH-181
- OOMPAH-182
labels: []
assignee: null
created_at: '2026-07-13T02:36:21.418119Z'
updated_at: '2026-07-13T06:19:27.313596Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 08b3f464-6398-4774-8498-aa8ae198c1d8
---
## Summary

Read sections 3 and 9 of plans/release-branch-addendums.md. Implement an idempotent migration from oompah.backports and child oompah.backport_of records to source-owned oompah.release_addendums. Apply the documented status mapping, preserve commits/PR URLs/timestamps where available, and archive historical child tasks with an oompah-authored redirect comment. Deploy read support and migration before disabling the old reconciler; then remove child creation, old metadata writes, legacy matrix/apply-all UI, and obsolete routes using the documented 410 compatibility period. Tests: every legacy status mapping; child evidence preservation; rerun safety; mixed migrated/new data; child archive behavior; and no new child task after cutover. Acceptance: existing release picks remain visible and actionable after migration, and new approvals never create child backport tasks.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-13 06:19
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-13 06:19
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-13 06:19
---
Understanding: I am a Duplicate Investigator agent assigned to OOMPAH-183 ('Migrate release picks and retire child-backport workflow'). My first task is to determine if this is a duplicate of an existing issue before any implementation begins. I will search for similar tasks using keywords like 'release picks', 'backport migration', 'child-backport', 'release_addendums', and 'backports' to find candidate duplicates. I will read the plans/release-branch-addendums.md sections 3 and 9, and inspect the .oompah/tasks directory to identify any overlapping issues.
---
<!-- COMMENTS:END -->
