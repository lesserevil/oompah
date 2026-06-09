---
id: TASK-477
title: Bound release-pick maintenance runtime
status: Done
assignee:
  - oompah
created_date: '2026-06-09 17:56'
updated_date: '2026-06-09 18:10'
labels: []
dependencies: []
priority: high
ordinal: 205000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The release_picks maintenance job can run CPU-hot for minutes while scanning all task metadata. Add a cooperative runtime/batch bound so it yields between passes instead of monopolizing a tick worker and making the service look hung.
<!-- SECTION:DESCRIPTION:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Release-pick maintenance now uses cached release-pick metadata loaded on Issue objects, avoiding per-task metadata rereads during the full-corpus scan. The release_picks maintenance job also has an env-backed runtime budget (OOMPAH_RELEASE_PICK_MAX_RUNTIME_SECONDS, default 15) and passes a cooperative stop callback so reconciliation yields at safe boundaries. Verified with focused tests and full make test: 6240 passed.
<!-- SECTION:FINAL_SUMMARY:END -->
