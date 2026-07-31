---
id: OOMPAH-652
type: bug
status: Open
priority: 1
title: Isolate the full Makefile test gate from a running Oompah service
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-31T08:57:15.160957Z'
updated_at: '2026-07-31T09:03:35.133336Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 4e4f47b3a25b1f1379996386bbd81b33cb3d94161e692fcd6f77703b77da69c3
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 5c54598a-f4c6-4e83-acb1-f9e39e47689b
  claim_owner: 432b475d-ac6b-4689-b481-380c0818b1e9
  claimed_at: '2026-07-31T09:02:40.689692+00:00'
  claim_expires_at: '2026-07-31T09:32:40.689692+00:00'
  retry_count: 0
  retry_after: null
oompah.agent_run_id: 7a3f243a-c751-4a8e-a472-0fe97684375c
---
## Summary

Live reproduction on 2026-07-31: make test was run in a task worktree while the local service instance from the canonical checkout was healthy on port 8090. During the process-lifecycle portion of the suite, that unrelated service received shutdown and exited cleanly, leaving oompah not running. The gate itself later completed, so this was test cleanup escaping its ownership boundary. Implementation scope: identify the exact test/fixture/process-discovery path that can signal a sibling live service, constrain lifecycle cleanup to subprocess identities created by that test (PID plus start time/process group/session and exact temporary workspace), and add a gate-level guard so tests cannot read or act on the canonical service PID file, port, or process group. Do not mask the issue by merely restarting after tests. Relevant areas include tests marked oompah_process_global, tests/test_agent.py workspace capture, Granian/lifespan fixtures, Makefile lifecycle helpers, pytest worker isolation, and process cleanup utilities. Required regression: start a sentinel Oompah-like listener/service in a separate session with a PID/start-time identity, execute the complete process-global lifecycle test group or make test in a separate worktree, and prove the sentinel stays alive and its port remains bound; also prove each test-owned descendant is still cleaned up. Acceptance: repeated full gates cannot signal or stop a pre-existing service, all test-owned processes are reaped, focused lifecycle tests and make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-31 09:02
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-31 09:02
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-31 09:03
---
Second deterministic live reproduction: OOMPAH-649 quality gate ran python -m pytest tests/ under /home/shedwards/.oompah/worktrees/oompah/OOMPAH-649 (run.d4XOQV) while canonical service PID 3243032 was healthy in its own setsid session. Gate reached completion at about 09:00:19; immediately afterward make status reported not running, PID 3243032 was gone, no graceful shutdown lines were written, and the server could not persist the green gate callback/PR. Direct PR #615 was required to break the pass->kill->lost-callback->rerun deadlock. This strongly indicates a hard signal/cleanup escape at full-suite teardown, not ordinary application shutdown.
---
<!-- COMMENTS:END -->
