---
id: OOMPAH-172
type: epic
status: Merged
priority: 0
title: Implement queued release-branch addendums
parent: null
children:
- OOMPAH-173
- OOMPAH-174
- OOMPAH-175
- OOMPAH-176
- OOMPAH-177
- OOMPAH-178
- OOMPAH-179
- OOMPAH-180
- OOMPAH-181
- OOMPAH-182
- OOMPAH-183
- OOMPAH-184
- OOMPAH-185
blocked_by: []
labels:
- ci-fix
assignee: null
created_at: '2026-07-13T02:35:12.892610Z'
updated_at: '2026-07-13T07:16:01.767170Z'
work_branch: epic-OOMPAH-172
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/407
review_number: '407'
merged_at: null
oompah.review_url: https://github.com/lesserevil/oompah/pull/407
oompah.review_number: '407'
oompah.work_branch: epic-OOMPAH-172
oompah.target_branch: main
oompah.agent_run_id: f808e288-e449-468b-9d16-3430c96bad7e
oompah.task_costs:
  total_input_tokens: 98
  total_output_tokens: 2787
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 98
      output_tokens: 2787
      cost_usd: 0.0
  runs:
  - profile: deep
    model: unknown
    input_tokens: 98
    output_tokens: 2787
    cost_usd: 0.0
    recorded_at: '2026-07-13T07:10:50.541327+00:00'
---
## Summary

Implement plans/release-branch-addendums.md. Replace new release-pick child tasks with durable, queueable release addendums attached to the original merged task or epic. Supported release lines are configured per project; approval of any task or epic merged to main immediately queues one addendum per selected supported release branch. Preserve an auditable task/branch view, migrate existing release-pick records safely, and retire the old child-backport workflow.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-13 02:38
---
Filed implementation children OOMPAH-173 through OOMPAH-184 from plans/release-branch-addendums.md, with scoped tests and acceptance criteria. OOMPAH-185 was immediately archived as a duplicate of OOMPAH-184.
---
author: oompah
created: 2026-07-13 07:00
---
YOLO: CI tests failed on MR #407. Fix the failing tests so this MR can merge. Do NOT rewrite the feature — only fix test failures. IMPORTANT: Paths in CI logs are not trustworthy. Run tests locally to get accurate paths and errors.
---
author: oompah
created: 2026-07-13 07:01
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-07-13 07:01
---
Focus: CI Failure Fixer
---
author: oompah
created: 2026-07-13 07:01
---
YOLO: CI tests failed on MR #407. Fix the failing tests so this MR can merge. Do NOT rewrite the feature — only fix test failures. IMPORTANT: Paths in CI logs are not trustworthy. Run tests locally to get accurate paths and errors.
---
author: oompah
created: 2026-07-13 07:02
---
Understanding: CI is failing on PR #407 (branch epic-OOMPAH-172) with 6 test failures in tests/test_granian_parity.py::TestMultipartAttachmentEndpoints. All failures show Granian returning 503 while uvicorn returns expected codes (400, 404, 500). Root cause: multipart attachment endpoints likely not registered in the Granian route set. Will investigate the granian parity test setup and the attachment route registration.
---
author: oompah
created: 2026-07-13 07:07
---
Discovery: Root cause identified. test_epic_draft_migration.py::test_migration_called_during_set_orchestrator calls server_module.set_orchestrator(mock_orch) which sets the global _orchestrator to a MagicMock, but does NOT restore it. Since tests run alphabetically, test_epic_draft_migration (e) runs before test_granian_parity (g), leaving _orchestrator polluted. The TestClient then finds an orchestrator and returns 400/404/500 instead of 503, while the Granian subprocess starts fresh with no orchestrator and correctly returns 503. Fix: save/restore _orchestrator in the epic draft migration test. The same pattern exists in test_release_pick_migration_startup.py but it runs after (r > g) so it doesn't affect these tests.
---
author: oompah
created: 2026-07-13 07:09
---
Implementation: Fixed test isolation pollution in two test files. test_epic_draft_migration.py::test_migration_called_during_set_orchestrator and test_release_pick_migration_startup.py::_run_set_orchestrator both called set_orchestrator(mock_orch) without saving/restoring server._orchestrator. This left _orchestrator set to a MagicMock for all subsequent tests in the same process. Since test_epic_draft_migration (e) runs before test_granian_parity (g), the parity tests' TestClient found a mock orchestrator instead of None, returning 400/404/500 rather than the expected 503. Fix: wrap set_orchestrator calls in try/finally that restores _orchestrator to its original value.
---
author: oompah
created: 2026-07-13 07:10
---
Verification: All 7993 tests pass locally (28 skipped, 11 pre-existing warnings). Confirmed root cause by reproducing the failure locally with test_epic_draft_migration.py run before test_granian_parity.py, then verified the fix eliminates all 6 parity test failures. Fix pushed to epic-OOMPAH-172; CI checks are now re-running on PR #407.
---
author: oompah
created: 2026-07-13 07:10
---
YOLO: merged PR #407.
---
author: oompah
created: 2026-07-13 07:10
---
Run #YOLO-reopen [attempt=YOLO-reopen, profile=deep, role=deep -> Claude/default]
- Turns: 0, Tool calls: 56
- Tokens: 98 in / 2.8K out [2.9K total]
- Cost: $0.0000
- Exit: terminated, Duration: 9m 40s
- Log: OOMPAH-172__20260713T070119Z.jsonl
---
<!-- COMMENTS:END -->
