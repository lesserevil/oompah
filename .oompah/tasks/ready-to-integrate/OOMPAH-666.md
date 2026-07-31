---
id: OOMPAH-666
type: bug
status: Ready to Integrate
priority: 1
title: Fix dashboard vertical scrolling when alerts precede the Kanban board
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-31T21:19:38.816688Z'
updated_at: '2026-07-31T23:45:25.684308Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: c01898d7e202c2aa042354f310604e9ae494bf878078cb88c46a93a66f4bdac1
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-07-31T22:56:58.152902+00:00'
  matched_identifiers: []
  evidence: "Based on my investigation:\n\n**Active tasks (non-terminal states \u2014\
    \ Open, In Progress, In Review, Backlog):**\n- **OOMPAH-281** (Open): \"Run Oompah\
    \ CI on a containerized self-hosted GitHub Actions runner\" \u2014 DevOps CI infrastructure,\
    \ no overlap with dashboard scrolling.\n- **OOMPAH-282** (Backlog): \"Stage A\
    \ migration failed for project proj-edbc8b4c\" \u2014 Backend UnicodeEncodeError\
    \ in state branch migration, no overlap with dashboard UI.\n\n**Searched but found\
    \ no active matches for:**\n- `dashboard.*scroll|scroll.*dashboard|kanban.*scroll`\n\
    - `vertical scroll|scrolling|scroll owner|overflow`\n- `layout|viewport|height|clip`\n\
    - `sticky|min-height|max-height|100vh`\n- `kanban|Kanban`\n- `board.*bottom|bottom.*board|clipped|cannot\
    \ scroll|scroll.*bottom`\n\n**Closest historical (terminal, excluded) references:**\n\
    - **OOMPAH-205** (Archived, terminal): Dashboard board reconciliation to avoid\
    \ full DOM rebuilds on WebSocket updates, and preserve scroll positions across\
    \ incremental re-renders. That work was about `renderBoard()` DOM diffing/scroll\
    \ POSITION preservation on updates \u2014 NOT the CSS scroll-owner/overflow-clipping\
    \ layout bug described in OOMPAH-666 (alerts increase page height, but the vertical\
    \ scroll container remains constrained). Different root cause, different file\
    \ surface (CSS/layout vs. JS reconciliation).\n- **OOMPAH-252, OOMPAH-200, OOMPAH-236,\
    \ OOMPAH-182, OOMPAH-171, OOMPAH-180** (all Archived/Merged): Dashboard changes\
    \ for Release Delivery overlays, epic drafts, release addendums, etc. None address\
    \ vertical scroll container / overflow / alerts-above-board layout.\n\nNo active\
    \ task in Open/Backlog/In Progress/In Review describes the same layout/overflow\
    \ bug as OOMPAH-666.\n\nFocus handoff: duplicate_detector\nDuplicate preflight\
    \ verdict: no_duplicate\nMatches: none\nEvidence: Only two active tasks exist\
    \ (OOMPAH-281 self-hosted GitHub Actions runner; OOMPAH-282 state_branch_migration\
    \ UnicodeEncodeError). Neither touches dashboard CSS, layout, kanban board vertical\
    \ scrolling, alert"
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
oompah.agent_run_id: a0d4d1f3-ca53-4231-a444-0e9ef748ec59
oompah.task_costs:
  total_input_tokens: 372340
  total_output_tokens: 8225
  total_cost_usd: 0.0
  by_model:
    opus:
      input_tokens: 15
      output_tokens: 3466
      cost_usd: 0.0
    haiku:
      input_tokens: 372325
      output_tokens: 4759
      cost_usd: 0.0
  runs:
  - profile: deep
    model: opus
    input_tokens: 15
    output_tokens: 3466
    cost_usd: 0.0
    recorded_at: '2026-07-31T22:56:58.150612+00:00'
  - profile: default
    model: haiku
    input_tokens: 372325
    output_tokens: 4759
    cost_usd: 0.0
    recorded_at: '2026-07-31T23:14:20.715106+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-666__20260731T225546Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: opus
    focus: duplicate_detector
    source_branch: OOMPAH-666
    source_sha: d96740a6ecdca353e40ef87e94a4ee91b8828df0
    completed_at: '2026-07-31T22:56:58.164909+00:00'
  - run_id: OOMPAH-666__20260731T225710Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: event_api
    source_branch: OOMPAH-666
    source_sha: 8d3da62bf488a6537a188303934957293b2d2951
    completed_at: '2026-07-31T23:14:20.729417+00:00'
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  task_branch: OOMPAH-666
  head_sha: 8d3da62bf488a6537a188303934957293b2d2951
  submitted_at: '2026-07-31T23:12:06.885897+00:00'
  updated_at: '2026-07-31T23:12:06.885897+00:00'
---
## Summary

