---
id: OOMPAH-860
type: task
status: In Progress
priority: null
title: Eliminate leaked coroutine and webhook subprocess state from exact gates
parent: OOMPAH-763
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-06T12:00:52.058327Z'
updated_at: '2026-08-06T12:44:48.310430Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Live regression at canonical OOMPAH-837 head c31b8d32a on 2026-08-06: the combined-tree gate reached 16,631 passing tests, then failed an innocent synchronous epic-rebase test when garbage collection surfaced PytestUnraisableExceptionWarning from an asyncio BaseSubprocessTransport after its event loop closed, plus 'coroutine sleep was never awaited' and unittest.mock _terminate lookup context. Root-cause inspection found two allocator leaks: tests/test_submission_fencing.py creates six raw asyncio.sleep(0) coroutine objects in worker_task fields that the tested paths never await or close; tests/test_webhooks.py::test_launch_skips_missing_gh calls real WebhookForwarder._launch with extension availability unresolved, so when gh exists it spawns a real subprocess/stderr task and returns without terminating it. Xdist/GC later attributes the warnings to unrelated tests. Implementation scope: replace unused raw coroutines with a non-awaitable sentinel/None or explicitly owned tasks with deterministic cancellation+await; make the missing-gh test mock create_subprocess_exec to raise FileNotFoundError and assert no tracked process/task; audit adjacent fixtures for identical ownership mistakes without broad production changes. Required tests: focused submission_fencing + webhooks + epic_rebase_state with RuntimeWarning and PytestUnraisableExceptionWarning promoted to errors; repeat under -n 4/loadgroup or loadscope; complete exact make test at the repaired shared head. Acceptance: no real gh process launches in the missing-extension test, no unawaited sleep coroutine remains, focused tests leave no subprocess/task/transport residue, and the exact shared gate passes without unraisable warnings.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-06 12:22
---
Focused warning-as-error validation found and repaired one adjacent environment-dependent real spawn: test_exponential_backoff_capped_at_60s exercised real _launch after a crash. It now mocks _launch while preserving/asserting the actual restart delay/attempt path. On OOMPAH-837 head ef2120815, the affected submission-fencing, webhook, and epic-rebase suites passed 265 serial and 265 xdist tests with RuntimeWarning and PytestUnraisableExceptionWarning promoted to errors; independent static review accepted. The same test-only commit is cherry-picked cleanly onto task branch epic-OOMPAH-763--task-OOMPAH-860 at 34bf3aa8; branch-specific focused validation is intentionally waiting until the active OOMPAH-837 exact gate and audit release the serialized lane.
---
author: oompah
created: 2026-08-06 12:44
---
Dedicated task branch epic-OOMPAH-763--task-OOMPAH-860 is clean and pushed at exact head 34bf3aa8a. This patch already passed 265 serial + 265 xdist warning-as-error tests in the shared OOMPAH-837 composition and that exact full gate has now passed. Branch-specific focused validation is deliberately queued behind the active independent OOMPAH-837 terminal audit; no submission until that exact-branch evidence completes.
---
<!-- COMMENTS:END -->
