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
updated_at: '2026-07-13T20:09:44.869926Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 00f509c2-d4ae-457f-aef9-39fca1e55fec
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
<!-- COMMENTS:END -->
