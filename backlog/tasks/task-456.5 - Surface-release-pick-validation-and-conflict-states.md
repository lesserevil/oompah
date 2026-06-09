---
id: TASK-456.5
title: Surface release-pick validation and conflict states
status: Open
assignee: []
created_date: '2026-06-08 17:29'
updated_date: '2026-06-09 02:34'
labels:
  - task
dependencies:
  - TASK-456.1
parent_task_id: TASK-456
priority: high
ordinal: 107000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Show branch validation errors, waiting-for-source-merge state, open PRs, merged picks, closed PRs, and cherry-pick conflicts clearly in the UI without requiring operators to inspect logs.
<!-- SECTION:DESCRIPTION:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-08 21:24
---
Agent dispatched (profile: default)
---

author: oompah
created: 2026-06-08 21:24
---
Focus: Duplicate Investigator
---

author: oompah
created: 2026-06-08 22:15
---
Agent dispatched (profile: default)
---

author: oompah
created: 2026-06-08 22:16
---
Focus: Frontend Developer
---

author: oompah
created: 2026-06-08 22:21
---
Run #1 [attempt=1, profile=default, role=fast -> InferenceAPI/nvidia/nvidia/nemotron-3-ultra]
- Turns: 18, Tool calls: 17
- Tokens: 784.9K in / 1.5K out [786.5K total]
- Cost: $0.0000
- Exit: normal, Duration: 5m 33s
- Log: TASK-456.5__20260608T221644Z.jsonl
---

author: oompah
created: 2026-06-08 22:21
---
Agent completed successfully in 333s (786452 tokens)
---

author: oompah
created: 2026-06-08 22:21
---
Agent completed without closing this issue (333s (786452 tokens)). Escalating from 'default' to 'standard'. Retrying in 10s (1/3).
---

author: oompah
created: 2026-06-08 22:22
---
Agent dispatched (profile: standard)
---

author: oompah
created: 2026-06-08 22:22
---
Focus: Frontend Developer
---

author: oompah
created: 2026-06-08 22:42
---
Run #2 [attempt=2, profile=standard, role=standard -> InferenceAPI/nvidia/nvidia/nemotron-3-ultra]
- Turns: 0, Tool calls: 20
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 20m 7s
- Log: TASK-456.5__20260608T222238Z.jsonl
---

author: oompah
created: 2026-06-08 22:45
---
Retrying (attempt #2, agent: standard)
---

author: oompah
created: 2026-06-08 22:45
---
Focus: Duplicate Investigator
---

author: oompah
created: 2026-06-08 22:46
---
Agent failed: RuntimeError: Codex exec exited with code 1: . Retrying in 40s (attempt #3)
---

author: oompah
created: 2026-06-08 22:46
---
Run #3 [attempt=3, profile=standard, role=standard -> Codex/default]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 1m 26s
- Log: TASK-456.5__20260608T224614Z.jsonl
---

author: oompah
created: 2026-06-08 22:48
---
Retrying (attempt #3, agent: standard)
---

author: oompah
created: 2026-06-08 22:58
---
Understanding + Discovery: This is NOT a duplicate. TASK-456.5 is the last piece of the Release Picks UI series. TASK-456.1-4 are Done and provide the API (GET/PATCH /release-picks) and basic UI sections (task detail panel, Add modal, epic matrix). TASK-456.5 specifically needs to surface in the UI: (1) branch validation errors (is_valid/validation_error from API - currently NOT displayed), (2) closed PRs (pr_url present but status=cherry_picking means prior PR was closed), (3) waiting-for-source-merge state (clearer 'waiting' hint), (4) conflict state visual prominence. Key files: oompah/templates/dashboard.html renderReleasePicksSection() function and CSS. Plan: add validation_error display, closed PR indicator with .release-pick-pr-closed CSS, clearer waiting hint; add tests in test_dashboard_release_pick_states.py.
---

author: oompah
created: 2026-06-08 23:05
---
Implementation: Updated oompah/templates/dashboard.html with: (1) .release-pick-validation-error CSS class (red border/background) for branch validation error banners, (2) .release-pick-pr-closed CSS class (line-through + muted opacity) for PRs closed without merging, (3) renderReleasePicksSection now reads entry.is_valid/entry.validation_error and shows ⚠ error banner per-entry, (4) PR links now state-aware: pr_open → active link, merged → '✓' indicator, otherwise → '(closed)' with .release-pick-pr-closed styling, (5) releasePickNextAction 'waiting' updated to 'Waiting for source to merge' and 'conflict' to 'Resolve conflict and re-pick'. Added tests/test_dashboard_release_pick_states.py with 16 new tests covering all surfaced states.
---
<!-- COMMENTS:END -->
