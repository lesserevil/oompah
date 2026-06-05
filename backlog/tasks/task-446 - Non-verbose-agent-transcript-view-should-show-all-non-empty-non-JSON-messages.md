---
id: TASK-446
title: 'Non-verbose agent transcript view should show all non-empty, non-JSON messages'
status: Backlog
assignee: []
created_date: '2026-06-04 14:30'
labels: []
dependencies: []
ordinal: 82000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
In the agent transcript/console view, the non-verbose ('verbose off') mode currently hides plain-text 'thinking' messages (agent_thinking) and other non-empty text, so operators watching a live agent (e.g. TASK-706.1) can't see the agent's reasoning narration without flipping verbose on.

Change the non-verbose filter so it shows ALL non-empty, non-JSON messages. The only things hidden in non-verbose mode should be: (1) empty/whitespace-only messages, and (2) events whose visible payload is just a raw JSON blob (e.g. tool-call argument dumps, structured event payloads). Plain-text content -- assistant text AND thinking narration -- must be visible in non-verbose mode. Verbose mode behavior is unchanged (still shows everything).

Likely touch points: the transcript rendering / verbose toggle in the agent activity view (frontend filter that decides which ConsoleEvent kinds render), and oompah/console_format.py event kinds (agent_thinking carries plain 'text'). Find the predicate that gates messages on the verbose flag and broaden the non-verbose path to 'non-empty AND not pure-JSON' rather than an allowlist of kinds.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 In verbose=off, agent_thinking (plain-text) messages are visible
- [ ] #2 In verbose=off, all non-empty, non-JSON text messages are visible (not just an allowlisted subset of kinds)
- [ ] #3 In verbose=off, empty/whitespace-only messages and JSON-only payload events remain hidden
- [ ] #4 In verbose=on, the view behavior is unchanged (shows everything it does today)
<!-- AC:END -->
