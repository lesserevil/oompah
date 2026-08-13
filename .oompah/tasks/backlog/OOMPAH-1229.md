---
id: OOMPAH-1229
type: task
status: Backlog
priority: null
title: Stabilize WebSocket completion fault-injection synchronization
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-13T09:37:50.327401Z'
updated_at: '2026-08-13T09:37:50.327401Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.create_once:
  version: 1
  project_id: oompah
  operation_kind: api_task_create
  creation_marker: 1392a045-7295-4cfd-8a46-295cbe950be9
  request_fingerprint: cc9c91296985b97656c171e2976056fe6d8bbd5cabb832cae4e84348f15dddcc
---
## Summary

Bug observed in hosted Python 3.13 gate for OOMPAH-1227 PR #856: tests/test_ws_fault_injection.py::TestLiveDashboardConvergence::test_four_completion_snapshots_converge_to_zero_running_chips intermittently records only 3 of 4 broadcast completion envelopes because the final zero-running broadcast races the assertion, while Python 3.11/3.12 pass. This is unrelated to the GitLab provider patch but makes branch gates nondeterministic. Scope: replace timing-dependent portal/broadcast observation with an explicit bounded synchronization point that proves all four broadcasts were processed before asserting; preserve the real WebSocket/broadcast/full-sync path and avoid sleeps as correctness. Add/adjust regression coverage across supported Python versions. Acceptance: the test reliably observes all four deliberately dropped completion states, then proves a full sync converges to zero chips; repeated focused runs and the hosted Makefile matrix pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

