---
id: OOMPAH-401
type: task
status: Merged
priority: null
title: Preserve structured Markdown descriptions in native tasks
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-22T05:18:51.142416Z'
updated_at: '2026-07-26T00:28:06.098683Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Prevent native Markdown task creation from storing a non-empty structured Markdown description that the tracker later parses as empty. Normalize H1/H2 headings before embedding descriptions in the Summary section, validate the resulting parsed description, and add regression tests. Repair OOMPAH-308 through OOMPAH-313 so their existing structured content remains intact and their parsed descriptions are non-empty. Acceptance: structured Markdown task creation yields a non-empty API description; blank normalized descriptions are rejected; the six affected tasks are repaired through the task API; relevant tests pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-22 05:22
---
Implemented and verified: native task creation and description updates now demote H1/H2 headings before embedding them in Summary, preventing structured Markdown from parsing as an empty description. The API now rejects promotion to a dispatchable status when the normalized description is empty. Repaired OOMPAH-308 through OOMPAH-313 via the task API; each now exposes a non-empty parsed description. make test passed.
---
author: oompah
created: 2026-07-22 05:22
---
Implemented native structured-description safeguards, repaired the six affected tasks, and passed make test.
---
author: oompah
created: 2026-07-26 00:28
---
Delivery reconciled: structured native task description preservation and validation is present on origin/main in commit dcbef393e. This task was Done rather than waiting for an agent; it is now being aligned with the delivered repository state.
---
<!-- COMMENTS:END -->
