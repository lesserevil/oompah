---
id: OOMPAH-700
type: bug
status: Open
priority: 1
title: Gate accepted submissions without a canonical task worktree
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-02T19:52:39.323644Z'
updated_at: '2026-08-02T19:56:05.186876Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Triggered by: OOMPAH-698

Production reproduction from OOMPAH-698: oompah task submit accepted a clean, pushed checkout whose branch and exact head matched the task, but the standalone review gate only searched the canonical managed worktree path and project checkout. It then moved the task to Needs CI Fix with No existing worktree matched the review branch tip, despite the submitted head already being available at origin/OOMPAH-698 and having passed the full gate in the submitting checkout.\n\nImplementation scope:\n- Make exact-head review gating independent of a surviving checkout at the submitted branch head. Materialize or snapshot the verified remote/local ref from the managed repository, or reject unsupported submission locations synchronously before returning success.\n- Preserve the immutable exact-head sandbox, lifecycle safety-head containment, clean-tree guarantees, generation cancellation, and cache semantics.\n- Do not trust a client-supplied filesystem path and do not require operators to copy an otherwise valid checkout into the private worktree directory.\n- Classify missing commit objects or unavailable remote refs as infrastructure/evidence failures, not candidate CI failures; never add ci-fix for a gate command that did not run.\n- Make retries and restart recovery idempotent.\n\nRelevant code: oompah/orchestrator.py quality-gate worktree discovery and review gate; oompah/quality_gate.py exact-head snapshot/preflight; submission validation in oompah/server.py and oompah/task_cli.py.\n\nRequired tests:\n- A valid pushed submission from a clean non-canonical checkout gates the exact remote head and creates a review.\n- A missing canonical worktree does not become Needs CI Fix when the exact commit exists in the managed repository.\n- A missing or unfetchable exact head fails closed with an actionable infrastructure classification and no ci-fix label.\n- A branch advancing during snapshot or gate remains stale and cannot create a review.\n- Repeated resubmission and restart runs at most one gate per evidence key and one review.\n\nAcceptance criteria:\n- The OOMPAH-698 reproduction completes without manually recreating its worktree.\n- Accepted submissions cannot be stranded solely by checkout-path discovery.\n- Focused tests and make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

