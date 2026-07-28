---
id: OOMPAH-512
type: bug
status: Open
priority: 1
title: Route managed tracker mutations through project-scoped trackers
parent: OOMPAH-511
children: []
blocked_by: []
labels:
- focus-complete:duplicate_detector
- needs:refactor
assignee: null
created_at: '2026-07-28T15:16:42.904572Z'
updated_at: '2026-07-28T15:20:26.987022Z'
work_branch: epic-OOMPAH-511
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: d32ba0bf-84f8-458c-b788-247ef7f2a525
oompah.work_branch: epic-OOMPAH-511
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
<!-- COMMENTS:END -->
