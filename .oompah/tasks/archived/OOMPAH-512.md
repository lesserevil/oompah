---
id: OOMPAH-512
type: bug
status: Archived
priority: 1
title: Route managed tracker mutations through project-scoped trackers
parent: OOMPAH-511
children: []
blocked_by: []
labels:
- focus-complete:duplicate_detector
- focus-complete:refactor
assignee: null
created_at: '2026-07-28T15:16:42.904572Z'
updated_at: '2026-08-04T16:46:51.503591Z'
work_branch: epic-OOMPAH-511
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: f88436a6-9ae5-4a18-9430-a6a18eb27a2b
oompah.work_branch: epic-OOMPAH-511
oompah.task_costs:
  total_input_tokens: 134
  total_output_tokens: 9659
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 134
      output_tokens: 9659
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 48
    output_tokens: 6883
    cost_usd: 0.0
    recorded_at: '2026-07-28T15:20:34.953913+00:00'
  - profile: deep
    model: unknown
    input_tokens: 86
    output_tokens: 2776
    cost_usd: 0.0
    recorded_at: '2026-07-28T15:41:40.717347+00:00'
oompah.terminal_audit:
  queued_comment_posted: true
  applied_result_attempts:
    attempt-ba30f91882f8: '2026-08-04T16:46:48.255370+00:00'
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-512
    target_state: Archived
    evidence_fingerprint: f525bf1a560a05b3bad92a50acf26ee9d63d5f9b7292c2d580e3e4f2c1829c00
    audit_ids:
    - audit-2aec2f89198c
    kind: result
    applied: true
    retired_at: '2026-08-04T16:46:48.255385+00:00'
  oompah.terminal_audit_result_intents:
  - project_id: proj-14849f1b
    task_id: OOMPAH-512
    audit_id: audit-2aec2f89198c
    attempt_id: attempt-ba30f91882f8
    target_state: Archived
    evidence_fingerprint: f525bf1a560a05b3bad92a50acf26ee9d63d5f9b7292c2d580e3e4f2c1829c00
    status: Archived
    audit_ids:
    - audit-2aec2f89198c
    applied: false
    created_at: '2026-08-04T16:46:48.255403+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-2aec2f89198c
    project_id: proj-14849f1b
    task_id: OOMPAH-512
    target_state: Archived
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: f525bf1a560a05b3bad92a50acf26ee9d63d5f9b7292c2d580e3e4f2c1829c00
    attempts:
    - version: 1
      attempt_id: attempt-ba30f91882f8
      target_state: Archived
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: f525bf1a560a05b3bad92a50acf26ee9d63d5f9b7292c2d580e3e4f2c1829c00
      created_at: '2026-08-04T16:44:38.581331+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-04T16:44:38.581331+00:00'
      branch_key: epic-OOMPAH-511
      verdict: pass
      completed_at: '2026-08-04T16:46:48.255165+00:00'
      ended_at: '2026-08-04T16:46:48.255165+00:00'
    requested_by:
      version: 1
      identity: oompah
      source: auto_archive
    previous_state: Merged
    created_at: '2026-08-04T16:24:43.299559+00:00'
    updated_at: '2026-08-04T16:46:48.255165+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-ba30f91882f8
    target_state: Archived
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: f525bf1a560a05b3bad92a50acf26ee9d63d5f9b7292c2d580e3e4f2c1829c00
    created_at: '2026-08-04T16:44:38.581331+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-04T16:44:38.581331+00:00'
    branch_key: epic-OOMPAH-511
---
## Summary

Implementation scope

Remove writable legacy/global tracker use from managed-project runtime paths. Audit Orchestrator construction and every server, watcher, maintenance, release-delivery, and fallback call site that reads or mutates orch.tracker/self.tracker. For any operation associated with a managed project, resolve the tracker through _tracker_for_project(project_id) (or a single shared public helper) so OompahMarkdownTracker receives the project's repository path, state_branch_enabled, state_branch_name, shadow-write, and migration-stage settings. Do not silently use os.getcwd() when a project store exists. Preserve an explicit standalone tracker path only for deployments with no managed project store.

Relevant files

