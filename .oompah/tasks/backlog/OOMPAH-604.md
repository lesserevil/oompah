---
id: OOMPAH-604
type: bug
status: Backlog
priority: 1
title: Allow owner overrides after terminal-audit evidence supersession
parent: OOMPAH-585
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-30T17:07:44.032640Z'
updated_at: '2026-07-30T17:07:44.032640Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Implementation scope

Repair TerminalTransitionCoordinator._override_transition_locked so an authorized owner override evaluates the current active audit request for the requested target instead of rejecting whenever any superseded historical pending-chain record has a different EvidenceFingerprint. Preserve authorization, quarantine handling, atomic metadata persistence, redaction, and fail-closed behavior for a genuinely stale current request. Relevant files: oompah/terminal_transition_coordinator.py, API/CLI terminal status routing, and terminal override tests. Reproduce using OOMPAH-589, which has multiple Done audit records after reintegration and currently returns HTTP 409 for every valid owner override. Do not hand-edit task metadata as the workaround.

Tests

Add regressions with multiple same-target audit records carrying different fingerprints: a current matching record plus superseded older records must allow the override; a mismatch against the active/current record must still reject; authorization, comment ordering, metadata quarantine, secret redaction, and concurrent update behavior must remain covered. Run focused terminal override/coordinator/interface/CLI tests and make test.

Acceptance criteria

A project owner can apply an auditable override to the current OOMPAH-589-style terminal request even when historical records use older fingerprints. Truly stale overrides remain rejected, the selected active-record rule is deterministic and documented in code, no terminal metadata is edited manually, and all override records/comments remain durable and redacted.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

