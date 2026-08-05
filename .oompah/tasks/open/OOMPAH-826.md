---
id: OOMPAH-826
type: bug
status: Open
priority: 1
title: Gate changed heads before adopting an existing open review
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-05T12:59:13.179121Z'
updated_at: '2026-08-05T18:17:32.510479Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 9f01d5fa0cbf46c07fb161dc8acb5f98101fda5b10483836a60aa8f789ac25be
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: d6518b65-9c4e-43f2-8a6a-40411c2834ee
  claim_owner: 3a62b7a5-bbb7-4494-ae8d-738d99774e0d
  claimed_at: '2026-08-05T18:17:12.295817+00:00'
  claim_expires_at: '2026-08-05T18:47:12.295817+00:00'
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 3afe0e24-ff78-4f66-a922-91a298edda72
---
## Summary

Triggered by: OOMPAH-825

Live reproduction on OOMPAH-825 PR #721 on 2026-08-05: exact head 74c4b71c passed the local branch gate, forge CI failed, a test-only repair advanced the branch to 11c75e6c, and explicit resubmission immediately moved the task to In Review while validation_resources and quality_gates remained idle. The existing-review path in oompah/orchestrator.py adopts a live open review and calls _mark_task_in_review before _review_quality_gate_passes, so the changed repaired head has no local exact-head gate evidence. This is the standalone/integration-entry analogue of archived OOMPAH-520, which fixed only existing epic-review reconciliation. Implementation scope: bind existing open review adoption to its exact current source head/generation; before marking an accepted submission In Review or allowing merge reconciliation, require _review_quality_gate_passes for the submitted exact head, reusing same-head PASS only; preserve the open review while the gate runs/fails, route a true gate failure through the normal retryable Needs CI Fix flow, and avoid duplicate gates/reviews/comments across webhook, polling, resubmit, and restart races. Relevant code: oompah/orchestrator.py existing live-review adoption in integration delivery, standalone Ready review recovery, review-head metadata/authorities, quality-gate outcome/cache fencing. Required tests: OOMPAH-825 case with existing open PR old gate PASS then changed CI-fix head; changed head must run once before In Review, unchanged head reuses PASS, gate failure never merges/adopts, concurrent webhook+submit coalesces, restart preserves exact-head evidence, and epic behavior from OOMPAH-520 remains intact. Acceptance: every accepted current review head has passing local exact-head evidence before In Review/merge eligibility; forge CI alone cannot bypass the configured branch gate; no duplicate review is created; focused suites and make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-05 18:17
---
Duplicate screening dispatched (profile: deep, task remains Open)
---
author: oompah
created: 2026-08-05 18:17
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
