---
id: OOMPAH-492
type: bug
status: In Progress
priority: 1
title: Isolate worker-exit and epic-rebase tests from the live tracker
parent: OOMPAH-490
children: []
blocked_by:
- OOMPAH-491
labels: []
assignee: null
created_at: '2026-07-28T13:53:27.511520Z'
updated_at: '2026-07-28T14:56:49.362365Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Implementation scope

Isolate the known worker-exit and epic-rebase tests that fell through to the checkout's live tracker. In `tests/test_event_driven_loop.py`, give every `RunningEntry.issue` in `TestWorkerExitPostsEvent` a test project ID, inject a `MagicMock` tracker through `_tracker_for_project`, and mock unrelated telemetry/comment/completion side effects so the test exercises only event publication. Combine the normal and abnormal variants only if the assertion remains clear. Apply the same isolation to worker-exit tests in `tests/test_acp_billing.py` that currently spend seconds in unrelated tracker work. In `tests/test_epic_rebase_state.py::TestPersistence::test_persists_on_clear`, pass `project_id="proj-1"` to both set and clear operations so the already-injected project tracker is used. Inspect neighboring tests in these three classes for the same missing-project pattern and correct confirmed cases.

Tests

Add a fail-fast mock in each affected test that raises if `subprocess.run` or `subprocess.Popen` receives a Git push command. Assert the expected tracker interactions as well as the original event, billing, or persistence result. Run the three affected files with `--durations=20`; the two event tests and the clear-persistence test must not spawn Git and should complete without network-scale delays. Then run `make test` after the safety prerequisite is available.

Acceptance criteria

The affected tests cannot reach `orch.tracker` or the checkout's `origin`, retain their original behavioral assertions, leave no background tasks, and no individual case waits on a network timeout or retry path.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