Reproduce and fix the main dashboard layout bug where alert panels or other content above the Kanban board increase the page height but the vertical scroll container remains constrained, preventing the operator from scrolling through the board to its bottom. Inspect the height and overflow rules in oompah/templates/dashboard.html and related dashboard CSS/JavaScript; identify the actual document or application scroll owner and remove conflicting fixed-height, min-height, or overflow clipping without breaking horizontal board scrolling, per-column scrolling, sticky controls, drag and drop, or responsive layouts. Add regression coverage following the existing dashboard test patterns in tests/ that exercises the page with no alerts and with one or multiple alert panels, verifies that content above the board remains visible, and verifies that the viewport or designated vertical container can reach the bottom edge of a board taller than the viewport. Acceptance criteria: on common desktop viewport heights, an operator can scroll continuously from the dashboard header and alerts to the final Kanban row or card; the bottom is not clipped; behavior remains correct when alerts appear or clear dynamically; existing board horizontal and column scrolling behavior is preserved; focused dashboard tests and the configured project gate pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-31 22:55
---
Duplicate screening dispatched (profile: deep, task remains Open)
---
author: oompah
created: 2026-07-31 22:55
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-31 22:56
---
Run #1 [attempt=1, profile=deep, role=deep -> Claude/opus]
- Turns: 23, Tool calls: 16
- Tokens: 15 in / 3.5K out [3.5K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 17s
- Log: OOMPAH-666__20260731T225546Z.jsonl
---
author: oompah
created: 2026-07-31 22:57
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-31 22:57
---
Focus: Event Api Redaction Specialist
---
author: oompah
created: 2026-07-31 22:57
---
Understanding: I will trace dashboard document/application scroll ownership and the height/overflow rules around alerts, board, columns, sticky controls, and drag/drop. I will add regression coverage for no-alert and alert-present layouts, preserve horizontal/per-column scrolling, then run focused tests and the project gate as configured.
---
author: oompah
created: 2026-07-31 22:58
---
Discovery: dashboard.html has four interacting constraints: body is height:100vh/overflow:hidden, .main-area is flex:1/overflow:hidden, flat .board hides vertical overflow, and .column uses max-height:calc(100vh - 80px) without subtracting the alert/banner stack. Alerts therefore reduce the available main-area height while columns can extend below the clipped region. Swimlane view has its own board scroller but remains nested under the same constrained parent. I will fix the layout contract and add static regression tests for both no-alert and alert-present states, including dynamic hidden/visible alert handling and preserved horizontal/column overflow.
---
author: oompah
created: 2026-07-31 23:03
---
Implementation: Updated dashboard flex sizing so .main-area and .board can shrink to the space remaining after visible banners; changed flat .column max-height from calc(100vh - 80px) to 100% and removed the 60px column-body minimum. Explicitly kept the existing scroll owners (.column-body for flat view, .board for swimlane view), horizontal board/swimlane scrolling, and drag/drop DOM structure. Marked the remaining pre-board health panels non-shrinking so alert content stays visible during dynamic updates. Added tests/test_dashboard_vertical_scroll.py covering no-alert ordering/hidden state, one-or-many alert transitions, bottom reachability contract, and preserved horizontal/swimlane scroll rules.
---
author: oompah
created: 2026-07-31 23:11
---
Verification: focused dashboard suites passed (48 passed), the isolated full project harness passed 14,545 tests with 8 skipped and 1 expected xfail, and terminal-mutation scan passed (6/6 allowlisted). Direct make[1]: Entering directory '/home/shedwards/.oompah/worktrees/oompah/OOMPAH-666'
make[1]: Leaving directory '/home/shedwards/.oompah/worktrees/oompah/OOMPAH-666' setup could not initialize this worktree because the host uv launcher failed with a DBus transient-scope error; the trusted-gate retry rejected the separate source checkout as a non-candidate alias. The exact run-tests.sh parallel harness completed successfully against this worktree.
---
author: oompah
created: 2026-07-31 23:12
---
Completion: Pushed commit 8d3da62bf to origin/OOMPAH-666. Dashboard flex sizing now tracks the space left after dynamic alerts, flat columns scroll to their bottom without viewport-formula clipping, and existing horizontal/swimlane/per-column scrolling remains intact. Regression coverage is in tests/test_dashboard_vertical_scroll.py; focused and full isolated gates are green. Worktree is clean and branch is up to date with origin.
---
author: oompah
created: 2026-07-31 23:12
---
Fixed dashboard vertical scrolling with dynamic alert panels; added regression coverage and verified focused/full test harnesses.
---
author: oompah
created: 2026-07-31 23:13
---
Reviewed coordination overlap with OOMPAH-670 commit 67026d068. The shared dashboard.html edits are interface-compatible: OOMPAH-666 changes only flex/overflow CSS and pre-board panel sizing, while OOMPAH-670 changes the later auth global/state-update/mutation JavaScript; merge-tree reports no content conflict. The regression suites are separate files. Integration can retain both changes in either order; no additional interface adjustment is required.
---
author: oompah
created: 2026-07-31 23:14
---
Task handoff failed after the worker ran: the server-owned, task-scoped tracker capability could not update this task. The task is held in Needs Human and will not be redispatched automatically; verify the handoff service and reconcile the worker's branch before resuming it.
---
author: oompah
created: 2026-07-31 23:14
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 2, Tool calls: 98
- Tokens: 372.3K in / 4.8K out [377.1K total]
- Cost: $0.0000
- Exit: normal, Duration: 17m 15s
- Log: OOMPAH-666__20260731T225710Z.jsonl
---
author: oompah
created: 2026-07-31 23:30
---
Direct operator recovery: I reviewed the completed branch and am holding the task in Needs Human solely to prevent scheduler reassignment while I independently verify it. No further implementation worker should be dispatched; I will reconcile it directly to Ready to Integrate after validation.
---
author: oompah
created: 2026-07-31 23:45
---
Direct operator validation complete. Reviewed the dashboard flex/overflow change and regression coverage; the exact pushed head 8d3da62bf488a6537a188303934957293b2d2951 passed the full Makefile gate: 14,546 passed, 7 skipped, 1 expected xfail. The prior Needs Human state was only a task-handoff transport failure after successful implementation, so the existing ready integration record is authoritative.
---
<!-- COMMENTS:END -->
