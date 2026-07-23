---
id: OOMPAH-312
type: task
status: In Progress
priority: null
title: 'UI/dashboard: show child completion status in epic branch context (Done on
  branch vs Merged to target)'
parent: OOMPAH-307
children: []
blocked_by:
- OOMPAH-310
labels:
- focus-complete:duplicate_detector
assignee: null
created_at: '2026-07-21T16:54:16.661153Z'
updated_at: '2026-07-23T00:12:02.618722Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 5fa31ec0-21bc-42c3-a64f-c8089592dbbb
oompah.task_costs:
  total_input_tokens: 100583
  total_output_tokens: 10028
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 100583
      output_tokens: 10028
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 29
    output_tokens: 8880
    cost_usd: 0.0
    recorded_at: '2026-07-23T00:07:14.286776+00:00'
  - profile: default
    model: unknown
    input_tokens: 100554
    output_tokens: 1148
    cost_usd: 0.0
    recorded_at: '2026-07-23T00:07:57.029558+00:00'
---
## Summary

Show shared-epic child completion on the epic branch separately from merge-to-target status.
## Context

The current _effective_display_status function in oompah/server.py returns the canonical tracker state for shared-epic children. When a child is Done (complete on the epic branch) but the epic has not yet merged, the UI shows 'Done' with no indication that the work is sitting on the epic branch awaiting the epic merge. This is confusing for operators who see 'Done' but the code isn't in the target branch yet.

The _effective_display_status function (tests in tests/test_shared_epic_display_status.py) was recently simplified to always return the tracker state. We need to verify the displayed state correctly communicates to operators:
1. When child is Done and epic is not merged: 'Done (on epic branch)'
2. When child is Merged (after epic merge to target): 'Merged'
3. When child had an independent merge (reconciliation case): 'Done (reconciled - independent merge)'

## Implementation scope

1. In oompah/server.py _effective_display_status (or its caller): when a child's tracker state is Done AND the parent epic is not yet merged, return an annotated display label or add badge data (epic_branch_pending: true) to the task detail/card response.

2. In the dashboard task card template (oompah/static/ or oompah/templates/): show a visual indicator when a child is Done-on-epic-branch (awaiting epic merge). This can be a badge like 'On epic branch' shown alongside the Done status.

3. In the CLI/API (oompah/task_cli.py, oompah/server.py /api/v1/issues endpoint): include a parent_epic_branch field in the issue API response for shared-epic children.

4. In the release association views: do not include children with Done-on-epic-branch state in the 'released' release listing until the epic is merged.

## Relevant files
- oompah/server.py: _effective_display_status, issue detail API endpoint
- oompah/static/ or templates: task card, issue detail view
- oompah/task_cli.py: oompah task view output
- tests/test_shared_epic_display_status.py: existing display status tests

## Tests required
- test_shared_epic_display_status.py: Add case where child is Done and epic is not merged → display annotates with epic-branch context
- Test that CLI output for a Done shared-epic child shows the parent epic branch
- Test that the API response includes parent_epic_branch for shared-epic children

## Acceptance criteria
- Dashboard and detail views clearly distinguish 'Done on epic branch (awaiting epic merge)' from 'Done (standalone task complete)'
- CLI and API expose the parent epic branch for shared-epic children
- No child is shown as Merged in release views before the epic is confirmed merged

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-23 00:03
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-23 00:03
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-23 00:04
---
Understanding: Investigating OOMPAH-312 as Duplicate Investigator. This task asks for the UI/dashboard to show child completion status in an epic branch context, distinguishing 'Done on branch' vs 'Merged to target'. Blocked by OOMPAH-310. I will search for similar tasks to determine if this is a duplicate before any implementation work begins.
---
author: oompah
created: 2026-07-23 00:06
---
Discovery: Duplicate screening found NO duplicate for OOMPAH-312.

Search scope: All .oompah/tasks/ folders (archived, merged, done, open, backlog), plans/, docs/, README.md, WORKFLOW.md. CLI queries for OOMPAH-310, OOMPAH-311, OOMPAH-307, OOMPAH-412, OOMPAH-413.

Keywords searched: dashboard, UI, child completion, epic branch context, Done on branch, Merged to target, shared-epic, status display, child status, display status, effective_display_status.

Candidates reviewed and REJECTED as duplicates:
- OOMPAH-307 (Open): Parent epic for shared-epic child routing. OOMPAH-312 was explicitly created as P3 child of OOMPAH-307 ('UI/dashboard: show Done-on-epic-branch vs Merged-to-target status [depends on 310]'). Not a duplicate — it is the parent.
- OOMPAH-310 (Done): 'Verify and harden epic-merge-triggered Merged promotion for shared-epic children' — different; covers backend Merged promotion logic/guards. OOMPAH-310's own investigator confirmed OOMPAH-312 is distinct ('covers display labels, not Merged promotion logic').
- OOMPAH-311 (Done): 'Diagnose and surface remediation path for existing independently-merged child branches/PRs' — different; covers detection/annotation of already-merged children. OOMPAH-311's own investigator confirmed OOMPAH-312 is distinct ('covers display labels, not remediation').
- OOMPAH-412 (Done): Audit and harden shared-epic Merged promotion paths — backend-only; OOMPAH-412 investigator also confirmed OOMPAH-312 is distinct ('display labels').
- OOMPAH-413 (Done): Regression tests for promotion gates — test-only, not UI display.
- OOMPAH-313 (Done): Routing fixture and native lifecycle regression tests — different scope.

Current code state: oompah/server.py _effective_display_status() (line 1277) currently just returns issue.state — no differentiation between 'Done on epic branch' and 'Merged to target'. The test file tests/test_shared_epic_display_status.py (107 lines) documents that the old epic-worktree-file-reading approach was retired; the new approach (canonical tracker state) does not yet surface the 'Done on branch' vs 'Merged to target' UI distinction OOMPAH-312 requires.

