---
id: TASK-482
title: Let agents dispatch when PR capacity is full
status: Done
assignee:
  - oompah
created_date: '2026-06-09 19:08'
updated_date: '2026-06-09 19:35'
labels: []
dependencies: []
priority: high
ordinal: 210000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Bug: project open-review caps currently block _should_dispatch, so a single in-review PR can idle all ready work for that project. Dispatch should continue while PR capacity is full. Only review/PR creation should be capacity-aware and deferred until capacity frees. Update close/review handoff and maintenance retry paths so completed work without a PR can remain Done when the only blocker is PR capacity, and later gets a PR when capacity is available.
<!-- SECTION:DESCRIPTION:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Implemented review-cap deferral so project PR capacity no longer blocks agent dispatch. Normal task and epic PR handoffs now defer while the cap is full, Done tasks can remain Done when PR capacity is the only blocker, and deferred Done reviews are retried only when local git proves the task branch is ahead. Verification: focused pytest selection passed with 103 tests; full make test passed with 6258 tests and 10 warnings.
<!-- SECTION:FINAL_SUMMARY:END -->
