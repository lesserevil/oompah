---
id: OOMPAH-312
type: task
status: Backlog
priority: null
title: 'UI/dashboard: show child completion status in epic branch context (Done on
  branch vs Merged to target)'
parent: OOMPAH-307
children: []
blocked_by:
- OOMPAH-310
labels: []
assignee: null
created_at: '2026-07-21T16:54:16.661153Z'
updated_at: '2026-07-21T16:54:57.442507Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

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

