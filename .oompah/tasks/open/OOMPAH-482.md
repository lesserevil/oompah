---
id: OOMPAH-482
type: feature
status: Open
priority: 1
title: Dispatch one repair-planner run for an epic that fails audit
parent: OOMPAH-459
children: []
blocked_by:
- OOMPAH-466
- OOMPAH-475
labels: []
assignee: null
created_at: '2026-07-28T13:07:30.191340Z'
updated_at: '2026-07-28T18:07:22.432223Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Implementation scope

When coordinator result handling reopens an epic as Open with audit:repair-needed, allow _plan_open_epics/_should_dispatch_epic to schedule one epic_planner run even though children already exist. Provide the failed audit summary and evidence references in the prompt. Update the epic_planner focus for repair mode: inspect existing children, reopen the child responsible for a gap or create narrowly scoped missing children, add dependencies, then remove audit:repair-needed and end without implementing code. Prevent duplicate repair runs with persisted audit ID/claim metadata. Ordinary already-planned epics without the label remain nondispatchable.

Tests

Cover existing child reopened, missing child created, multiple findings, dependency creation, no duplicate planning, restart, label removal, planner failure/retry, normal epic unchanged, and nested epic repair. Run epic planning tests and make test.

Acceptance criteria

A failed epic audit becomes actionable without the auditor creating work; exactly one repair-planner session reconciles the findings into normal child workflow.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

