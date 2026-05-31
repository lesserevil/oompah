---
id: TASK-107
title: Make the agent details pane easier to read
status: Done
assignee: []
created_date: 2026-03-08 20:50
updated_date: 2026-03-08 21:03
labels:
- archive:yes
- merged
- beads-migrated
dependencies: []
priority: medium
ordinal: 1000
type: task
beads:
  id: oompah-0fl
  state: closed
  parent_id: null
  dependencies: []
  branch_name: oompah-0fl
  target_branch: null
  url: null
  created_at: '2026-03-08T20:50:35Z'
  updated_at: '2026-03-08T21:03:24Z'
  closed_at: '2026-03-08T21:03:24Z'
---
## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The agent deatails popup scrolls way too fast to keep up. How about this: we have each input into the model (that's the message, right?) be a collapsable element with the message as the text for the element, and then we can expand the message to see the full tool/reply/etc. for that message. The collapsible message elements should all start collapsed.
<!-- SECTION:DESCRIPTION:END -->

## Comments
<!-- COMMENTS:BEGIN -->
<!-- COMMENT:BEGIN -->
index: c7431837-582d-4150-b4ea-18954f987fd1
author: oompah
created: 2026-03-08T20:59:07Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: ec2d3cfc-8a09-4b70-8ce5-3f9bc9d20405
author: oompah
created: 2026-03-08T20:59:08Z

Focus: Software Engineer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: da7b1fe8-d01a-49bb-9d24-4b66db110a9d
author: oompah
created: 2026-03-08T20:59:38Z

I understand the issue: The agent activity panel (the popup that shows agent activity when clicking a running agent chip) scrolls too fast to read because all messages are shown expanded.

My plan:
1. Modify the activity panel rendering so each activity entry starts collapsed
2. Each entry will show the kind + summary as the clickable header
3. Clicking expands to show the full detail content
4. Currently, entries only expand if they have 'detail' - but the issue wants ALL messages to be collapsible with the message (summary) as the label

The key function to modify is  in . Currently entries with details are expandable, but they start expanded only via click. Looking at the code, entries don't auto-expand - they start collapsed already (the  class is toggled on click).

Wait - looking more carefully, the activity entries do start collapsed already (the  CSS has  and only shows when the  class is present). But the real issue is that ALL entries and their summaries are visible, making it scroll fast.

The fix: make each entry collapsible by default (collapsed), showing just a brief identifier (turn + kind) as the header, with the full summary+detail revealed on expand. All entries should start collapsed.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: c622b92e-3f76-45a6-a2fd-d8856199d203
author: oompah
created: 2026-03-08T21:00:16Z

Found the relevant code: The  function in  (around line 1933) currently shows all entries expanded (summary always visible, only 'detail' is hidden behind expand). The issue asks that each entry be a collapsible element starting collapsed, showing just the message summary as the header label.

My implementation plan:
1. Modify  so each entry starts COLLAPSED - showing only turn + kind + truncated summary as the header
2. The full summary AND detail are revealed when the user clicks to expand
3. Add a 'collapsed' CSS class variant for the activity entries (to hide summary body by default)
4. Update CSS for  to support the collapsed-by-default behavior
5. Write a test to verify this behavior
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 58b048b3-93ca-4fb1-84a3-901bbb4e8a1c
author: oompah
created: 2026-03-08T21:02:50Z

Implementation complete. Changes made to oompah/templates/dashboard.html:

1. CSS changes:
   - : Simplified to just handle border and cursor
   - Added : flex row with turn/kind/summary for the collapsed view
   - Added : rotating arrow indicator (▶ collapses, ▼ expanded)
   - Added : hidden by default (display:none), shown when
   - : now uses white-space:nowrap + text-overflow:ellipsis for single-line truncation
   - : rotates the arrow 90deg when expanded

2. JS changes in :
   - All entries start collapsed (no 'expanded' class set initially)
   - Click handler added to ALL entries unconditionally (not just those with detail)
   - Each entry: collapsible header (turn + kind + summary one-liner) + body-content (detail or full summary)
   - Toggle arrow (▶) in the header rotates to ▼ when expanded

3. Added 19 new tests in tests/test_activity_panel_collapsible.py - all pass.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 68fa3280-5979-44c0-b2e4-87debcff62db
author: oompah
created: 2026-03-08T21:03:17Z

PR created: https://github.com/lesserevil/oompah/pull/39

All 19 new tests pass. The agent activity panel now shows all entries collapsed by default. Each entry displays a compact one-line header (turn number + kind + truncated summary) with a ▶ toggle arrow. Clicking any entry expands it to show the full content. This addresses the issue of the panel scrolling too fast to read.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 6e9f13c7-4dbf-4e92-8ba4-d9c61f308ff9
author: oompah
created: 2026-03-08T21:03:24Z

Agent completed successfully in 257s (1376262 tokens)
<!-- COMMENT:END -->
<!-- COMMENTS:END -->
