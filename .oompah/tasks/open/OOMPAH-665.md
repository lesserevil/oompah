---
id: OOMPAH-665
type: task
status: Open
priority: null
title: Retire legacy no-auditor alerts after terminal task completion
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-31T16:04:07.401588Z'
updated_at: '2026-07-31T18:13:28.710434Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Live reproduction on 2026-07-31 after OOMPAH-653 merged: OOMPAH-644 and OOMPAH-648 are canonically Merged and have owner/pass terminal evidence, but /api/v1/state still emits terminal_audit:no_independent_candidate alerts for audit-710535de2bba and audit-db48e6cb6d3e. Replaying the authorized Merged override for OOMPAH-644 fails HTTP 409 because current evidence differs from the historical override fingerprint, so the supported API cannot retire the stale alert without re-staging an already-terminal task. Implementation scope: during observability reconciliation, treat a no-auditor record as actionable only while it still owns the task's current nonterminal human decision; retire legacy/superseded identities when a later authorized override, PASS, or canonical terminal task state proves they no longer own lifecycle authority, while preserving historical counters and audit records. Do not clear alerts merely because tracker reads fail or evidence is ambiguous. Relevant files include oompah/orchestrator.py terminal-audit observability reconciliation, terminal_transition_coordinator.py retirement metadata, terminal_audit_observability.py, restart recovery, and alert/state tests. Required deterministic tests: migrated pre-fix metadata for OOMPAH-644 override and OOMPAH-648 PASS; changed fingerprint after merge; restart; task reopened with genuinely current no-auditor decision remains actionable; quarantine/read failure fails closed; project isolation. Acceptance: the two stale alerts clear without lifecycle restaging or metadata hand edits, real current Needs Human audit alerts remain, and focused plus full Makefile gates pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

