---
id: OOMPAH-29
type: task
status: In Progress
priority: 1
title: Audit GitHub Issues intake reconciliation
parent: OOMPAH-27
children: []
blocked_by:
- OOMPAH-28
labels: []
assignee: null
created_at: '2026-06-22T01:16:57.697390Z'
updated_at: '2026-06-22T01:54:15.028913Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 8ee160c1-e233-4efa-b994-94c3c72e9f0d
---
## Summary

Plan: plans/oompah-1.0-release.md#managed-project-workflow-readiness

WHAT TO DO
Audit GitHub Issues intake reconciliation for open, closed, and reopened external issues.

EXPECTED BEHAVIOR
- Open external issue without an internal task creates an internal proposed task.
- Closed external issue archives a non-terminal internal task.
- Reopened external issue returns the internal task to proposed and runs the normal intake flow.

HOW TO VERIFY
Tests or documented manual checks cover all three cases.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-22 01:53
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-06-22 01:53
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-06-22 01:54
---
Understanding: OOMPAH-29 is NOT a duplicate. Duplicate investigation complete — no existing task covers this specific scope. Sibling OOMPAH-28 covered native tracker state transitions; OOMPAH-29 is specifically about GitHub Issues intake reconciliation for the three external-issue state changes: open (creates internal Proposed task), closed (archives non-terminal internal task), reopened (returns to Proposed and re-runs intake flow). Proceeding with audit of github_intake_bridge.py and related code to verify all three cases are handled and tested.
---
<!-- COMMENTS:END -->
