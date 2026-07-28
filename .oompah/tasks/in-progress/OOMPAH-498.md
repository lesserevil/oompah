---
id: OOMPAH-498
type: chore
status: In Progress
priority: 2
title: Group granular Release Delivery template assertions by behavior
parent: OOMPAH-490
children: []
blocked_by:
- OOMPAH-491
- OOMPAH-497
labels:
- focus-complete:duplicate_detector
assignee: null
created_at: '2026-07-28T13:53:33.437818Z'
updated_at: '2026-07-28T16:27:17.832317Z'
work_branch: epic-OOMPAH-490
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 3412c37e-e007-4c16-8e0d-17db4ccc714d
oompah.work_branch: epic-OOMPAH-490
oompah.task_costs:
  total_input_tokens: 825003
  total_output_tokens: 3836
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 825003
      output_tokens: 3836
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 825003
    output_tokens: 3836
    cost_usd: 0.0
    recorded_at: '2026-07-28T16:26:50.023761+00:00'
---
## Summary

Implementation scope

After canonical ownership is established, reduce granular static-source assertions remaining in `tests/test_dashboard_release_delivery_ui.py` and `tests/test_release_delivery_page.py`. Group assertions by observable contract: controls/structure, URL and refresh lifecycle, status rendering, selection/queue payload, drawer/evidence, accessibility, and XSS boundaries. Use helper assertions or table loops with descriptive failure messages instead of one test per HTML ID, CSS token, or JavaScript variable. Keep behaviorally distinct server-route tests and JavaScript function-body checks that validate data flow, generation counters, idempotency keys, safe text handling, and queue payload shape. Do not replace executable behavior tests with snapshots.

Tests

Run both files with collection and duration reporting before and after. Deliberately mutate or monkeypatch representative fixture strings in helper-level tests, where practical, to prove each grouped contract fails for the intended missing behavior. Run the release-delivery backend and E2E suites plus `make test`.

Acceptance criteria

Every listed behavior category remains protected, failures identify the missing contract, the two UI files have substantially fewer collected cases and repeated source reads, no queueing/security/accessibility behavior is lost, and all release-delivery tests pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-28 16:25
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-28 16:25
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-28 16:25
---
Understanding: I will perform duplicate screening first by searching .oompah/tasks and project docs for release-delivery/template assertion work, then read the closest candidate task descriptions and comments. I will not modify code; if no duplicate is confirmed, I will hand off with evidence and the recommended next focus.
---
author: oompah
created: 2026-07-28 16:26
---
Discovery: No confirmed duplicate. Searched .oompah/tasks (all available states), docs, plans, README.md, and WORKFLOW.md for release-delivery UI/template assertions, granular/static-source tests, and the two target files. Read OOMPAH-490, OOMPAH-491, OOMPAH-496, OOMPAH-497, OOMPAH-499, plus Release Delivery predecessors OOMPAH-200, OOMPAH-236, OOMPAH-237, and OOMPAH-252 in full via task view. OOMPAH-497 establishes canonical ownership and explicitly identifies OOMPAH-498 as the distinct follow-up; the older tasks implement production/page behavior, while OOMPAH-499 targets exact duplicates/name shadowing in other files. No code changes made.
---
author: oompah
created: 2026-07-28 16:26
---
Focus handoff: duplicate_detector\n\n1. Outcome: No confirmed duplicate; OOMPAH-498 should proceed to implementation.\n\n2. Evidence and decisions: Target files are tests/test_dashboard_release_delivery_ui.py and tests/test_release_delivery_page.py. OOMPAH-497 (Done) owns cross-file contract assignment and removed page/dialog duplicates; it explicitly leaves backlog rendering, selection, queueing, status, drawer, XSS, and refresh consolidation to OOMPAH-498. OOMPAH-200/236/237/252 provide shipped Release Delivery behavior and regression context, not this test-maintenance scope. OOMPAH-491 is unrelated pytest Git transport isolation; OOMPAH-496 and OOMPAH-499 target different test sets.\n\n3. Remaining work/risks: Baseline both target files with collection and duration reporting, group static assertions by controls/structure, URL-refresh lifecycle, status, selection/queue payload, drawer/evidence, accessibility, and XSS; retain route tests and function-body/data-flow checks. Preserve queueing, security, accessibility, generation/idempotency behavior and add descriptive failure messages; run focused release-delivery backend/E2E suites and make test.\n\n4. Recommended next focus: chore or test (implement grouped assertion helpers/table loops and verify coverage).
---
author: oompah
created: 2026-07-28 16:26
---
Agent completed successfully in 96s (828839 tokens)
---
author: oompah
created: 2026-07-28 16:26
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 19
- Tokens: 825.0K in / 3.8K out [828.8K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 36s
- Log: OOMPAH-498__20260728T162517Z.jsonl
---
author: oompah
created: 2026-07-28 16:26
---
Focus handoff from `duplicate_detector` is complete. Queued a fresh agent run for the next applicable focus. The next agent should begin with the preceding Focus handoff comment.
---
author: oompah
created: 2026-07-28 16:26
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-28 16:27
---
Focus: Maintenance Engineer
---
author: oompah
created: 2026-07-28 16:27
---
## Understanding

I'm the Maintenance Engineer taking over from the Duplicate Investigator focus. I will implement grouped assertions in the Release Delivery UI test files.

**Plan:**
1. Baseline both test files (collection count + duration)
2. Analyze granular assertions to identify patterns by contract type (controls/structure, URL-refresh lifecycle, status, selection/queue payload, drawer/evidence, accessibility, XSS)
3. Create helper assertion functions and table-loop structures with descriptive failure messages
4. Consolidate granular ID/CSS/JS-variable checks into grouped contracts
5. Preserve behavioral route tests and function-body checks
6. Verify test count reduction and duration before/after
7. Run full test suite to ensure coverage is maintained

**Target files:** tests/test_dashboard_release_delivery_ui.py, tests/test_release_delivery_page.py

**Acceptance criteria:** Reduce test count, improve maintainability, preserve all security/queueing/accessibility behavior contracts.
---
<!-- COMMENTS:END -->
