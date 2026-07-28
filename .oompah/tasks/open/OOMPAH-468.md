---
id: OOMPAH-468
type: feature
status: Open
priority: 1
title: Persist worker and epic contributor provider-model provenance
parent: OOMPAH-458
children: []
blocked_by:
- OOMPAH-462
- OOMPAH-463
- OOMPAH-457
labels: []
assignee: null
created_at: '2026-07-28T13:06:08.315289Z'
updated_at: '2026-07-28T18:09:12.829014Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Implementation scope

At successful worker startup/exit, persist a compact oompah.work_contributors record containing run ID, provider ID, safe provider name, resolved model ID when known, focus, source branch, source SHA, and completion time. Do not store credentials, prompts, logs, or costs. For an epic evidence revision, derive the union of contributors from its own branch work plus all child and nested-child audit/work records whose commits are contained in that revision. Preserve prior contributors when later workers add commits; discard contributors whose commits are not in the audited revision.

Tests

Cover API, ACP SDK-managed unknown model, CLI worker, retries, multiple workers on one task, shared epic children, nested epics, commits excluded from the current SHA, restart rereads, and redaction. Run focused tests and make test.

Acceptance criteria

The audit evidence collector can identify every provider/model that contributed to a task or epic revision, including unknown-model ACP contributors, without relying on transient RunningEntry state.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

