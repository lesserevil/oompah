---
id: OOMPAH-166
type: epic
status: Merged
priority: 0
title: Standardize epic workflow on shared strategy
parent: null
children:
- OOMPAH-167
- OOMPAH-168
- OOMPAH-169
- OOMPAH-170
- OOMPAH-171
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-13T02:22:52.257643Z'
updated_at: '2026-07-14T10:00:24.579997Z'
work_branch: null
target_branch: null
review_url: https://github.com/lesserevil/oompah/pull/406
review_number: null
merged_at: null
oompah.review_url: https://github.com/lesserevil/oompah/pull/406
---
## Summary

Remove the flat and stacked epic/task-management strategies. Oompah must retain only the shared epic workflow, with no project-level choice exposed in the UI or API. Existing persisted flat/stacked project configuration must migrate safely to shared. Decompose implementation, UI, and documentation work into child tasks; preserve existing shared projects and add regression coverage.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-13 02:23
---
Filed implementation, orchestration, UI, and documentation children. OOMPAH-168 and OOMPAH-169 depend on the configuration simplification; OOMPAH-170 follows the shared-only orchestration change.
---
author: oompah
created: 2026-07-13 02:26
---
Finalized this epic by removing its draft label. Added a dedicated child to remove automatic draft-epic labeling and draft-specific dashboard controls.
---
<!-- COMMENTS:END -->
