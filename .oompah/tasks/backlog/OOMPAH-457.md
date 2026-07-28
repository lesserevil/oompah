---
id: OOMPAH-457
type: epic
status: Backlog
priority: 1
title: Build the terminal-audit state model and transition coordinator
parent: null
children:
- OOMPAH-461
- OOMPAH-462
- OOMPAH-463
- OOMPAH-464
- OOMPAH-465
- OOMPAH-466
- OOMPAH-467
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-28T13:03:45.243838Z'
updated_at: '2026-07-28T13:05:09.364940Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Goal

Create the durable state-machine foundation that places an independent validation step between active work and every terminal status. This epic does not dispatch auditor agents or migrate every caller; it defines the canonical In Validation status, audit records, evidence identity, persistence, transition chaining, failure routing, restart behavior, and explicit owner override contract that later epics consume.

Required behavior

- Existing terminal records at upgrade are grandfathered, but every new Done, Merged, or Archived request is represented by a durable audit request.
- A direct Merged request without a current Done audit for the same evidence revision creates an ordered Done-then-Merged chain.
- Duplicate requests are idempotent and stale verdicts cannot change state.
- Failures route to Open, Needs CI Fix, Needs Rebase, In Review, Needs Human, or the pre-archive state using a centralized classification table.
- Owner bypasses require explicit authority and a non-empty reason.
- No verifier error or retry ceiling may fail open into a terminal state.

Constraints

Use tracker-owned oompah metadata for durable audit authority and normal comments for human-readable evidence. Preserve native Markdown state-branch behavior and GitHub/GitLab adapter compatibility. Configuration belongs in .env, not WORKFLOW.md. All code changes require tests.

Acceptance criteria

The coordinator can stage, persist, recover, pass, fail, supersede, and override target-specific terminal audits without starting a model. Its public types and methods are documented and stable enough for the auditor and integration epics. Focused tests and make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

