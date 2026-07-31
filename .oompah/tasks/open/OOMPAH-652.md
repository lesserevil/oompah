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
updated_at: '2026-07-31T08:59:18.421418Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Live reproduction on 2026-07-31: make test was run in a task worktree while the local service instance from the canonical checkout was healthy on port 8090. During the process-lifecycle portion of the suite, that unrelated service received shutdown and exited cleanly, leaving oompah not running. The gate itself later completed, so this was test cleanup escaping its ownership boundary. Implementation scope: identify the exact test/fixture/process-discovery path that can signal a sibling live service, constrain lifecycle cleanup to subprocess identities created by that test (PID plus start time/process group/session and exact temporary workspace), and add a gate-level guard so tests cannot read or act on the canonical service PID file, port, or process group. Do not mask the issue by merely restarting after tests. Relevant areas include tests marked oompah_process_global, tests/test_agent.py workspace capture, Granian/lifespan fixtures, Makefile lifecycle helpers, pytest worker isolation, and process cleanup utilities. Required regression: start a sentinel Oompah-like listener/service in a separate session with a PID/start-time identity, execute the complete process-global lifecycle test group or make test in a separate worktree, and prove the sentinel stays alive and its port remains bound; also prove each test-owned descendant is still cleaned up. Acceptance: repeated full gates cannot signal or stop a pre-existing service, all test-owned processes are reaped, focused lifecycle tests and make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

