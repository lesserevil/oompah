---
id: OOMPAH-574
type: task
status: Open
priority: null
title: Rerun failed cached quality gates on explicit same-head retry
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-30T02:15:22.112289Z'
updated_at: '2026-07-30T13:31:09.136101Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: f55f5eab566970505d6992f30c8a2400036ebbf0fd17826d3c17d85fb6db4782
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 27e2d9fd-5e8b-4e8c-a9f0-2bd0df89b57b
  claim_owner: 42623072-9e4e-4956-a81f-a5c79aedc624
  claimed_at: '2026-07-30T13:31:01.545314+00:00'
  claim_expires_at: '2026-07-30T14:01:01.545314+00:00'
  retry_count: 0
  retry_after: null
oompah.agent_run_id: 43cf88a2-713b-484b-838f-e9523cae8ed9
---
## Summary

Implementation scope

Make explicit integration resubmission invalidate and re-execute cached BranchQualityGate outcomes whose prior result is failed, timed_out, or error, even when the pushed head SHA is unchanged. Continue reusing passed evidence for the exact head, keep interrupted runs non-persistent, and prevent duplicate concurrent gates for one row/head. Wire the retry intent through the task handoff/API and integration executor without weakening normal cache reuse. Relevant files: oompah/quality_gate.py, oompah/integration_queue.py, oompah/server.py, and oompah/integration_executor.py.

Tests

Add regression coverage in tests/test_quality_gate.py, tests/test_integration_queue.py, and task-handoff/integration-executor tests for explicit same-SHA retry after failure, timeout, and error; passed-result reuse; interruption behavior; and concurrent retry deduplication. Run focused tests and the configured full Makefile gate.

Acceptance criteria

An explicit retry of an unchanged blocked integration row performs a real fresh quality gate instead of immediately reusing failed evidence; successful evidence remains safely reusable and no duplicate active gate is started.
## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-30 13:31
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-30 13:31
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
