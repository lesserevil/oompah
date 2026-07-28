---
id: OOMPAH-474
type: feature
status: Open
priority: 1
title: Add the auditor-only structured result submission API and tool
parent: OOMPAH-458
children: []
blocked_by:
- OOMPAH-466
- OOMPAH-469
labels: []
assignee: null
created_at: '2026-07-28T13:06:14.992374Z'
updated_at: '2026-07-28T18:06:43.045138Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Implementation scope

Add an internal result endpoint/tool keyed by audit ID and task/project identity. Accept only PASS, FAIL, or NEEDS_HUMAN plus the defined failure enum, concise summary, bounded structured evidence references, and optional questions/instructions. Authenticate the call as the running auditor session, verify that session owns the audit, validate payload size and enums, reject credentials/unsafe fields, and pass the typed result to the coordinator. The tool must not accept an arbitrary status. Make repeated identical submissions idempotent and conflicting submissions reject.

Tests

Cover owner session, wrong session/task/project, expired/stale audit, malformed enum, oversized output, attempted status injection, secret-like fields, duplicate/conflicting submissions, and coordinator failure. Run API/tool tests and make test.

Acceptance criteria

An auditor can submit exactly one safe structured verdict for its assigned audit; it cannot mutate state directly or affect another audit.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