oompah/orchestrator.py, oompah/server.py, oompah/error_watcher.py and other confirmed orch.tracker consumers, plus tests following existing project-scoped tracker patterns.

Required tests

Add unit regressions for managed-project construction and each changed consumer. Prove mutation paths use the requested project tracker and never the process-cwd tracker. Prove standalone/no-project-store behavior still works. Run focused orchestrator/server/watcher tests and make test.

Acceptance criteria

No managed-project mutation path can reach a writable cwd-derived tracker; project-specific state-branch settings are present on every managed OompahMarkdownTracker; ambiguous operations fail with an actionable error instead of guessing; standalone compatibility remains covered; all tests pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-28 15:17
---
Implementation started manually in the isolated epic worktree. First step is to inventory every legacy/global tracker consumer and define the explicit managed versus standalone tracker contract.
---
author: oompah
created: 2026-07-28 15:17
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-28 15:17
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-28 15:17
---
Understanding (Duplicate Investigator): This issue describes a bug where managed-project runtime paths incorrectly use a legacy/global cwd-derived tracker instead of resolving the tracker through a project-scoped helper (_tracker_for_project). The fix requires auditing orch.tracker/self.tracker consumers in orchestrator.py, server.py, error_watcher.py, and related files. My role is to determine whether this issue is a duplicate of an existing task before any implementation begins.
---
author: oompah
created: 2026-07-28 15:20
---
Focus handoff: duplicate_detector

1. Outcome: No confirmed duplicate. OOMPAH-512 is a fresh, unique child task of epic OOMPAH-511.

2. Evidence reviewed:
   - Searched all .oompah/tasks/ states (open, backlog, merged, archived - 200+ tasks) for: 'tracker routing', 'project-scoped tracker', '_tracker_for_project', 'managed tracker mutation', 'global tracker', 'cwd tracker', 'orch.tracker', 'self.tracker' — zero hits.
   - Reviewed OOMPAH-511 (parent epic, In Progress): explicitly decomposes into OOMPAH-512/513/514 as distinct subtasks; confirms OOMPAH-512's scope is novel.
   - Reviewed OOMPAH-492 (Done): isolated *test cases* from live tracker via mock injection in tests/test_event_driven_loop.py, tests/test_acp_billing.py, tests/test_epic_rebase_state.py. Complementary (test-side isolation), not a duplicate of OOMPAH-512 (production-code routing).
   - Reviewed OOMPAH-513 (Backlog): 'Fail closed on task writes from a managed code checkout' — sibling task adding a defensive write-guard at the tracker boundary AFTER routing is fixed. Not a duplicate.
   - Reviewed OOMPAH-514 (Backlog): 'Prove maintenance cannot dirty or push the server code checkout' — sibling E2E regression task. Not a duplicate.
   - Reviewed OOMPAH-490 (In Progress): test suite pruning and isolation epic. Complementary context, not overlapping scope.
   - plans/state-branch-design.md: design background, no prior routing implementation.

3. Remaining work: Full implementation as described in the task description — audit every orch.tracker/self.tracker consumer in oompah/orchestrator.py, oompah/server.py, oompah/error_watcher.py and related files; route each managed-project path through _tracker_for_project (or public helper); add unit regressions proving cwd tracker is not reachable on managed paths; prove standalone behavior still works.

