---
id: TASK-433
title: Show provider and model in agent log popup
status: Backlog
assignee: []
created_date: '2026-06-03 18:01'
labels:
  - feature
dependencies: []
priority: medium
ordinal: 69000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The agent log popup should display the provider and model associated with the agent run or log entry. Provider/model identifiers can be long, so the UI should put this metadata on its own line in the popup header or another readable header area instead of forcing it into a cramped inline label.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Agent log popup displays both provider and model when that metadata is available.
- [ ] #2 Long provider/model values wrap, truncate with tooltip, or otherwise remain readable without breaking the popup header layout.
- [ ] #3 Relevant UI tests or component tests cover the new metadata display and long-text behavior.
<!-- AC:END -->
