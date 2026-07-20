---
id: OOMPAH-256
type: task
status: In Progress
priority: null
title: Make the native Markdown tracker read and write the configured state branch
parent: OOMPAH-253
children: []
blocked_by:
- OOMPAH-255
labels:
- focus-complete:duplicate_detector
- focus-complete:test
assignee: null
created_at: '2026-07-20T16:29:29.498883Z'
updated_at: '2026-07-20T18:22:38.127834Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 14ecfd8b-205f-4e84-bec5-632598c306f5
oompah.task_costs:
  total_input_tokens: 106
  total_output_tokens: 7931
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 106
      output_tokens: 7931
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 18
    output_tokens: 5148
    cost_usd: 0.0
    recorded_at: '2026-07-20T17:38:42.081547+00:00'
  - profile: default
    model: unknown
    input_tokens: 88
    output_tokens: 2783
    cost_usd: 0.0
    recorded_at: '2026-07-20T18:05:05.492431+00:00'
---
## Summary

Scope

Extend the native Markdown tracker so a project configured with a state branch reads task files from that branch and commits task mutations only there. Code repository operations, PR branches, main, and release branches must remain independent. Preserve the legacy default-branch tracker behavior when no state branch is configured.

Implementation requirements

- Create or reuse a safe dedicated Git worktree or equivalent branch-scoped repository access for the configured state branch; do not switch the shared code checkout between branches.
- Initialize a missing configured state branch only through the explicit bootstrap or migration flow. Normal reads must not create remote branches.
- Route all tracker reads, task writes, comments, status changes, dependencies, and task discovery through the state-branch worktree after migration.
- Keep project code Git operations and state-branch writes isolated with clear locks and error handling.
- Implement pull/rebase/push conflict recovery that never uses destructive reset and provides an actionable error when recovery is impossible.

Tests

- Integration fixture with distinct main and oompah/state branches proves tracker reads and writes use state while code main remains byte-for-byte unchanged.
- Legacy fixture without state-branch configuration proves existing behavior is unchanged.
- Concurrency test covers simultaneous code fetch/rebase activity and a tracker write.
- Failure tests cover missing branch, authentication failure, and non-fast-forward state-branch push without corrupting task data.

Acceptance criteria

- Task mutations for a migrated project create commits only on its configured state branch.
- Code branch heads are not changed by normal native tracker operations.
- Legacy projects continue to work without migration.
- make test passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-20 17:36
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-20 17:36
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-20 17:36
---
Understanding: As Duplicate Investigator, I am screening OOMPAH-256 ('Make the native Markdown tracker read and write the configured state branch') for duplicates before any implementation begins. I will search existing tasks for similar topics: state branch, native markdown tracker branch isolation, git worktree tracker, and related keywords.
---
author: oompah
created: 2026-07-20 17:38
---
Focus handoff: duplicate_detector

**Outcome:** No duplicate found. OOMPAH-256 is a unique, non-duplicated task.

**Evidence reviewed:**
- Searched all .oompah/tasks/ directories (open, in-progress, in-review, done, archived) for keywords: state branch, state_branch, StateBranch, native markdown tracker, oompah_md, tracker branch, worktree tracker
- Reviewed all 8 sibling tasks in the OOMPAH-253 epic (255, 256, 257, 258, 259, 260, plus parent 253 and blocker 254)
- Checked archived tasks OOMPAH-266, OOMPAH-264 which reference state-branch but are distinct: OOMPAH-266 ('Do not auto-file epic rebase tasks for tracker-only main divergence') was archived as superseded by OOMPAH-253 — different scope (suppression of rebase tasks, not tracker read/write routing); OOMPAH-264 similar suppression scope

**Closest reviewed tasks (all confirmed distinct):**
- OOMPAH-255 (Done): adds project model fields for state branch configuration — distinct: config model only, not tracker routing
- OOMPAH-257 (Open, blocked by 256): checkpoint coalescing after state-branch support — distinct: write coalescing, not read/write routing
- OOMPAH-258 (Open, blocked by 256): bootstrap and docs — distinct: new project setup only
- OOMPAH-259 (Open, blocked by 256+257): migration of existing projects — distinct: migration path only
- OOMPAH-260 (Open): E2E validation — distinct: integration testing only

**Design artefacts available:** plans/state-branch-design.md, docs/state-branch-migration.md (created by OOMPAH-254 agent), plans/multi-branch-support.md

**Remaining work:** Full implementation of state-branch-aware reads/writes in the native Markdown tracker using a dedicated git worktree, including isolation from code branches, conflict recovery, and the required test suite (integration fixtures, legacy compat, concurrency, and failure tests).

