---
id: OOMPAH-41
type: task
status: In Progress
priority: 1
title: Create and verify the final v1.0.0 release
parent: OOMPAH-37
children: []
blocked_by:
- OOMPAH-40
labels: []
assignee: null
created_at: '2026-06-22T01:17:48.285544Z'
updated_at: '2026-06-22T17:01:59.805283Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: ffc2ecda-23e5-46ea-968d-412e0edfe9e3
---
## Summary

Plan: plans/oompah-1.0-release.md#release-execution-and-verification

WHAT TO DO
Create the immutable v1.0.0 final tag and verify the final GitHub Release.

HOW TO VERIFY
The final tag is not force-moved, the release workflow passes, artifacts install successfully, and release notes identify v1.0.0.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-22 17:01
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-06-22 17:01
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-06-22 17:01
---
UNDERSTANDING: Not a duplicate. OOMPAH-41 is step E4 in the 1.0 release plan (plans/oompah-1.0-release.md). All other release tasks are distinct: OOMPAH-38=E1 (cut branch+quality gate, Done), OOMPAH-39=E2 (v1.0.0-draft release, Done), OOMPAH-40=E3 (fix draft findings+sync to main, Done), OOMPAH-42=E5 (post-release smoke checks, Open). Proceeding with E4 work: create the immutable v1.0.0 final tag from release/1.0 HEAD and verify the final GitHub Release.
---
<!-- COMMENTS:END -->
