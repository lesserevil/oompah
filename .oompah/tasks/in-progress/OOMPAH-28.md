---
id: OOMPAH-28
type: task
status: In Progress
priority: 1
title: Audit native tracker state transitions for 1.0
parent: OOMPAH-27
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-06-22T01:16:55.337471Z'
updated_at: '2026-06-22T01:40:59.682563Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 28d482c7-1dfc-46df-aaa3-f80460c36a33
---
## Summary

Plan: plans/oompah-1.0-release.md#managed-project-workflow-readiness

WHAT TO DO
Audit native tracker state transitions for 1.0 readiness, especially proposed, backlog, open, in progress, done, in review, merged, archived, decomposed, awaiting owner, and awaiting requestor.

HOW TO VERIFY
Document any release-blocking gaps as follow-up tasks or fix them before marking this task done.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-22 01:35
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-06-22 01:35
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-06-22 01:36
---
Understanding: This task asks for an audit of native tracker state transitions for 1.0 readiness, covering proposed, backlog, open, in progress, done, in review, merged, archived, decomposed, awaiting owner, and awaiting requestor. Duplicate investigation complete — no duplicate exists. All other tasks in OOMPAH-27's epic (OOMPAH-29, 30, 31) depend on this one finishing first. Proceeding with the audit by examining the state machine code, allowed transitions, and any missing or incorrect guard logic.
---
author: oompah
created: 2026-06-22 01:40
---
Discovery: Completed the audit of native tracker state transitions. Key findings:

1. All 14 canonical statuses (Proposed, Backlog, Open, In Progress, Needs Answer, Needs Human, Needs CI Fix, Needs Rebase, In Review, Decomposed, Duplicate Candidate, Done, Merged, Archived) have correct _STATUS_DIRS mappings in oompah_md_tracker.py.

2. 'awaiting owner' and 'awaiting requestor' from the task description are NOT separate tracker statuses — they are intake metadata sub-states within the Proposed status (tracked via oompah.intake field). No gap here.

3. The transition gate (Proposed→Backlog, {Proposed,Backlog}→Open) correctly applies to BOTH GitHub Issues AND native oompah_md tracker via the API layer.

4. RELEASE-BLOCKING GAP: test_oompah_md_tracker.py has zero coverage for: Proposed, In Review, Merged, Archived, Decomposed, Duplicate Candidate, Needs Answer, and Needs Human statuses. There are no tests verifying that task files move to the correct directory for any status beyond Backlog/Open/In-Progress/Done. This needs to be fixed before 1.0.

5. No guard prevents re-transitioning from terminal states (Done/Merged/Archived) back to non-terminal states in the native tracker — this is intentional (to allow un-archiving) but should be tested.

Fix: Adding comprehensive status transition tests to test_oompah_md_tracker.py.
---
<!-- COMMENTS:END -->
