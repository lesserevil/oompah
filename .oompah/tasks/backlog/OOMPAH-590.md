---
id: OOMPAH-590
type: bug
status: Backlog
priority: 1
title: Retry terminal audits after auditor launch or transport failure
parent: OOMPAH-585
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-30T14:14:22.194798Z'
updated_at: '2026-07-30T14:14:22.194798Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Implementation scope

Treat completion-auditor launch, malformed endpoint, transport, timeout, and provider-session failures as recoverable audit-attempt outcomes. Persist a safe failure classification, release the candidate claim, retry with bounded backoff and the next eligible independent candidate, and prevent duplicate concurrent attempts for one audit/evidence fingerprint. Preserve terminal-state idempotency and audit history. Relevant files include oompah/auditor_dispatch.py, oompah/terminal_transition_coordinator.py, orchestrator audit dispatch/reconciliation, and state metadata.

Tests

Cover launch exception, transport exception, timeout, next-candidate fallback, exhausted candidates, restart recovery, duplicate tick coalescing, and successful later completion. Run focused terminal/auditor tests and make test.

Acceptance criteria

A transient auditor-session failure cannot leave a request silently Pending forever; the request either passes on retry or reaches an explicit actionable exhausted/needs-human state.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

