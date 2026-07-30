---
id: OOMPAH-610
type: bug
status: Backlog
priority: 1
title: Release stale claimed_issues entries when completion auditors exit
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-30T18:53:05.632137Z'
updated_at: '2026-07-30T18:53:05.632137Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Triggered by: OOMPAH-590

Implementation scope: Fix the completion-auditor worker-exit path in oompah/orchestrator.py so every auditor exit removes the issue from both state.claimed and state.claimed_issues, releases its audit branch claim, and leaves the pending terminal-audit request eligible for candidate rotation or explicit no-auditor routing after backoff. Preserve ordinary-worker and duplicate-preflight cleanup behavior. Add defensive observability or invariant coverage if needed so a stale in-memory claim cannot silently suppress an In Validation request forever.\n\nRequired tests: Add a regression reproducing an auditor that exits stalled or errored without a structured result, then prove _audit_branch_busy is false after cleanup and the next audit-lane tick either dispatches the next independent candidate or routes exhaustion to Needs Human. Cover idempotent cleanup and retain existing auditor dispatch tests. Run focused scheduler/auditor tests and make test.\n\nAcceptance criteria: No ended auditor remains in state.claimed_issues; OOMPAH-593 and equivalent In Validation tasks cannot be silently skipped after retry_after; the scheduler reaches a new auditor or an actionable terminal outcome; all relevant tests pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

