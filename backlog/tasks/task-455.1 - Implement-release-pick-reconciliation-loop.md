---
id: TASK-455.1
title: Implement release-pick reconciliation loop
status: In Progress
assignee: []
created_date: '2026-06-08 17:29'
updated_date: '2026-06-08 19:03'
labels:
  - task
dependencies:
  - TASK-454.4
parent_task_id: TASK-455
priority: high
ordinal: 96000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Add an idempotent background reconciliation pass that scans merged source tasks and epics with oompah.backports metadata, evaluates each target branch, and advances stale or pending targets without creating duplicates.
<!-- SECTION:DESCRIPTION:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-08 18:43
---
Agent dispatched (profile: default)
---

author: oompah
created: 2026-06-08 18:45
---
Understanding: No duplicate found — this is a unique new feature. The closest candidates (TASK-453 reconciles stale In-Review tasks, TASK-455.6 reconciles PR outcomes) cover different scopes. TASK-454.4 (the blocker) has implemented release_pick_schema.py with the typed schema and FSM we need. Plan: (1) Explore existing codebase for background orchestration patterns; (2) Implement oompah/release_pick_reconciler.py — idempotent pass that scans merged tasks/epics with oompah.backports, evaluates each target branch entry against existing child tasks, and advances waiting/stale entries without duplicates; (3) Wire it into the background loop; (4) Write tests; (5) Commit and push.
---

author: oompah
created: 2026-06-08 18:49
---
Discovery: No duplicate confirmed. Key finding: release_pick_schema.py (TASK-454.4) and release_pick_validation.py (TASK-454.3) are in place. The orchestrator uses _timed_merged_labels() in _handle_yolo_review() as the hook for background reconciliation passes (following _reconcile_stale_in_review_tasks pattern). Implementation plan: (1) Create oompah/release_pick_reconciler.py with reconcile_release_picks(tracker)->ReconcileResult; (2) Add _reconcile_release_picks_pass() to orchestrator; (3) Wire into _timed_merged_labels(); (4) Tests in tests/test_release_pick_reconciler.py.
---

author: oompah
created: 2026-06-08 19:03
---
Implementation: Created oompah/release_pick_reconciler.py with reconcile_release_picks(tracker)->ReconcileResult. The pass: (1) fetches all issues once; (2) builds a child index mapping (source_id, branch) to existing child tasks; (3) for each source with oompah.backports, advances 'waiting' entries by creating child tasks or healing stale entries, and mirrors terminal child states back to the parent entry; (4) writes updated backports metadata. Added _reconcile_release_picks_pass() to Orchestrator, wired into _timed_merged_labels() in _handle_yolo_review(). No legacy-tracker fallback — requires per-project config. 53 tests in tests/test_release_pick_reconciler.py.
---
<!-- COMMENTS:END -->
