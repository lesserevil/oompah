---
id: OOMPAH-476
type: feature
status: Backlog
priority: 1
title: Stage API, dashboard, and CLI terminal requests through the coordinator
parent: OOMPAH-459
children: []
blocked_by:
- OOMPAH-467
- OOMPAH-475
labels: []
assignee: null
created_at: '2026-07-28T13:07:24.379848Z'
updated_at: '2026-07-28T13:09:37.967405Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
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

