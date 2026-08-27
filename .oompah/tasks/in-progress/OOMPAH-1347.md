---
id: OOMPAH-1347
type: feature
status: In Progress
priority: 2
title: Add Pi AI provider transport
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels:
- human-only
assignee: null
created_at: '2026-08-27T17:12:13.126258Z'
updated_at: '2026-08-27T18:31:27.609358Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.create_once:
  version: 1
  project_id: proj-14849f1b
  operation_kind: api_task_create
  creation_marker: pi-ai-provider-implementation-v1
  request_fingerprint: ce1a08358047a0fa88eef9a742e9f66ca46a3c65f78b4c923dd37987e5035043
oompah.lifecycle_revision: 1
---
## Summary

Implement the accepted design in plans/pi-ai-provider.md on an isolated branch. Add a provider backend named pi that uses the pinned @earendil-works/pi-ai framework without pi-coding-agent or pi-agent-core. Oompah must retain its current agent loop and guarded Python tool execution. Add a versioned bounded JSONL Node bridge, provider/model/auth wiring, process cancellation and provider-contact accounting, usage/cost propagation, UI/registry integration, focused unit and integration tests using a fake transport/provider, and operator documentation. Preserve exact-task capabilities, read-only auditor/duplicate policy, isolated rebase policy, secret redaction, and existing Claude/Codex/OpenCode behavior. Acceptance: pi appears as a selectable provider backend, health checks and one multi-turn tool flow work, malformed/oversized frames and cancellation fail closed, no Pi coding-agent resources or tools load, focused tests and make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-27 17:34
---
Implementation started on branch OOMPAH-1347-pi-ai-provider.
---
author: oompah
created: 2026-08-27 18:31
---
Implemented initial Pi provider transport on branch OOMPAH-1347-pi-ai-provider and opened PR #966. The implementation uses @earendil-works/pi-ai only; Oompah retains its existing agent loop and guarded Python tool executor. Added pinned Node bridge, provider transport fields/API/UI, health probe, exact provider/model mapping, usage/cost propagation, bounded JSONL framing, cancellation/process cleanup, and tests. Focused checks passed: 779 Python tests plus 3 Node tests. CI pending.
---
<!-- COMMENTS:END -->
