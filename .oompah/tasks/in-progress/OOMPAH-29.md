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
updated_at: '2026-06-22T01:58:11.127903Z'
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
author: oompah
created: 2026-06-22 01:58
---
Discovery: Audited github_intake_bridge.py and tests/test_github_intake_bridge.py. All three reconciliation cases are implemented correctly in the code. Coverage gaps found:\n\n1. OPEN (case 1): Both polling and webhook paths covered. No gap.\n2. CLOSED (case 2): Polling + webhook archive tested, terminal-state idempotency tested for MERGED. Missing: (a) closed external issue with NO existing native task (should create nothing), (b) closed external issue when native task is already ARCHIVED (idempotent).\n3. REOPENED (case 3): Polling path covered by test_reopened_github_issue_moves_externally_archived_task_to_proposed. Missing: (a) webhook issues.reopened event on existing archived task, (b) webhook issues.reopened with no prior native task (intake flow creates new task).\n\nWill add 4 tests to close these gaps.
---
<!-- COMMENTS:END -->