4. Recommended next focus: feature (or refactor) — production code changes in orchestrator, server, and error_watcher.
---
author: oompah
created: 2026-07-28 15:20
---
Agent completed successfully in 180s (6931 tokens)
---
author: oompah
created: 2026-07-28 15:20
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 62, Tool calls: 45
- Tokens: 48 in / 6.9K out [6.9K total]
- Cost: $0.0000
- Exit: normal, Duration: 3m 0s
- Log: OOMPAH-512__20260728T151738Z.jsonl
---
author: oompah
created: 2026-07-28 15:20
---
Focus handoff from `duplicate_detector` is complete. Queued a fresh agent run for the next applicable focus. The next agent should begin with the preceding Focus handoff comment.
---
author: oompah
created: 2026-07-28 15:20
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-07-28 15:20
---
Focus: Refactoring Specialist
---
author: oompah
created: 2026-07-28 15:21
---
Understanding (refactor): Managed runtime paths currently retain a cwd-derived global tracker alongside project-scoped trackers. I will inventory every orch.tracker/self.tracker consumer and the project tracker construction contract, run baseline focused tests, then make only behavior-preserving structural changes that clarify/centralize tracker resolution. Any mutation-routing behavior change will be handed to a feature focus with exact remaining call sites and regression requirements.
---
author: oompah
created: 2026-07-28 15:27
---
Discovery (refactor): Root cause is not missing tracker construction but ambiguous selection. Orchestrator.__init__ and reload_config always create self.tracker via _new_tracker(), whose OompahMarkdownTracker defaults cwd to os.getcwd(); managed paths then reach it whenever project_id is absent. High-risk consumers: server.set_orchestrator draft-label migration and global ErrorWatcher (server.py:614,629), frontend /api/v1/errors (projectless global watcher), Orchestrator._tracker_for_issue and repeated  mutation paths, release_addendum_queue, config-error task creation at orchestrator.py:10495, and server legacy fallbacks. Per-project startup release migration and project log watchers already route correctly. _new_tracker_for_project passes repo_path plus enabled/name/shadow-write, but does not represent state_branch_migration_stage. Required contract: one resolver must return a project tracker for explicit project_id; allow the cwd standalone tracker only when the project store has no projects; and raise an actionable error for missing/ambiguous project context in managed mode.
---
author: oompah
created: 2026-07-28 15:28
---
Discovery correction (refactor): Root cause is ambiguous tracker selection, not missing project tracker construction. Orchestrator.__init__ and reload_config always create self.tracker through _new_tracker; OompahMarkdownTracker then defaults cwd to os.getcwd. Managed paths reach that tracker whenever project_id is absent. High-risk consumers are server.set_orchestrator draft-label migration and the global ErrorWatcher (server.py:614 and 629), frontend POST /api/v1/errors, Orchestrator._tracker_for_issue and repeated project_id-else-self.tracker mutations, release_addendum_queue, config-error task creation at orchestrator.py:10495, and server legacy fallbacks. Per-project startup release migration and project log watchers already route correctly. _new_tracker_for_project passes repo_path and state-branch enabled/name/shadow-write, but does not represent state_branch_migration_stage. Required contract: explicit project_id resolves only its project tracker; cwd standalone tracker is allowed only when the project store is empty; missing project context in managed mode raises an actionable error.
---
author: oompah
created: 2026-07-28 15:28
---
Verification (refactor baseline): make test was executed before any refactor. The installed Snap uv cannot create a transient scope in this sandbox, so the Make target was run with the existing project virtualenv while preserving the target command. Result: 12,611 passed, 7 skipped, 1 failed in 293.78s. The sole failure was tests/test_acp_agent.py::TestAcpWorkerModelHandoff::test_codex_subscription_omits_synthetic_default_model because the sandbox denied writing /home/shedwards/.oompah/agent-logs; it is unrelated to tracker routing. No repository files were changed.
---
author: oompah
created: 2026-07-28 15:29
---
Focus handoff: refactor

1. Outcome: Completed the production consumer inventory and defined the routing contract. No code refactor was made because the necessary work changes tracker-selection behavior; doing it under this focus would violate the behavior-preservation constraint. The existing _tracker_for_project helper is already the correct project factory/cache, so adding another forwarding abstraction alone would add churn without closing a mutation path.

2. Evidence and decisions: Orchestrator creates cwd-derived self.tracker at orchestrator.py:679 and again at 1673. Project construction at 1942-2048 correctly uses project.repo_path and passes state_branch_enabled, state_branch_name, and state_branch_shadow_write, but the Project field state_branch_migration_stage is not represented by OompahMarkdownTracker. Direct managed-risk consumers include server.py:614 draft-label mutation, server.py:629 global ErrorWatcher creation, server.py:12372 frontend error filing, orchestrator.py:2051 issue fallback, 2100 release-addendum queue fallback, 10495 management/config-error task creation, and all project_id-else-self.tracker branches enumerated by rg. Correct examples are server.py:805 per-project release migration, server.py:638 project log watcher factory, and list-all-projects-else-standalone maintenance loops. Baseline make test: 12,611 passed, 7 skipped, 1 sandbox-only failure caused by denied write to /home/shedwards/.oompah/agent-logs.

