---
id: OOMPAH-1224
type: bug
status: Ready to Integrate
priority: 2
title: '[backend:server] Issue detail API error: ProgrammingError(''Cannot operate
  on a closed database.'')'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-13T07:24:01.242921Z'
updated_at: '2026-08-21T16:40:10.959260Z'
work_branch: OOMPAH-1224
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/900
review_number: '900'
review_head: 4f8cc5f6edcf27ff6400d23f2f999da92b3d12bb
merged_at: null
oompah.lifecycle_revision: 5
oompah.last_batch:
  batch_id: batch-41327bd44d2248989351b0a98c84746f
  actor: shedwards
  committed_at: '2026-08-18T16:18:18.970327Z'
  operation:
    kind: whole_column_move
    source_status: Backlog
    scope: flat_board
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 84e39eb9bfe1e2443cafbf5328c75b63f023401957b723d17a35c9ed116de657
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-21T00:18:04.166761+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: The current task corpus contains no active (non-terminal)\
    \ tasks that describe the same underlying problem as OOMPAH-1224. The `ProgrammingError('Cannot\
    \ operate on a closed database.')` in backend:server's Issue detail API is distinct\
    \ from the archived/merged tasks in the corpus, which address terminal audit metadata\
    \ issues (OOMPAH-1015+), epic workflow coordination (OOMPAH-1000\u20131014), and\
    \ git sync problems (OOMPAH-10). OOMPAH-1224 is a fresh backend database connection\
    \ bug requiring investigation and implementation.\nI need to analyze whether OOMPAH-1224\
    \ is a duplicate of an existing task by reviewing the supplied project task corpus.\n\
    \n**Analysis of OOMPAH-1224:**\n- **Issue**: `ProgrammingError('Cannot operate\
    \ on a closed database.')` in backend:server Issue detail API\n- **Status**: Open\n\
    - **Type**: Bug, auto-filed by error_watcher\n- **Context**: Occurs when operating\
    \ on proj-14849f1b with provenanceguardedtracker\n\n**Reviewing the Task Corpus:**\n\
    \nI examined all 30 similarity candidates in the corpus. The active tasks in non-terminal\
    \ states are:\n- **OOMPAH-1224** (Open) - the current task itself\n\nAll other\
    \ candidates are in terminal states:\n- **Archived**: OOMPAH-1, OOMPAH-10, OOMPAH-1016\u2013\
    1030, OOMPAH-164\n- **Merged**: OOMPAH-1000\u20131002, OOMPAH-1004\u20131006,\
    \ OOMPAH-1010\u20131014, OOMPAH-1015\n- **Done**: OOMPAH-1003, OOMPAH-1007\n\n\
    Per the duplicate-screening rules, terminal-state tasks (Done, Merged, Archived)\
    \ are **excluded as duplicate targets** because completed tasks represent historical\
    \ context, not active problems.\n\n**Differential Analysis of Closest Candidates\
    \ (Terminal State):**\n\nEven though I cannot use them as targets, reviewing the\
    \ closest thematic candidates:\n- **OOMPAH-1015**: Malformed terminal-audit enforcement\
    \ metadata errors (pre_recovery_finalization_metadata_malformed)\n- **OOMPAH-1000\u2013\
    1014**: All focus on terminal audit, epic workflows, and workflow coordination\u2014\
    not database connection errors\n- **OOMPAH-10**: Git sync failures with rebase\
    \ logic\n\nNone describe the same root cause: a closed database connection during\
    \ the Issue detail API in backend:server.\n\n---\n\nFocus handoff: duplicate_detector\n\
    \nDuplicate preflight verdict: no_duplicate\n\nMatches: none\n\nEvidence: The\
    \ current task corpus contains no active (non-terminal) tasks that describe the\
    \ same underlying problem as OOMPAH-1224. The `ProgrammingError('Cannot operate\
    \ on a closed database.')` in backend:server's Issue detail API is distinct from\
    \ the archived/merged tasks in the corpus, which address terminal audit metada"
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 1
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: null
oompah.work_contributors:
  runs:
  - run_id: 43290814822749df83caa2eeaf2ec4ca--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-1224
    source_sha: null
    completed_at: ''
  - run_id: c8470fa192aa4f5787330252c657bf61--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-1224
    source_sha: null
    completed_at: ''
  - run_id: c8470fa192aa4f5787330252c657bf61--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-1224
    source_sha: 02bd5960434a5c65dce259894737a55ab7a8ea96
    completed_at: '2026-08-21T00:18:04.169991+00:00'
  - run_id: 3ba7779e223141169bf658070c0d7c0d--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: general
    source_branch: OOMPAH-1224
    source_sha: 4f8cc5f6edcf27ff6400d23f2f999da92b3d12bb
    completed_at: '2026-08-21T02:22:29.651486+00:00'
oompah.task_costs:
  total_input_tokens: 996
  total_output_tokens: 29305
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 996
      output_tokens: 29305
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 1341
    cost_usd: 0.0
    recorded_at: '2026-08-21T00:18:04.165948+00:00'
  - profile: default
    model: haiku
    input_tokens: 986
    output_tokens: 27964
    cost_usd: 0.0
    recorded_at: '2026-08-21T02:22:29.645862+00:00'
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: standalone
  task_branch: OOMPAH-1224
  base_branch: main
  base_sha: 859aa8a5a9fcf82063f312f6d16f8eb4ae288631
  head_sha: 4f8cc5f6edcf27ff6400d23f2f999da92b3d12bb
  submitted_at: '2026-08-21T02:20:45.121707+00:00'
  updated_at: '2026-08-21T11:00:39.066030+00:00'
  wait_reason: review_generation_requeue
  wait_generation: review:5b439c38832996983b05da448308617a4ece18543ec8d73cc8d0d546665c0770
