---
id: OOMPAH-492
type: bug
status: Open
priority: 1
title: Isolate worker-exit and epic-rebase tests from the live tracker
parent: OOMPAH-490
children: []
blocked_by:
- OOMPAH-491
labels:
- focus-complete:duplicate_detector
- needs:test
assignee: null
created_at: '2026-07-28T13:53:27.511520Z'
updated_at: '2026-07-28T14:58:27.442458Z'
work_branch: epic-OOMPAH-490
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 89b1e6eb-aa99-4590-a53d-56b3aa990bd0
oompah.work_branch: epic-OOMPAH-490
oompah.task_costs:
  total_input_tokens: 404810
  total_output_tokens: 3022
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 404810
      output_tokens: 3022
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 404810
    output_tokens: 3022
    cost_usd: 0.0
    recorded_at: '2026-07-28T14:58:23.653994+00:00'
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

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-28 14:56
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-28 14:56
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-28 14:57
---
Understanding: Screening OOMPAH-492 for an existing task covering the same live-tracker/origin leakage in worker-exit, ACP billing, and epic-rebase tests. I will search task history and project decisions, inspect plausible candidates in full, and either archive as a confirmed duplicate or hand off for implementation without changing code.
---
author: oompah
created: 2026-07-28 14:58
---
Discovery: Duplicate screening found no confirmed duplicate. Exact searches across .oompah/tasks, docs, plans, README.md, and WORKFLOW.md found no prior task covering TestWorkerExitPostsEvent/test_acp_billing/test_persists_on_clear live-tracker leakage or the missing project_id pattern. Closest tasks reviewed in full: OOMPAH-491 adds the suite-wide Git transport barrier but explicitly identifies OOMPAH-492 as distinct targeted leak-site isolation; OOMPAH-500 is the downstream clean-checkout/no-network audit; parent OOMPAH-490 assigns this fixture-isolation scope uniquely to OOMPAH-492.
---
author: oompah
created: 2026-07-28 14:58
---
Focus handoff: duplicate_detector

1. Outcome: No confirmed duplicate; OOMPAH-492 should proceed to implementation.
2. Evidence: Searched task records and project docs for the three named test files/classes, worker-exit tests, live tracker access, project_id omissions, Git push guards, isolation, and network delays. Reviewed OOMPAH-491, OOMPAH-500, and parent OOMPAH-490 in full. OOMPAH-491 is the completed suite-wide remote barrier; OOMPAH-500 is the final audit; neither performs these targeted fixture corrections.
3. Remaining work/risks: Update only the affected and confirmed neighboring tests in tests/test_event_driven_loop.py, tests/test_acp_billing.py, and tests/test_epic_rebase_state.py; inject project-scoped mock trackers, isolate unrelated side effects, add fail-fast Git push guards, retain original assertions, run the three files with --durations=20, then make test. Watch for background tasks and any orch.tracker fallback.
4. Recommended next focus: test implementation. No code was changed or tests run during duplicate screening.
---
author: oompah
created: 2026-07-28 14:58
---
Agent completed successfully in 92s (407832 tokens)
---
author: oompah
created: 2026-07-28 14:58
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/default]
- Turns: 1, Tool calls: 14
- Tokens: 404.8K in / 3.0K out [407.8K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 32s
- Log: OOMPAH-492__20260728T145655Z.jsonl
---
author: oompah
created: 2026-07-28 14:58
---
Focus handoff from `duplicate_detector` is complete. Queued a fresh agent run for the next applicable focus. The next agent should begin with the preceding Focus handoff comment.
---
<!-- COMMENTS:END -->
