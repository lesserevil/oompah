---
id: OOMPAH-774
type: task
status: Done
priority: 1
title: Build replayable fixtures for historical stuck-task incidents
parent: OOMPAH-764
children: []
blocked_by:
- OOMPAH-772
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-04T13:58:46.269128Z'
updated_at: '2026-08-04T14:40:41.314422Z'
work_branch: epic-OOMPAH-764--task-OOMPAH-774
target_branch: epic-OOMPAH-764
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.target_branch: epic-OOMPAH-764
oompah.work_branch: epic-OOMPAH-764--task-OOMPAH-774
oompah.integration:
  version: 2
  state: blocked
  attempts: 1
  task_branch: epic-OOMPAH-764--task-OOMPAH-774
  base_branch: epic-OOMPAH-764
  head_sha: 73f5aeb26fc91f62a0bd9ac5ba544582b761f811
  submitted_at: '2026-08-04T14:36:07.111250+00:00'
  updated_at: '2026-08-04T14:38:38.803076+00:00'
  last_error: task worktree head e34e3c58b8f99cda238df44d1e59d816303d3112 differs
    from the published task head 73f5aeb26fc91f62a0bd9ac5ba544582b761f811; refusing
    to reset a preserved recovery snapshot
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-7cdeadbf1a77
    project_id: proj-14849f1b
    task_id: OOMPAH-774
    target_state: Done
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 0fc6c9ca3ac40030a937b55d8ef98422a002773abb3e727c17419f034b247214
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: 'Project-owner recovery for a stale integration worktree. Published head
      73f5aeb26fc91f62a0bd9ac5ba544582b761f811 was proven to descend from parent e34e3c58b8f99cda238df44d1e59d816303d3112
      and fast-forwarded exactly to epic-OOMPAH-764. Evidence: 482 tests passed; Ruff
      and diff checks clean.'
    created_at: '2026-08-04T14:40:37.752003+00:00'
    applied: false
  version: 1
  pending_chain: []
  attempt_history: []
---
## Summary

Convert the systemic incident set OOMPAH-562, OOMPAH-731, OOMPAH-732, OOMPAH-739, OOMPAH-748, OOMPAH-749, and OOMPAH-751 into durable scenario fixtures with authoritative before/after facts and expected decisions. Capture mixed integration row ordering, self-invalidating epic maintenance, benign metadata authority churn, deleted source branches after merge, nested target cycles, audit-history starvation, and advisory peer-denial poisoning. Use native Markdown tracker and temporary Git where feasible; mocks may isolate unavailable forge transport but not replace lifecycle composition. Acceptance: every incident fails against the pre-fix model or asserts its historical failure condition, replays deterministically, and is reusable by transition, evaluator, job, liveness, and scale tests.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-04 14:36
---
Implementation complete: added an immutable seven-incident corpus with authoritative before/after facts, explicit historical failure predicates, expected reason/disposition/owner/jobs/invariants, native Markdown tracker materialization, real temporary Git DAG/ref/deletion replay, stable JSON serialization, and implementation guidance. All seven historical failures replay deterministically; 482 corpus, contract, integration, standalone, handoff, audit, and epic tests pass with Ruff/diff/secret checks clean.
---
author: oompah
created: 2026-08-04 14:36
---
Added a reusable seven-incident workflow corpus with deterministic historical failure predicates, expected decisions, native Markdown task replay, real Git topology/deleted-ref replay, stable serialization, docs, and regression coverage.
---
author: oompah
created: 2026-08-04 14:38
---
Integration could not verify `epic-OOMPAH-764--task-OOMPAH-774`: task worktree head e34e3c58b8f99cda238df44d1e59d816303d3112 differs from the published task head 73f5aeb26fc91f62a0bd9ac5ba544582b761f811; refusing to reset a preserved recovery snapshot

Fetch the private branch, preserve its commits, push a clean current head, and submit it again.
---
<!-- COMMENTS:END -->
