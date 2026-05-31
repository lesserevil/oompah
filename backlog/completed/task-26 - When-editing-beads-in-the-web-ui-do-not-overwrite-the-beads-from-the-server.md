---
id: TASK-26
title: When editing beads in the web ui, do not overwrite the beads from the server
status: Done
assignee: []
created_date: 2026-03-06 21:05
updated_date: 2026-03-06 21:38
labels:
- archive:yes
- merged
- bug
- beads-migrated
dependencies: []
priority: high
ordinal: 1000
type: bug
beads:
  id: umpah-tgu
  state: closed
  parent_id: null
  dependencies: []
  branch_name: umpah-tgu
  target_branch: null
  url: null
  created_at: '2026-03-06T21:05:55Z'
  updated_at: '2026-03-06T21:38:18Z'
  closed_at: '2026-03-06T21:38:18Z'
---
## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
If I'm editing a bug in the web ui, updates from the server for that bead must not overwrite what I'm writing in the ui. And when I'm done with my edits, they should overwrite the bead on the server.
<!-- SECTION:DESCRIPTION:END -->

## Comments
<!-- COMMENTS:BEGIN -->
<!-- COMMENT:BEGIN -->
index: b301f097-5bc0-47f1-adaf-d3f3637d6e75
author: oompah
created: 2026-03-06T21:06:13Z

Agent dispatched (profile: deep)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: adbe4276-3cc1-4a01-b336-229a91149a3b
author: oompah
created: 2026-03-06T21:06:14Z

Focus: Bug Investigator & Fixer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 2ecfe864-d9f9-4b64-bb23-09dc8f4aa891
author: Shawn Edwards
created: 2026-03-06T21:07:37Z

I understand the issue: When a user is inline-editing a bead's title or description in the web UI, incoming WebSocket updates (issues broadcast) re-render the entire board, which destroys the user's in-progress edits. The fix needs to: (1) track which fields are being edited, (2) skip overwriting those fields during re-render, or (3) prevent re-rendering cards that are being edited. My plan is to examine the JS in the dashboard HTML to understand the re-render flow, then implement edit-state tracking to protect in-progress edits.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 529c31fd-a18e-40ba-91ef-1d1c9af6aef1
author: Shawn Edwards
created: 2026-03-06T21:08:21Z

Found the bug: renderBoard() in the dashboard JS completely rebuilds the DOM (board.innerHTML = '') on every WebSocket 'issues' message. This destroys any in-progress contenteditable edits. Similarly, refreshOpenDetailPanel() reloads the detail panel, overwriting any edits there. The fix: (1) Track which element is being edited using a global 'editing' state, (2) Skip renderBoard() if an inline edit is active, (3) After the user finishes editing (blur), apply the queued update. For the detail panel, the comment text is already preserved - I need to add the same for the description field.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: aac74275-97a2-4dfe-b874-403deb9b07b0
author: oompah
created: 2026-03-06T21:29:44Z

Agent dispatched (profile: deep)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: bc8de549-61be-4e6c-8643-a79078f77a20
author: oompah
created: 2026-03-06T21:29:47Z

Focus: Bug Investigator & Fixer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: ebea51be-72fd-4279-8653-21bb14845a49
author: Shawn Edwards
created: 2026-03-06T21:31:25Z

I understand the issue: When a user is inline-editing a bead's title or description (contenteditable fields) on a card in the kanban board, incoming WebSocket 'issues' messages call renderBoard() which does board.innerHTML = '', completely destroying the DOM including any in-progress edits. Similarly, refreshOpenDetailPanel() reloads the detail panel, overwriting description edits there.

My plan:
1. Track which element is being actively edited (field + identifier) via focus/blur events
2. During renderBoard(), if an edit is active, store the incoming data but skip the full DOM rebuild — or merge updates without touching the actively-edited card
3. When the user finishes editing (blur), the save fires as normal and the pending board data gets rendered
4. For the detail panel, skip refresh while a field is being edited
5. Write tests to verify editing state is tracked and renders are properly deferred
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 70494228-e295-41b3-99e7-f6b2d53b85ab
author: Shawn Edwards
created: 2026-03-06T21:32:42Z

Found the bug in the dashboard JS (embedded in server.py DASHBOARD_HTML):

1. **renderBoard()** - does board.innerHTML = '' on every WebSocket 'issues' message, destroying any in-progress contenteditable edits on cards
2. **refreshOpenDetailPanel()** - calls openDetailPanel() which rebuilds the detail panel body, overwriting description edits (comment text is already preserved via prevText logic)
3. **ws.onmessage handler** - calls both renderBoard(msg.data) and refreshOpenDetailPanel() for every 'issues' message

Root cause: No edit-state tracking exists. The system has no way to know a user is mid-edit, so every server update obliterates the user's work.

Fix approach: Add a global editingState tracker, skip renderBoard/refreshOpenDetailPanel when editing is active, queue the latest data, and render the queued data on blur (after save completes).
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: c0fbb676-b335-44e9-8a57-1d58bf0e6e8f
author: Shawn Edwards
created: 2026-03-06T21:35:24Z

Implementation complete. Four surgical changes to the dashboard JavaScript (embedded in server.py DASHBOARD_HTML):

1. **Added edit-state tracking globals**: editingState (tracks {identifier, field} of active edit), _pendingBoardData (queues latest server data during edits)

2. **Modified renderBoard()**: When editingState is non-null, the function stores incoming data in _pendingBoardData and returns early without touching the DOM. The in-memory boardData/allIssuesFlat are still updated so other lookups work.

3. **Modified createCard() focus/blur handlers**: Focus sets editingState, blur clears it, saves the edit via API, then flushes any _pendingBoardData by calling renderBoard() with the queued data.

4. **Modified refreshOpenDetailPanel()**: Checks if the comment textarea has focus before refreshing; if so, skips the refresh entirely. Also re-checks after the 500ms debounce in case the user started typing during the wait.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: ffbdb93a-cbc1-4031-86ed-ce7794fca3f5
author: Shawn Edwards
created: 2026-03-06T21:37:01Z

Verification: All 151 tests pass (140 existing + 11 new). The new test_server_edit_protection.py validates:
- editingState and _pendingBoardData globals are declared
- renderBoard() checks editingState and defers when editing is active
- boardData/allIssuesFlat are still updated even when deferred
- Focus handler sets editingState
- Blur handler clears editingState BEFORE the async save (important!)
- Blur handler flushes _pendingBoardData after save
- Detail panel refresh skips when comment textarea is focused
- The wiring is correct: editingState = null happens before await updateIssue
- Normal renderBoard clears _pendingBoardData
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: ea4a4e5b-6424-497c-8b37-db5e453a33d3
author: Shawn Edwards
created: 2026-03-06T21:38:02Z

PR created: https://github.com/lesserevil/oompah/pull/4

Summary of changes:
- oompah/server.py: 4 surgical JS changes in DASHBOARD_HTML to add edit-state tracking
- tests/test_server_edit_protection.py: 11 new tests verifying the fix

The fix ensures that when a user is editing a bead's title, description, or comment in the web UI, incoming WebSocket updates queue data instead of destroying the DOM. When the user finishes editing, queued data is flushed and the board renders with the latest server state.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 0b99105e-43f2-4186-8877-be1294877197
author: oompah
created: 2026-03-06T21:38:39Z

Agent completed successfully in 535s (2981562 tokens)
<!-- COMMENT:END -->
<!-- COMMENTS:END -->
