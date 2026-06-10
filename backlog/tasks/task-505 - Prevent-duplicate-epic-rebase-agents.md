---
id: TASK-505
title: Prevent duplicate epic rebase agents
status: Done
assignee:
  - oompah
created_date: '2026-06-10 06:38'
updated_date: '2026-06-10 06:43'
labels: []
dependencies: []
priority: high
ordinal: 225000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Oompah filed and dispatched multiple sibling rebase tasks for the same shared epic branch (TASK-462.7/.8/.9/.10 for epic-TASK-462). Fix rebase task idempotency and dispatch selection so only one active rebase worker can exist per epic branch; archived/merged duplicates must not be dispatched. Add regression tests covering duplicate sibling detection and shared epic dispatch suppression for rebase tasks.
<!-- SECTION:DESCRIPTION:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Fixed duplicate epic rebase agent handling. Oompah now recognizes auto-filed epic rebase tasks, reuses an existing actionable sibling before filing a new one, and serializes P0 rebase siblings for the same shared epic branch during dispatch selection and live dispatch checks. Added regressions for YOLO idempotency and shared-epic dispatch suppression. Verification: uv run pytest tests/test_epic_strategy.py tests/test_yolo_handlers.py -q (122 passed).
<!-- SECTION:FINAL_SUMMARY:END -->
