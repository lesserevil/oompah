---
id: OOMPAH-476
type: feature
status: Open
priority: 1
title: Stage API, dashboard, and CLI terminal requests through the coordinator
parent: OOMPAH-459
children: []
blocked_by:
- OOMPAH-467
- OOMPAH-475
- OOMPAH-458
labels: []
assignee: null
created_at: '2026-07-28T13:07:24.379848Z'
updated_at: '2026-07-29T01:26:31.548668Z'
work_branch: epic-OOMPAH-459
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: c5c4c9017c067d482a761e3a22a758d55e00a5cc1d2d4b3fe50959e2d4a650ec
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: d12d1eb3-f6bd-4080-bb7d-e83df55171c1
  claim_owner: bb8dc074-1652-491f-b4a8-188fd113fd9d
  claimed_at: '2026-07-29T01:26:25.167993+00:00'
  claim_expires_at: '2026-07-29T01:56:25.167993+00:00'
  retry_count: 0
  retry_after: null
oompah.agent_run_id: 69fe4064-a0b3-4763-8f40-111d66a26140
oompah.work_branch: epic-OOMPAH-459
---
## Summary

Implementation scope

Update the project-aware task PATCH/status endpoints, MCP/ACP task mutation tools, and oompah task set-status client so requests for Done, Merged, or Archived call TerminalTransitionCoordinator.request_transition. Return a response showing In Validation, requested target, and audit ID. Add explicit audit_override plus required override_reason inputs; authorize them through the coordinator owner check. Nonterminal transitions keep current behavior. Direct forge label mutations cannot express an override and must stage validation or be reverted by reconciliation. Update CLI help and errors without exposing metadata internals.

Tests

Cover each terminal target, nonterminal status, owner override, unauthorized/blank override, matching aliases, project resolution, MCP/ACP tool calls, CLI request/response, tracker errors, and backward-compatible clients that send only status. Run focused API/CLI tests and make test.

Acceptance criteria

All user- and agent-facing status interfaces stage terminal audits consistently, explicit owner overrides work, and no ordinary client can write a terminal status directly.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-29 01:26
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-29 01:26
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
