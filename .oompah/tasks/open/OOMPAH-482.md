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
- OOMPAH-458
labels: []
assignee: null
created_at: '2026-07-28T13:07:30.191340Z'
updated_at: '2026-07-29T01:59:33.466473Z'
work_branch: epic-OOMPAH-459
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 5d34fedffb4ff803f6dd76be8a7be0f8fd5e1cd2d329a1c465f5281c87f7db5b
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: cadc6de7-8e17-48a6-b793-b5fe10d25833
  claim_owner: 5d80b10c-0ace-4fc9-8e33-587cf319fe4d
  claimed_at: '2026-07-29T01:59:26.844607+00:00'
  claim_expires_at: '2026-07-29T02:29:26.844607+00:00'
  retry_count: 0
  retry_after: null
oompah.agent_run_id: fc0ab54d-53aa-4201-b432-2cf0a8881e69
oompah.work_branch: epic-OOMPAH-459
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

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-29 01:59
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-29 01:59
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