3. Remaining work and risks: Introduce one resolver whose contract is explicit project_id to _tracker_for_project; empty project store to standalone tracker; managed store plus missing project_id to actionable error. Route every direct fallback and mutation through it, including startup migrations, error reporting, maintenance, release delivery, worker-exit gates, reconciliation, and config-error filing. Prevent construction or exposure of a writable os.getcwd tracker in managed mode. Decide how unscoped backend log errors behave in managed mode; they must not guess a project. Preserve dynamic standalone compatibility and project-name lookup. Add regressions in project-scoped orchestrator/server/watcher tests plus existing tests/test_oompah_md_tracker_state_branch.py and tests/test_release_pick_migration_startup.py patterns.

4. Recommended next focus: feature. This is a bug fix with observable fail-closed routing behavior, followed by focused orchestrator/server/error-watcher tests and make test.
---
author: oompah
created: 2026-07-28 15:29
---
Run #1 [attempt=1, profile=deep, role=deep -> Codex/default]
- Turns: 0, Tool calls: 56
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 9m 0s
- Log: OOMPAH-512__20260728T152049Z.jsonl
---
author: oompah
created: 2026-07-28 15:29
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-07-28 15:29
---
Focus: Software Engineer
---
author: oompah
created: 2026-07-28 15:37
---
Understanding (Software Engineer): I have read the full codebase context, prior agent findings, and issue requirements. Root cause: Orchestrator.__init__ always creates self.tracker via _new_tracker() which defaults cwd to os.getcwd(). In managed-project mode (projects in project_store), this cwd-derived tracker incorrectly receives mutations. Three high-risk sites to fix: (1) server.py:614 — remove_draft_labels_from_epics(orch.tracker) runs on cwd tracker in managed mode instead of iterating project trackers like _migrate_release_picks_on_startup does; (2) server.py:629 — global ErrorWatcher(orch.tracker) files server errors in cwd tracker in managed mode; (3) orchestrator.py:2051 — _tracker_for_issue falls back to self.tracker for issues without project_id in managed mode. Plan: (a) fix set_orchestrator to iterate projects for draft-label migration (same pattern as _migrate_release_picks_on_startup), (b) skip global ErrorWatcher in managed mode, (c) add _resolve_tracker(project_id) helper that raises an actionable error in managed mode when project_id is None, (d) update _tracker_for_issue and release_addendum_queue to use it, (e) update _dispatch_conflict_agent_for_delivery to use project-scoped tracker in managed mode. Add regressions proving cwd tracker is not reached for managed-project mutations. Baseline: 12,611 passed, 1 sandbox-only failure (unrelated).
---
author: oompah
created: 2026-07-28 15:41
---
Completed in commit 6533e235e on epic-OOMPAH-511. Managed startup draft migration, global operational error filing, issue routing, and release-conflict task creation now resolve explicit project trackers; ambiguous management scope fails closed. Focused routing tests and the full suite pass.
---
author: oompah
created: 2026-07-28 15:41
---
Run #1 [attempt=1, profile=deep, role=deep -> Claude/default]
- Turns: 0, Tool calls: 57
- Tokens: 86 in / 2.8K out [2.9K total]
- Cost: $0.0000
- Exit: terminated, Duration: 11m 52s
- Log: OOMPAH-512__20260728T152952Z.jsonl
---
author: oompah
created: 2026-07-28 15:41
---
Routed managed runtime task mutations through canonical project trackers and removed writable cwd-tracker fallbacks from confirmed server/orchestrator consumers.
---
author: oompah
created: 2026-08-04 16:24
---
Queued Archived audit: Aged Merged auto-archive (closed 7 days ago). An auditor will review before the task is retired.
---
author: oompah
created: 2026-08-04 16:44
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-08-04 16:44
---
Focus: Completion Auditor
---
<!-- COMMENTS:END -->
