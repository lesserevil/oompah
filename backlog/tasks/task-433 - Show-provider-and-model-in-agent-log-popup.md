---
id: TASK-433
title: Show provider and model in agent log popup
status: In Progress
assignee: []
created_date: '2026-06-03 18:01'
updated_date: '2026-06-04 15:55'
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

## Comments

<!-- COMMENT:1:BEGIN -->
**oompah** (2026-06-04 15:55): Agent dispatched (profile: default)
<!-- COMMENT:1:END -->

<!-- COMMENT:2:BEGIN -->
**oompah** (2026-06-04 15:55): Focus: Duplicate Investigator
<!-- COMMENT:2:END -->

<!-- COMMENT:3:BEGIN -->
**oompah** (2026-06-04 16:00): Understanding: Searched for duplicate tasks related to 'agent log popup', 'provider model display', and 'log popup UI'. No duplicate found — this is a unique feature request. Plan: (1) Add provider_name and model_name to orchestrator get_snapshot() running rows; (2) Add them to /api/v1/agents/{id}/activity response; (3) Display in the activity overlay popup on its own line in the header with truncation/tooltip for long values.
<!-- COMMENT:3:END -->

<!-- COMMENT:4:BEGIN -->
**oompah** (2026-06-04 16:01): Discovery: RunningEntry in models.py already has provider_name and model_name fields (lines 982/986). These are NOT currently included in get_snapshot() running_rows (orchestrator.py ~11160) or /api/v1/agents/{id}/activity (server.py ~2086). The activity overlay popup (dashboard.html) builds its title from lastRunningAgents which comes from the WS-broadcast snapshot. Implementation: add fields to snapshot + API, add #activity-provider-model div to the popup HTML, update openActivityPanel and refreshActivity to populate it.
<!-- COMMENT:4:END -->
