---
id: OOMPAH-163
type: bug
status: Open
priority: 1
title: Allow generated epic target branches through dispatch
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-10T17:20:29.690205Z'
updated_at: '2026-07-10T17:23:12.539923Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 5b828242-41fa-40cf-a89f-f98f75667e8a
---
## Summary

Stacked/shared child tasks can carry oompah-generated target branches like epic-COROOT-5. The generic target_branch validator currently rejects those branches when a project only tracks main, so Needs CI Fix and Needs Rebase child tasks are considered but never receive agents. Oompah-owned epic branches should bypass the configured branch allowlist when the target matches epic-<parent_id>.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-10 17:21
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-07-10 17:21
---
Focus: CI Failure Fixer
---
<!-- COMMENTS:END -->
