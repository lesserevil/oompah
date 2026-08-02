---
id: OOMPAH-704
type: bug
status: Backlog
priority: 1
title: Fence graceful-restart redispatch against terminal state changes
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-02T21:11:44.479316Z'
updated_at: '2026-08-02T21:11:44.479316Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Triggered by: OOMPAH-700

Production regression after OOMPAH-653: OOMPAH-700 was owner-overridden to Merged with audit override override-41c2b65a97e8 at 21:09, and an immediate task/state sweep confirmed Merged with zero pending audits. A concurrently running startup recovery then logged 'Marked OOMPAH-700 as Open for re-dispatch after restart' at 21:09:55 and regressed the terminal task to Open. Root cause is oompah/orchestrator.py::_recover_restart_issues, which loads restart_issues, clears the list, and unconditionally calls tracker.update_issue(identifier, status=OPEN) without re-reading canonical status or fencing against a terminal transition that commits after the restart snapshot was recorded. Implementation scope: make restart redispatch conditional and atomic with current task ownership/state; re-read canonical task state immediately before mutation; never reopen Merged, Archived, In Validation/terminal-audit-owned, or otherwise superseded work; preserve recovery for genuinely interrupted implementation tasks; consume stale restart records idempotently; integrate terminal audit/owner override generation or fingerprint fencing so an override concurrent with recovery always wins. Add deterministic barrier tests for an override landing after restart state load but before update, already-terminal restart records, audit-owned records, repeated startup recovery, and a normal interrupted In Progress task that should reopen exactly once. Acceptance criteria: the OOMPAH-700 sequence remains Merged across startup recovery; no terminal task can regress to Open; legitimate interrupted implementation work remains recoverable; focused orchestrator/terminal-audit tests, terminal mutation scan, and make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

