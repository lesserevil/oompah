---
id: TASK-433
title: Show provider and model in agent log popup
status: Done
assignee: []
created_date: '2026-06-03 18:01'
updated_date: '2026-06-04 16:06'
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
- [x] #1 Agent log popup displays both provider and model when that metadata is available.
- [x] #2 Long provider/model values wrap, truncate with tooltip, or otherwise remain readable without breaking the popup header layout.
- [x] #3 Relevant UI tests or component tests cover the new metadata display and long-text behavior.
<!-- AC:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Added provider and model metadata display to the agent log popup. The #activity-provider-model element shows provider · model on its own line below the agent title, styled in muted smaller font with text-overflow:ellipsis and tooltip for long values. Backend: provider_name and model_name added to get_snapshot() running rows (orchestrator.py) and to /api/v1/agents/{id}/activity API response (server.py). Frontend: openActivityPanel() reads from lastRunningAgents snapshot; refreshActivity() fills from API when not yet set; closeActivityPanel() clears on close. 27 new tests all passing.
<!-- SECTION:FINAL_SUMMARY:END -->

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

<!-- COMMENT:5:BEGIN -->
**oompah** (2026-06-04 16:10): Implementation: Added provider_name/model_name to orchestrator snapshot and activity API. Added #activity-provider-model div in popup header (hidden by default), .activity-provider-model CSS with muted color/small font/ellipsis+tooltip, setActivityProviderModel() helper, and wired it into openActivityPanel/refreshActivity/closeActivityPanel. Verification: 27/27 new tests pass; 221/221 dashboard tests pass.
<!-- COMMENT:5:END -->
