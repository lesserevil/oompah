---
id: OOMPAH-471
type: feature
status: Backlog
priority: 1
title: Collect stable evidence for Done completion audits
parent: OOMPAH-458
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-28T13:06:12.016068Z'
updated_at: '2026-07-28T13:06:12.016068Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Implementation scope

Build a read-only DoneEvidenceCollector. Resolve the correct workspace/worktree, intended work or epic branch, source SHA, base/target branch, requirements text and digest, diff/stat with bounded excerpts, changed files, commit/push status, configured test commands, latest relevant CI/test evidence, comments/handoffs, children, and contributor identities. For tasks, require committed and pushed work on the intended branch plus coverage of the description and acceptance criteria. For epics, include every direct/nested child audit result and prove required child commits are contained in the epic revision. Return typed unavailable/invalid evidence rather than guessing.

Tests

Use Git fixtures for standalone tasks, shared epic children, nested epics, clean and dirty worktrees, unpushed commits, missing branches, changed requirements, test evidence, incomplete children, and bounded/redacted prompt payloads. Run focused tests and make test.

Acceptance criteria

The auditor receives a deterministic stable snapshot sufficient to judge completion; missing or unstable evidence is explicit and cannot be mistaken for a passing case.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

