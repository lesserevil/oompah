---
id: OOMPAH-177
type: task
status: Archived
priority: 1
title: Add durable release-addendum queue claiming and recovery
parent: OOMPAH-172
children: []
blocked_by:
- OOMPAH-173
labels: []
assignee: null
created_at: '2026-07-13T02:35:49.472960Z'
updated_at: '2026-07-20T07:22:49.330273Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 5a83e7a5-fea5-4a81-9324-4798b23ac658
oompah.task_costs:
  total_input_tokens: 2191332
  total_output_tokens: 14530
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 2191332
      output_tokens: 14530
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 2191277
    output_tokens: 13049
    cost_usd: 0.0
    recorded_at: '2026-07-13T04:33:30.108447+00:00'
  - profile: standard
    model: unknown
    input_tokens: 55
    output_tokens: 1481
    cost_usd: 0.0
    recorded_at: '2026-07-13T04:46:26.922721+00:00'
---
## Summary

Read sections 4.2 and 8 of plans/release-branch-addendums.md. Implement ReleaseAddendumQueue alongside the orchestrator dispatch loop. It must scan durable open addendums, wake immediately on release_addendum_ready, claim one addendum atomically by setting in_progress plus claimed_by and lease_expires_at, and return expired leases to open. Queue keys are project ID, source identifier, and target branch; never construct an Issue or tracker child task. Tests: one claimant wins; events wake the queue; restart recovery discovers persisted open rows; expired lease recovery; blocked/merged/archived rows are not claimed; and repeated scans are idempotent. Acceptance: a persisted open addendum is independently dispatchable and recoverable without source-task status changes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-13 04:17
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-13 04:17
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-13 04:33
---
Agent completed successfully in 958s (2204326 tokens)
---
author: oompah
created: 2026-07-13 04:33
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/default]
- Turns: 1, Tool calls: 27
- Tokens: 2.2M in / 13.0K out [2.2M total]
- Cost: $0.0000
- Exit: normal, Duration: 15m 58s
- Log: OOMPAH-177__20260713T041751Z.jsonl
---
author: oompah
created: 2026-07-13 04:33
---
Agent completed without closing this issue (958s (2204326 tokens)). Escalating from 'default' to 'standard'. Retrying in 10s (1/3).
---
author: oompah
created: 2026-07-13 04:37
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-13 04:37
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-13 04:43
---
Understanding: OOMPAH-177 requires implementing ReleaseAddendumQueue as a durable claiming/recovery mechanism. No duplicate found — the previous agent run (default profile) created the implementation but didn't commit it. Continuing with commit and close.
---
author: oompah
created: 2026-07-13 04:43
---
Discovery: Implementation already complete from prior agent run. Files created/modified:\n- oompah/release_addendum_queue.py: ReleaseAddendumQueue with scan(), claim_one(), recover_expired_leases(), wait_for_work(), and event-bus integration\n- tests/test_release_addendum_queue.py: 7 tests covering all required scenarios\n- oompah/orchestrator.py: _on_release_addendum_ready, release_addendum_queue(), _recover_release_addendum_leases() integrated into tick loop\n- oompah/release_addendum_schema.py: Added IN_PROGRESS→OPEN transition for lease recovery\n- tests/test_release_addendum_schema.py: Test for new transition
---
author: oompah
created: 2026-07-13 04:45
---
Verification: All 7 tests in test_release_addendum_queue.py pass. Full test suite: 7614 passed, 28 skipped. Branch epic-OOMPAH-172 is up to date with origin.
---
author: oompah
created: 2026-07-13 04:46
---
Completion: Implemented ReleaseAddendumQueue (oompah/release_addendum_queue.py) with:\n- scan(): idempotent read of all open addendums across all source tasks\n- claim_one(): atomic open→in_progress with claimed_by + lease_expires_at; per-source threading lock prevents double-claims\n- recover_expired_leases(): returns expired in_progress rows to open\n- wait_for_work(): async event-bus integration for immediate wake on release_addendum_ready\n- Orchestrator integration: _on_release_addendum_ready(), _recover_release_addendum_leases() on every tick, release_addendum_queue() factory\nNever constructs Issue or child task. Queue key is (project_id, source_identifier, target_branch). Committed to epic-OOMPAH-172 and pushed.
---
author: oompah
created: 2026-07-13 04:46
---
Implemented ReleaseAddendumQueue with durable scan/claim/recovery, orchestrator integration, and 7 passing tests. Queue key is (project_id, source_identifier, target_branch); never constructs Issue or child task. Added IN_PROGRESS→OPEN transition to schema for lease recovery. All 7614 tests pass.
---
author: oompah
created: 2026-07-13 04:46
---
Run #2 [attempt=2, profile=standard, role=standard -> Claude/default]
- Turns: 0, Tool calls: 35
- Tokens: 55 in / 1.5K out [1.5K total]
- Cost: $0.0000
- Exit: terminated, Duration: 9m 18s
- Log: OOMPAH-177__20260713T043718Z.jsonl
---
<!-- COMMENTS:END -->
