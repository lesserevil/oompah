---
id: OOMPAH-28
type: task
status: Done
priority: 1
title: Audit native tracker state transitions for 1.0
parent: OOMPAH-27
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-06-22T01:16:55.337471Z'
updated_at: '2026-06-22T01:53:03.977172Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 28d482c7-1dfc-46df-aaa3-f80460c36a33
oompah.task_costs:
  total_input_tokens: 112
  total_output_tokens: 3296
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 112
      output_tokens: 3296
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 112
    output_tokens: 3296
    cost_usd: 0.0
    recorded_at: '2026-06-22T01:53:01.209978+00:00'
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
author: oompah
created: 2026-06-22 01:52
---
Implementation: Added 62 new tests to tests/test_oompah_md_tracker.py covering the complete native tracker status transition matrix:

- TestOompahMarkdownTrackerAllStatusDirectories: Parametrized over all 14 canonical statuses. Tests initial creation, update-and-move, and read-back for every status → directory mapping.
- TestOompahMarkdownTrackerFullLifecycle: Proposed → Backlog → Open → In Progress → In Review → Merged end-to-end; archive-from-any-state; terminal state re-transition.
- TestOompahMarkdownTrackerProposedStatus: Proposed tasks excluded from dispatch, visible in fetch_all/fetch_by_states.
- TestOompahMarkdownTrackerDecomposedAndDuplicateStatuses: Decomposed and Duplicate Candidate excluded from dispatch.
- TestOompahMarkdownTrackerWaitingStatuses: Needs Answer (awaiting requestor) and Needs Human (awaiting owner) directory, dispatch exclusion, mark_needs_human, and re-transition back to In Progress/Open.
- TestOompahMarkdownTrackerReviewPipelineStatuses: In Review, Needs CI Fix, Needs Rebase directory, and full review pipeline walk-through.

All 77 tests in the file pass (15 pre-existing + 62 new).
---
author: oompah
created: 2026-06-22 01:52
---
Completion: Native tracker state transition audit complete for 1.0.

FINDINGS SUMMARY:
1. All 14 canonical statuses (Proposed, Backlog, Open, In Progress, Needs Answer, Needs Human, Needs CI Fix, Needs Rebase, In Review, Decomposed, Duplicate Candidate, Done, Merged, Archived) have correct on-disk directory mappings in _STATUS_DIRS. No gaps.
2. 'Awaiting owner' / 'awaiting requestor' from the task description are intake metadata sub-states of Proposed (oompah.intake field), not separate tracker statuses. Design is correct.
3. Transition gate (Proposed→Backlog, {Proposed,Backlog}→Open) applies to both GitHub Issues and native oompah_md tracker via the API layer.
4. Terminal state re-transition is intentionally allowed (un-archiving/re-opening).

WHAT WAS FIXED:
Added 62 new tests to tests/test_oompah_md_tracker.py covering the full status transition matrix. All 77 tests in the file pass.

NO RELEASE-BLOCKING GAPS FOUND. The test coverage gap was the only release-blocking issue, and it has been resolved.
---
author: oompah
created: 2026-06-22 01:52
---
Audited all 14 canonical native tracker state transitions. All _STATUS_DIRS mappings are correct. Transition gate applies to both GitHub Issues and native oompah_md tracker. Terminal re-transition is intentionally allowed. Added 62 new tests covering the full status matrix — all 77 tests in test_oompah_md_tracker.py pass. No release-blocking gaps found.
---
author: oompah
created: 2026-06-22 01:53
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 0, Tool calls: 71
- Tokens: 112 in / 3.3K out [3.4K total]
- Cost: $0.0000
- Exit: terminated, Duration: 17m 15s
- Log: OOMPAH-28__20260622T013552Z.jsonl
---
<!-- COMMENTS:END -->