OOMPAH-307 acceptance criterion explicitly states: 'UI status explains whether a child is complete on the epic branch versus merged to target.'

Conclusion: OOMPAH-312 is NOT a duplicate. It is a unique, unimplemented UI/dashboard task that needs to display child completion status in the epic branch context. Blocker OOMPAH-310 is now Done, so the task is unblocked.
---
author: oompah
created: 2026-07-23 00:07
---
Focus handoff: duplicate_detector

1. **Outcome**: No duplicate found. OOMPAH-312 is a unique, unimplemented UI/dashboard task. All prior investigators across OOMPAH-310, OOMPAH-311, OOMPAH-412, OOMPAH-413 independently confirmed OOMPAH-312 is distinct from their respective tasks.

2. **Relevant files, commands, evidence, and decisions**:
   - OOMPAH-307 (parent epic) comment #15: explicitly created OOMPAH-312 as 'P3: UI/dashboard: show Done-on-epic-branch vs Merged-to-target status [depends on 310]'. This is the definitive scope definition.
   - OOMPAH-307 acceptance criteria: 'UI status explains whether a child is complete on the epic branch versus merged to target.'
   - `oompah/server.py` line 1277: `_effective_display_status()` currently just returns `issue.state` — no differentiation between Done-on-branch vs Merged-to-target.
   - `tests/test_shared_epic_display_status.py` (107 lines): Existing tests confirm the old epic-worktree-file-reading approach was already retired; the new canonical tracker state approach does NOT yet surface the Done/Merged distinction.
   - `oompah/templates/dashboard.html`: Dashboard UI to add/modify display labels/badges for epic children.
   - Blocker OOMPAH-310 is Done (including children OOMPAH-412 and OOMPAH-413). OOMPAH-312 is unblocked.

3. **Remaining work**:
   - Implement a UI distinction in the dashboard that shows 'Done on branch' for shared-epic children who are Done but whose parent epic has not yet merged to target.
   - Show 'Merged to target' when the parent epic has merged and children have transitioned to Merged state.
   - Possible approaches: (a) add a visual badge/label in the dashboard card for epic children showing branch completion context; (b) extend `_effective_display_status()` or add a new helper to return an augmented status string for display; (c) add a new API field (e.g., `display_status_context`) to the card/issue API response and render it in dashboard.html.
   - Update or extend `tests/test_shared_epic_display_status.py` with tests for the new display logic.
   - Run `make test` before committing.

4. **Risks**:
   - The `_effective_display_status()` function was recently simplified to return `issue.state` directly. Any re-introduction of complexity needs to be deliberate and avoid regression of the existing tests in `test_shared_epic_display_status.py`.
   - Dashboard changes should be scoped to displaying context labels, not changing the canonical state.
   - The definition of 'Done on branch' needs careful interpretation: a child with state 'Done' whose parent epic is not yet in MERGED state. The `_project_epic_strategy()` check may be needed (only for shared strategy). 

5. **Recommended next focus**: `frontend` — implement the dashboard UI changes and extend tests.
---
author: oompah
created: 2026-07-23 00:07
---
Agent completed successfully in 197s (8909 tokens)
---
author: oompah
created: 2026-07-23 00:07
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 67, Tool calls: 41
- Tokens: 29 in / 8.9K out [8.9K total]
- Cost: $0.0000
- Exit: normal, Duration: 3m 17s
- Log: OOMPAH-312__20260723T000359Z.jsonl
---
author: oompah
created: 2026-07-23 00:07
---
Focus handoff from `duplicate_detector` is complete. Queued a fresh agent run for the next applicable focus. The next agent should begin with the preceding Focus handoff comment.
---
author: oompah
created: 2026-07-23 00:07
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-23 00:07
---
Focus: Frontend Developer
---
author: oompah
created: 2026-07-23 00:07
---
Agent completed successfully in 34s (101702 tokens)
---
author: oompah
created: 2026-07-23 00:07
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/default]
- Turns: 1, Tool calls: 2
- Tokens: 100.6K in / 1.1K out [101.7K total]
- Cost: $0.0000
- Exit: normal, Duration: 34s
- Log: OOMPAH-312__20260723T000725Z.jsonl
---
author: oompah
created: 2026-07-23 00:07
---
Agent completed without closing this issue (34s (101702 tokens)). Escalating from 'default' to 'standard'. Retrying in 10s (1/3).
---
author: oompah
created: 2026-07-23 00:08
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-23 00:08
---
Focus: Frontend Developer
---
author: oompah
created: 2026-07-23 00:12
---
Understanding: Implementing UI/dashboard epic child completion context badges.

Key findings:
- _effective_display_status() already returns canonical tracker state (no change needed)
- _project_epic_strategy() always returns 'shared' (OOMPAH-167 removed flat/stacked) — all projects are shared-epic
- The distinction is already in the canonical state: 'Done' = done on epic branch, 'Merged' = merged to target
- The serialized board entry and detail panel children data need a new 'display_status_context' field

Plan:
1. Add _child_display_context(issue) helper that returns 'done_on_branch'/'merged_to_target'/None based on parent_id and canonical state
2. Add 'display_status_context' to the board serialization in _fetch_and_serialize_issues()  
3. Add 'display_status_context' to children in api_issue_full_detail()
4. Add CSS for .branch-context-badge, .branch-context-done, .branch-context-merged
5. Render badge on kanban cards and in detail panel children list
6. Extend tests/test_shared_epic_display_status.py with _child_display_context tests
---
<!-- COMMENTS:END -->
