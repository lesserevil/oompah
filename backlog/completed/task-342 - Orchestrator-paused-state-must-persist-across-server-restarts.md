---
id: TASK-342
title: Orchestrator paused state must persist across server restarts
status: Done
assignee: []
created_date: 2026-05-05 01:21
updated_date: 2026-05-05 01:57
labels:
- bug
- beads-migrated
dependencies: []
priority: medium
ordinal: 1000
type: bug
beads:
  id: oompah-zlz_2-znn
  state: closed
  parent_id: null
  dependencies: []
  branch_name: oompah-zlz_2-znn
  target_branch: null
  url: null
  created_at: '2026-05-05T01:21:33Z'
  updated_at: '2026-05-05T01:57:59Z'
  closed_at: '2026-05-05T01:57:59Z'
---
## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
When the orchestrator is paused via /api/v1/orchestrator/pause, that state is lost on the next 'make restart' — the new process comes up running. The pause should survive restarts: if pause was set before the restart, the new process should boot in the paused state.

Suspected location: pause/resume handlers and orchestrator startup. Note tests/test_orchestrator_pause.py contains tests named test_paused_state_survives_restart and test_pause_persists_to_disk that imply this should already work via .oompah/service_state.json. Check whether (a) the pause is being persisted to that file on /pause but not loaded on boot, or (b) the load is happening but something resets the state, or (c) the test is asserting against an in-memory snapshot rather than actual disk persistence.
<!-- SECTION:DESCRIPTION:END -->

## Comments
<!-- COMMENTS:BEGIN -->
<!-- COMMENT:BEGIN -->
index: 019df5b9-f9ff-7232-8b79-a2f5d20b4532
author: oompah
created: 2026-05-05T01:21:39Z

Agent dispatched (profile: default)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df5ba-0076-7897-a6ab-79fa115c1189
author: oompah
created: 2026-05-05T01:21:41Z

Focus: Test Engineer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df5c8-c3eb-70bb-9f7e-f8b7e911dc4e
author: oompah
created: 2026-05-05T01:37:49Z

Agent dispatched (profile: default)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df5c8-ddba-7278-8e5f-55b3de316ac6
author: oompah
created: 2026-05-05T01:37:55Z

Focus: Test Engineer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df5cd-c2b5-788f-9c01-f718c32a1e57
author: oompah
created: 2026-05-05T01:43:16Z

Agent dispatched (profile: default)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df5cd-d49c-705d-9802-fa7f1c445d27
author: oompah
created: 2026-05-05T01:43:20Z

Focus: Test Engineer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df5ce-86a9-795e-8170-05cb7b9c013e
author: oompah
created: 2026-05-05T01:44:06Z

Agent dispatched (profile: default)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df5ce-8994-710d-84e7-a754ff53f330
author: oompah
created: 2026-05-05T01:44:07Z

Focus: Test Engineer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df5d5-8b8b-769f-b760-91712ff59edc
author: oompah
created: 2026-05-05T01:51:46Z

Agent dispatched (profile: default)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df5d5-8f1d-7a0e-8e0b-706ef80e1ee2
author: oompah
created: 2026-05-05T01:51:47Z

Focus: Test Engineer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df5d6-3f4f-72a3-b121-b953a2f5746b
author: oompah
created: 2026-05-05T01:52:32Z

Agent dispatched (profile: default)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df5d6-427c-7d3e-b335-c8798641294d
author: oompah
created: 2026-05-05T01:52:33Z

Focus: Test Engineer
<!-- COMMENT:END -->
<!-- COMMENTS:END -->
