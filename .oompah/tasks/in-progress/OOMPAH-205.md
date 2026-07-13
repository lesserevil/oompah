---
id: OOMPAH-205
type: bug
status: In Progress
priority: 2
title: Avoid full dashboard board rebuilds for unchanged issue snapshots
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-13T20:05:14.303298Z'
updated_at: '2026-07-13T20:11:06.812809Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: d4bc2d5d-a3e7-4e1e-bf7b-05bae5558cd7
oompah.task_costs:
  total_input_tokens: 58
  total_output_tokens: 1560
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 58
      output_tokens: 1560
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 58
    output_tokens: 1560
    cost_usd: 0.0
    recorded_at: '2026-07-13T20:10:14.415078+00:00'
---
## Summary

The dashboard currently clears and rebuilds every board column/card for each WebSocket issues update. The orchestrator emits a full observer update on every tick, so the 3-second issue-broadcast throttle still produces visibly frequent full re-renders even when no cards changed.

Implement incremental board reconciliation or snapshot-change suppression so unchanged issue payloads do not rebuild the board. Preserve live state/activity indicators, optimistic drag/drop updates, filters, view modes, keyboard/focus behavior, and editing safeguards.

Acceptance criteria
- An identical issue snapshot does not clear/recreate #board or its cards.
- A changed card updates only the necessary card/column elements without losing scroll position, focus, active dialogs, drag state, or inline edits.
- State-only agent activity continues to update lightweight UI without a board rebuild.
- Existing board behavior remains correct for project filtering, hide-merged, swimlane/flat modes, drag/drop, and WebSocket reconnection.

Tests
- Add browser tests for no-op snapshots, one-card state change, project filter, active inline edit, focus preservation, and optimistic drag/drop reconciliation.
- Run make test.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-13 20:07
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-13 20:07
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-13 20:07
---
Understanding: This issue asks for incremental board reconciliation on the dashboard — avoiding full DOM rebuilds when unchanged issue snapshots arrive via WebSocket. My first step as Duplicate Investigator is to search for similar tasks before any implementation work begins.
---
author: oompah
created: 2026-07-13 20:09
---
Discovery: Confirmed NOT a duplicate. Searched all task files (.oompah/tasks/), plans/, and docs/ for: board rebuild, board reconciliation, snapshot-change suppression, WebSocket issue broadcast, incremental board, no-op snapshot, unchanged issues. No existing task covers this problem. OOMPAH-203 (Done) is superficially related (auto-update restarts breaking drag/drop) but is a different backend fix. OOMPAH-205 is unique: it asks for frontend JavaScript incremental reconciliation in dashboard.html to avoid full DOM rebuilds on identical WebSocket issue payloads. This is a frontend task — handoff to frontend agent is appropriate.
---
author: oompah
created: 2026-07-13 20:09
---
HANDOFF: Duplicate investigation complete — this is NOT a duplicate (confirmed by full search of all tasks, plans, and docs). OOMPAH-205 is a unique frontend performance bug. Root: dashboard.html clears and rebuilds all board columns/cards on every WebSocket issues update regardless of whether the payload changed. The orchestrator emits full observer updates every tick, so even with the 3-second throttle the board re-renders constantly. A frontend agent needs to implement: (1) snapshot hash comparison to skip board rebuild when payload is identical, (2) incremental card/column DOM reconciliation when specific issues change, (3) lightweight agent-activity updates that bypass board rebuild, (4) preservation of scroll position, focus, drag state, inline edits across updates. Tests required: no-op snapshot, one-card state change, project filter, active inline edit, focus preservation, optimistic drag/drop reconciliation. Key file: oompah/templates/dashboard.html (JavaScript WebSocket handler and board rendering functions).
---
author: oompah
created: 2026-07-13 20:10
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 0, Tool calls: 36
- Tokens: 58 in / 1.6K out [1.6K total]
- Cost: $0.0000
- Exit: terminated, Duration: 3m 1s
- Log: OOMPAH-205__20260713T200721Z.jsonl
---
author: oompah
created: 2026-07-13 20:10
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-07-13 20:10
---
Focus: Frontend Developer
---
author: oompah
created: 2026-07-13 20:11
---
Understanding: I'm the frontend developer agent picking up this task. Previous agents confirmed this is NOT a duplicate. The root cause is in dashboard.html's JavaScript WebSocket handler — on every WS 'issues' message, the board is fully cleared and rebuilt regardless of whether the content changed. Plan: (1) Read dashboard.html to understand current rendering flow, (2) Implement snapshot hash comparison to skip full rebuild on identical payloads, (3) Implement incremental card/column DOM reconciliation for changed issues only, (4) Add lightweight agent-activity path that bypasses board rebuild, (5) Preserve scroll/focus/drag state across updates, (6) Add tests per acceptance criteria, (7) Run make test.
---
<!-- COMMENTS:END -->
