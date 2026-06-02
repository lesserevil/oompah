---
id: TASK-414
title: Stop retrying tasks from bouncing between Open and In Progress
status: Done
assignee:
  - oompah
created_date: '2026-06-02 02:49'
updated_date: '2026-06-02 02:56'
labels:
  - bug
dependencies: []
priority: high
ordinal: 46000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Bug: tasks such as TASK-389 can bounce between Open and In Progress. Reproduction from logs: the task is dispatched and marked In Progress; the agent exits without closing; oompah schedules an escalation retry; when the retry timer fires it only searches normal dispatch candidates. Under the Backlog status workflow, In Progress is not a candidate status, so the retry releases the claim as no longer candidate. The orphan cleanup then sees an In Progress task with no running agent or retry claim and resets it back to Open, causing another dispatch loop.\n\nExpected behavior: scheduled retries must be able to resolve and dispatch the same task while it is still In Progress, using the correct project tracker. A retry should release its claim only when the task has moved to a terminal or non-retryable status. Also verify that reused per-task worktrees do not feed stale Backlog task status to the agent.\n\nImplementation guidance:\n1. Preserve project identity in retry state so multi-project retries look up the correct tracker.\n2. Update retry timer lookup so it can fetch the specific task state by id/identifier, including In Progress tasks, instead of relying only on candidate lists.\n3. Requeue retries on transient tracker errors or no available slots without losing project identity.\n4. Add regression tests that prove an In Progress retry dispatches instead of releasing the claim, and terminal/non-retryable states still release.\n5. Add coverage for any worktree metadata sync or stale-state guard added for reused worktrees.\n6. Run the full test suite before closing.
<!-- SECTION:DESCRIPTION:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Fixed retry/task-state bounce. RetryEntry now records project_id; retry timers fetch the specific task by id so In Progress retries can dispatch instead of being released as non-candidates; retry requeues preserve project/profile context; reused worktrees sync the current Backlog task markdown from the managed repo before launching an agent. Added regression coverage and ran make test: 3694 passed.
<!-- SECTION:FINAL_SUMMARY:END -->
