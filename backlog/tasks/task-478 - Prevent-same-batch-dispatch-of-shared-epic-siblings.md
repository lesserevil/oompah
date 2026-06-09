---
id: TASK-478
title: Prevent same-batch dispatch of shared epic siblings
status: Done
assignee:
  - oompah
created_date: '2026-06-09 18:19'
updated_date: '2026-06-09 18:29'
labels:
  - bug
dependencies: []
priority: high
ordinal: 206000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Bug: projects with epic_strategy=shared can still dispatch multiple children from the same epic in one dispatch batch. _should_dispatch() only sees already-running/claimed siblings; _select_dispatchable() builds the ready list before any accepted candidate becomes running, so siblings accepted in the same batch bypass the shared-epic serialization rule. Fix selection to reserve shared-epic slots per project/parent while building the batch, preserving the existing P0 bypass and flat/stacked behavior. Add regression tests.
<!-- SECTION:DESCRIPTION:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Fixed shared-epic dispatch selection so _select_dispatchable reserves a per-project/per-parent shared epic slot as soon as a non-P0 child is accepted into the ready batch. This prevents two siblings from the same shared epic from being dispatched in the same tick before either is marked running. Added regression coverage for same-parent shared serialization, different shared epics, flat/stacked controls, and the existing P0 bypass.
<!-- SECTION:FINAL_SUMMARY:END -->