**Recommended next focus:** feature (backend implementation of git-worktree-based tracker routing, isolation locks, conflict recovery, and tests)
---
author: oompah
created: 2026-07-20 17:38
---
Agent completed successfully in 120s (5166 tokens)
---
author: oompah
created: 2026-07-20 17:38
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 34, Tool calls: 23
- Tokens: 18 in / 5.1K out [5.2K total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 0s
- Log: OOMPAH-256__20260720T173647Z.jsonl
---
author: oompah
created: 2026-07-20 17:39
---
Focus handoff from `duplicate_detector` is complete. Queued a fresh agent run for the next applicable focus. The next agent should begin with the preceding Focus handoff comment.
---
author: oompah
created: 2026-07-20 17:43
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-20 17:43
---
Focus: Test Engineer
---
author: oompah
created: 2026-07-20 17:43
---
Understanding: As Test Engineer for OOMPAH-256, I need to write tests for the state-branch-aware native Markdown tracker. Based on the previous handoff, the duplicate detector found the feature implementation is still pending. My role is to write the test suite specified in the task: integration fixture (distinct main vs oompah/state branches), legacy fixture (no state-branch config), concurrency test, and failure tests (missing branch, auth failure, non-fast-forward push). I will first explore the codebase to understand existing test patterns and the implementation that OOMPAH-255 delivered (project model fields for state branch config).
---
author: oompah
created: 2026-07-20 17:52
---
Discovery: The implementation gap is confirmed. OOMPAH-255 added state_branch_enabled/state_branch_name/etc. to the Project model (oompah/models.py) and ProjectStore validation (oompah/projects.py). However, OompahMarkdownTracker.__init__ in oompah/oompah_md_tracker.py has NO state_branch_enabled parameter and no routing logic. The orchestrator's _new_tracker_for_project() also does not yet pass state_branch fields to the factory.

I will now write tests/test_oompah_md_tracker_state_branch.py covering: (1) integration fixture - state branch receives commits while main stays byte-for-byte unchanged; (2) legacy fixture - no regression in default-branch behavior; (3) concurrency - simultaneous code fetch and tracker write; (4) failure tests - missing branch, auth failure, non-fast-forward push recovery.

Tests that require the not-yet-implemented tracker routing API (state_branch_enabled param) will use @pytest.mark.xfail so they are: (a) informative today about what's needed, (b) auto-passing once the feature agent implements the param.
---
author: oompah
created: 2026-07-20 18:00
---
Implementation: Created tests/test_oompah_md_tracker_state_branch.py with 28 tests covering all acceptance criteria for OOMPAH-256.

**Test summary (current results):**
- 8 passed: Legacy tracker behavior verified (no regression possible)
- 1 skipped: Explicit state_branch_enabled=False test (gracefully skips when feature absent)
- 19 xfailed: Feature contracts marked as expected-fail until implementation

**Coverage provided:**
§1 Integration - task creation/status/comment/label/dependency writes only to state branch; main unchanged byte-for-byte; reads from state branch not main; shared checkout not switched
§2 Legacy - default behavior unchanged; git_sync writes to default branch; legacy projects work without migration
§3 Failures - missing branch raises actionable error; auth failure preserves task data; non-fast-forward triggers rebase+retry; rebase failure aborts cleanly; never uses reset --hard
§4 Concurrency - concurrent tracker write and code fetch succeed; concurrent writes are serialized by _write_lock
§5 Orchestrator wiring - factory call must pass state_branch_enabled=True and state_branch_name; tracker stores the params
§6 Acceptance criteria - direct tests for AC1/AC2/AC3

All 19 xfailed tests use dynamic xfail detection (inspect.signature) so they auto-convert to PASSED once the feature agent adds state_branch_enabled/state_branch_name params to OompahMarkdownTracker.__init__ and implements routing logic.
---
author: oompah
created: 2026-07-20 18:04
---
Focus handoff: test

**Outcome:** Test suite complete. Created tests/test_oompah_md_tracker_state_branch.py (1358 lines, 28 tests) covering all OOMPAH-256 acceptance criteria contracts.

**Test results:** 8 passed | 1 skipped | 19 xfailed | 0 failures. Full suite: make test passes (9540 passed).

**Files and commands:**
- New file: tests/test_oompah_md_tracker_state_branch.py
- Run with: python -m pytest tests/test_oompah_md_tracker_state_branch.py -v
- The 19 xfailed tests auto-convert to PASSED once the feature agent adds state_branch_enabled/state_branch_name params to OompahMarkdownTracker.__init__

**What was written:**
- §2 Integration: 8 tests verifying task writes go only to state branch, main unchanged byte-for-byte, reads from state branch only, shared checkout not switched to state branch
- §3 Legacy: 5 tests (all passing now) verifying no regression in default-branch behavior
- §4 Failure handling: 5 tests for missing branch, auth failure, non-fast-forward push recovery (rebase+retry), catastrophic failure (raises TrackerError, aborts rebase, no reset --hard), fetch failure
- §5 Concurrency: 2 tests for simultaneous tracker write + code fetch, and multiple concurrent writes
- §6 Orchestrator wiring: 5 tests (3 passing now for model layer, 2 xfail for factory call contract)
- §7 Acceptance criteria: 3 direct AC tests mapping to AC1/AC2/AC3

**Detection mechanism:** Uses inspect.signature to dynamically detect if OompahMarkdownTracker accepts state_branch_enabled. xfail markers are strict=False so they don't block CI.

**Remaining work (for feature agent):**
1. Add state_branch_enabled: bool = False and state_branch_name: str | None = None params to OompahMarkdownTracker.__init__ in oompah/oompah_md_tracker.py
2. Implement routing: when enabled, all reads/writes use a dedicated git worktree or git-branch-scoped access on oompah/state/<project-id>
3. Override _prepare_default_branch_for_write and _commit_and_push to target the state branch
4. Update orchestrator._new_tracker_for_project() to pass state_branch_enabled=project.state_branch_enabled and state_branch_name=project.state_branch_name for oompah_md projects
5. Implement missing-branch detection (no auto-create, raise actionable error)
6. Implement non-fast-forward push recovery (fetch + rebase + retry, never reset --hard)

**Risks:**
- Worktree isolation: the implementation must use a dedicated git worktree (not checkout) so the shared code worktree stays on main. Tests verify this via test_state_branch_worktree_does_not_switch_main_checkout.
- Concurrency: _write_lock is already an RLock; the state-branch worktree operations need to be covered by the same lock.

**Recommended next focus:** feature
---
author: oompah
created: 2026-07-20 18:05
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 0, Tool calls: 59
- Tokens: 88 in / 2.8K out [2.9K total]
- Cost: $0.0000
- Exit: terminated, Duration: 22m 0s
- Log: OOMPAH-256__20260720T174310Z.jsonl
---
author: oompah
created: 2026-07-20 18:05
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-20 18:05
---
Focus: Software Engineer
---
author: oompah
created: 2026-07-20 18:08
---
Understanding: I am the feature implementation agent for OOMPAH-256. Based on previous handoffs:

**Scope:** Extend OompahMarkdownTracker to route reads/writes through a dedicated git worktree on the state branch (oompah/state/<project-id>) when state_branch_enabled=True.

**Current state:**
- OOMPAH-255 already added state_branch_enabled/state_branch_name fields to the Project model (oompah/models.py)
- A test suite already exists (tests/test_oompah_md_tracker_state_branch.py) with 19 xfail tests waiting for the implementation
- OompahMarkdownTracker.__init__ has NO state_branch_enabled parameter yet
- orchestrator._new_tracker_for_project() doesn't pass state_branch fields

**Plan:**
1. Add state_branch_enabled/state_branch_name params to OompahMarkdownTracker.__init__
2. Add _get_state_root() method that creates/reuses a git worktree on the state branch
3. Override tasks_root property to use the state worktree path when enabled
4. Override _prepare_default_branch_for_write() and _commit_and_push() to use the state branch
5. Update _oompah_md_factory() to pass state_branch kwargs through
6. Update orchestrator._new_tracker_for_project() to pass state_branch fields for oompah_md projects

Key design constraints:
- Never switch the shared code checkout between branches (use git worktree add)
- Never auto-create the state branch during normal reads (bootstrap is explicit)
- Never use reset --hard in conflict recovery
- Raise actionable TrackerError when state branch is missing
---
author: oompah
created: 2026-07-20 18:12
---
Discovery: Key implementation decisions confirmed:

**Architecture:** Use git worktree add to create an isolated worktree for the state branch. The shared code checkout stays on main/default. All task reads/writes go through the state worktree when state_branch_enabled=True.

**Git call routing:** The _git() method needs an optional 'cwd' parameter so ALL git operations (including state worktree commits) route through self._git(). This allows test mocking via tracker._git = fake_git to intercept all calls. Tests need minor updates to their _fake_git functions to handle the cwd kwarg.

**Key methods to add:**
- OompahMarkdownTracker.__init__: state_branch_enabled, state_branch_name params
- _get_state_root(): creates/reuses git worktree, raises TrackerError if branch missing
- _state_worktree_path(): deterministic path under .git/oompah-state-worktrees/
- _prepare_state_branch_for_write(): syncs state worktree from remote (no branch check on shared checkout)
- _sync_state_branch_from_remote(): fetch + ff-only, fallback to rebase --autostash (never reset --hard)
- _commit_and_push_state_branch(): commit + push in state worktree

**Orchestrator:** _new_tracker_for_project() needs to pass state_branch_enabled and state_branch_name for oompah_md projects.

**Test updates needed:** The 5 failure test _fake_git functions need **kwargs to handle the new cwd parameter. All xfail tests should then pass.
---
author: oompah
created: 2026-07-20 18:22
---
Agent failed: Exception: Command failed with exit code 143 (exit code: 143)
Error output: Check stderr output for details. Retrying in 20s (attempt #2)
---
<!-- COMMENTS:END -->