oompah.work_branch: OOMPAH-1224
oompah.review_url: https://github.com/lesserevil/oompah/pull/900
oompah.review_number: '900'
oompah.target_branch: main
oompah.review_head: 4f8cc5f6edcf27ff6400d23f2f999da92b3d12bb
---
## Summary

### Problem
Oompah detected a backend error from `backend:server`:

> Issue detail API error: ProgrammingError('Cannot operate on a closed database.')

### Steps to Reproduce
1. Run oompah with `backend:server` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:server` and is recorded by oompah's `error_watcher`:

> Issue detail API error: ProgrammingError('Cannot operate on a closed database.')

### Expected Behavior
The operation in `backend:server` should complete successfully, or degrade gracefully with a clear actionable message. No unhandled error should be auto-filed as a task during normal operation.

### Acceptance Criteria
- The error from `backend:server` no longer occurs, or is handled gracefully so `error_watcher` is not triggered.
- The root cause is identified and resolved, or documented as a known acceptable failure with explicit handling.
- No regression: other error types continue to be reported correctly by `error_watcher`.

---
*Auto-filed by oompah error_watcher*
- source_project: proj-14849f1b
- tracker: provenanceguardedtracker
- tracker_kind: provenanceguardedtracker
- fingerprint: a55639a0defd4a2b
- dedup_fingerprint: a55639a0defd4a2b

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-20 23:00
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-20 23:01
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-20 23:01
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 41s
- Log: OOMPAH-1224__20260820T230122Z.jsonl
---
author: oompah
created: 2026-08-21 00:15
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 00:17
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-21 00:18
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 1.3K out [1.4K total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 30s
- Log: OOMPAH-1224__20260821T001715Z.jsonl
---
author: oompah
created: 2026-08-21 01:51
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-21 01:51
---
Focus: Software Engineer
---
author: oompah
created: 2026-08-21 01:52
---
Understanding: Issue detail API endpoint raises 'Cannot operate on a closed database' error in backend:server. This indicates a database connection lifecycle issue - likely a connection being closed before an async operation completes, or improper connection context management.

Plan:
1. Identify the Issue detail API endpoint in backend:server
2. Trace the database connection lifecycle
3. Find where the connection is being closed prematurely
4. Implement proper connection/transaction management
5. Add/verify test coverage
6. Verify the fix resolves the error
---
author: oompah
created: 2026-08-21 02:00
---
Discovery: Found potential root cause. The 'Cannot operate on a closed database' error likely occurs during orchestrator replacement. When a new orchestrator replaces the old one via set_orchestrator(), the old orchestrator's SQLite stores (coordination_store, integration_queue, etc.) may be garbage collected. This can cause their database connections to be implicitly closed by Python's finalizer while API threads still hold references to those stores and try to access them. The issue is that there's no explicit lifecycle management to prevent this race condition.
---
author: oompah
created: 2026-08-21 02:16
---
Implementation: Added connection recovery mechanism to SQLite stores (CoordinationStore, IntegrationQueueStore, ReviewCapacityStore, WorkflowJobStore, TaskTransitionService, and ImplementationWorkflowAdapter).

Changes:
1. Added _ensure_conn() method to all SQLite-based stores
2. Method detects closed database connections and automatically re-opens them
3. Added _ensure_conn() calls before every database operation in the critical paths

This prevents 'Cannot operate on a closed database' errors when orchestrator instances are replaced and old stores are garbage collected while API threads still hold references to them.

The fix handles the race condition described in OOMPAH-1224 where database connections can be implicitly closed by Python's garbage collector during orchestrator replacement, while active API requests still try to use those connections.
---
author: oompah
created: 2026-08-21 02:20
---
Verification: Test results show connection recovery is working correctly.

- Coordination tests: 9/9 passed
- Integration queue tests: 47/47 passed
- Connection recovery tests: Successfully re-opens closed connections and resumes database operations
- No regressions detected

Branch pushed to origin/OOMPAH-1224. Ready for integration.
---
author: oompah
created: 2026-08-21 02:21
---
Fixed 'Cannot operate on a closed database' error by adding connection recovery to SQLite stores. When orchestrator instances are replaced, old stores may be garbage collected while API threads still hold references. The fix automatically detects and recovers from closed database connections, preventing race conditions during orchestrator replacement.
---
author: oompah
created: 2026-08-21 02:22
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 257, Tool calls: 122
- Tokens: 986 in / 28.0K out [28.9K total]
- Cost: $0.0000
- Exit: normal, Duration: 31m 23s
- Log: OOMPAH-1224__20260821T015125Z.jsonl
---
author: oompah
created: 2026-08-21 06:15
---
Branch quality gate passed for `4f8cc5f6edcf27ff6400d23f2f999da92b3d12bb` using `make test` in 184.4s. Review creation may proceed.
---
author: oompah
created: 2026-08-21 16:40
---
Branch quality gate passed for `4f8cc5f6edcf27ff6400d23f2f999da92b3d12bb` using `make test` in 203.2s. Review creation may proceed.
---
<!-- COMMENTS:END -->
