---
id: OOMPAH-267
type: bug
status: In Review
priority: 2
title: "[backend:server] Add comment API error: git commit -m Comment on oompah task\
  \ OOMPAH-266\n\n\U0001F916 Generated with https://github.com/lesserevil/oompah\n\
  \nCo-authored-by: oompah <lesserevil@users.noreply.gith..."
parent: null
children: []
blocked_by: []
labels:
- external:github
- focus-complete:duplicate_detector
- focus-complete:docs
assignee: null
created_at: '2026-07-20T16:51:11.086624Z'
updated_at: '2026-07-20T17:39:17.966699Z'
work_branch: OOMPAH-267
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/456
review_number: '456'
merged_at: null
oompah.external.github:
  id: lesserevil/oompah#453
  owner: lesserevil
  repo: oompah
  number: '453'
  url: https://github.com/lesserevil/oompah/issues/453
  requestor_login: NVShawn
  imported_comment_ids: []
  last_synced_status: Done
  last_synced_at: '2026-07-20T17:33:30.854439+00:00'
oompah.intake:
  missing_fields: []
  scope: small
  requestor_approved: false
  requestor_approved_at: null
  requestor_actor: null
  owner_override: false
  owner_override_at: null
  owner_actor: null
  decomposition_status: not_needed
  proposal_fingerprint: null
  last_validator_result: pass
  last_validated_at: '2026-07-20T16:51:30.711929+00:00'
oompah.agent_run_id: 6b4f7d8d-6902-4102-bcf2-73b16f16cfe8
oompah.task_costs:
  total_input_tokens: 172
  total_output_tokens: 13105
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 172
      output_tokens: 13105
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 9
    output_tokens: 3
    cost_usd: 0.0
    recorded_at: '2026-07-20T16:56:38.298001+00:00'
  - profile: deep
    model: unknown
    input_tokens: 22
    output_tokens: 9808
    cost_usd: 0.0
    recorded_at: '2026-07-20T17:02:49.013246+00:00'
  - profile: default
    model: unknown
    input_tokens: 89
    output_tokens: 2538
    cost_usd: 0.0
    recorded_at: '2026-07-20T17:19:53.766795+00:00'
  - profile: deep
    model: unknown
    input_tokens: 52
    output_tokens: 756
    cost_usd: 0.0
    recorded_at: '2026-07-20T17:28:57.749609+00:00'
oompah.review_url: https://github.com/lesserevil/oompah/pull/456
oompah.review_number: '456'
oompah.work_branch: OOMPAH-267
oompah.target_branch: main
---
## Summary

### Problem

Oompah detected a backend error from `backend:server`:

> Add comment API error: git commit -m Comment on oompah task OOMPAH-266

🤖 Generated with https://github.com/lesserevil/oompah

Co-authored-by: oompah <lesserevil@users.noreply.github.com>
 failed: fatal: cannot lock ref 'HEAD': is at df6135ea58c6e6bdac8de56169bce64f2ca953c8 but expected 46558c30aa2ea303df139557c48067ceee30bc53

### Desired Behavior

The operation in `backend:server` should complete successfully, or degrade gracefully with a clear actionable message. No unhandled error should be auto-filed as a task during normal operation.

### Steps to Reproduce

1. Run oompah with `backend:server` active.
2. Let oompah execute the operation that involves `backend:server` (tracker: `github_issues:lesserevil/oompah`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior

An error occurs in `backend:server` and is recorded by oompah's `error_watcher`:

> Add comment API error: git commit -m Comment on oompah task OOMPAH-266

🤖 Generated with https://github.com/lesserevil/oompah

Co-authored-by: oompah <lesserevil@users.noreply.github.com>
 failed: fatal: cannot lock ref 'HEAD': is at df6135ea58c6e6bdac8de56169bce64f2ca953c8 but expected 46558c30aa2ea303df139557c48067ceee30bc53

### Acceptance Criteria

- The error from `backend:server` no longer occurs, or is handled gracefully so `error_watcher` is not triggered.
- The root cause is identified and resolved, or documented as a known acceptable failure with explicit handling.
- No regression: other error types continue to be reported correctly by `error_watcher`.

---
*Auto-filed by oompah error_watcher*
- source_project: global
- tracker: github_issues:lesserevil/oompah
- tracker_kind: github_issues
- fingerprint: ec0c2cce6c7d7177
- dedup_fingerprint: ec0c2cce6c7d7177
- tracker_owner: lesserevil
- tracker_repo: oompah

## External GitHub Issue

- URL: https://github.com/lesserevil/oompah/issues/453
- Requestor: @NVShawn
- Reference: lesserevil/oompah#453

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-20 16:55
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-20 16:55
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-20 16:56
---
Understanding: This issue reports a git ref locking error when oompah tries to commit a comment on task OOMPAH-266. The error 'fatal: cannot lock ref HEAD: is at X but expected Y' indicates a concurrent git commit race condition — two git operations attempted to commit simultaneously and one lost the race. My role is to determine if this is a duplicate of a previously-handled issue before any implementation work begins.
---
author: oompah
created: 2026-07-20 16:56
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 0, Tool calls: 1
- Tokens: 9 in / 3 out [12 total]
- Cost: $0.0000
- Exit: terminated, Duration: 58s
- Log: OOMPAH-267__20260720T165601Z.jsonl
---
author: oompah
created: 2026-07-20 16:57
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-07-20 16:57
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-20 17:01
---
Discovery: OOMPAH-267 is NOT a duplicate.

Error in question: \`Add comment API error: git commit -m 'Comment on oompah task OOMPAH-266...' failed: fatal: cannot lock ref 'HEAD': is at df6135ea... but expected 46558c30...\`

This is a LOCAL git commit race condition — two concurrent processes both staged changes and tried to commit; the second one failed because HEAD was updated by the first between when it read HEAD and when it tried to lock it for the commit.

Candidates reviewed:
- **OOMPAH-204** (Merged, PR #416): Fixed \`_sync_from_remote()\` in oompah_md_tracker.py to add rebase fallback when ff-only fails — a different phase (push/sync), not the commit phase.
- **OOMPAH-233** (Merged): Added \`git reset --hard origin/<branch>\` as a third fallback in \`_sync_from_remote()\` — again the sync phase, not the commit phase.
- **OOMPAH-265** (In Progress): \`git push\` rejected by remote ref lock — a remote ref locking error during push, not a local HEAD lock during commit.
- **OOMPAH-268** (Open): \`git add\` failed because \`index.lock\` already exists — same root cause (concurrent git operations) but a different git operation. This is a sibling issue, not a duplicate.
- **OOMPAH-189/191** (Archived): \`Add comment/Create issue API error: Cannot sync native tracker: git merge --ff-only failed\` — diverged-branch sync failure, not a commit-phase HEAD locking error.

Key evidence OOMPAH-267 is unique:
1. The error occurs during \`git commit\`, before the push/sync phase — no existing fix covers this.
2. The \`_write_lock\` (threading.RLock) in oompah_md_tracker.py serializes within a single process, but this error suggests either multiple server processes hitting the same git repo, or asyncio.to_thread spawning threads that bypass the lock at the commit step.
3. Distinct dedup_fingerprint (ec0c2cce6c7d7177) confirms oompah has not seen this exact error before.

Relevant files for implementor:
- \`oompah/oompah_md_tracker.py\` — \`_commit_and_push()\` (line ~1040), \`_write_lock\` (threading.RLock, line 207)
- The fix likely needs to either: (a) add retry logic on \`cannot lock ref HEAD\` in \`_commit_and_push\`, or (b) identify why the per-process lock is insufficient (multiple server instances, or per-request tracker instantiation).
---
author: oompah
created: 2026-07-20 17:02
---
Focus handoff: duplicate_detector

1. **Outcome**: OOMPAH-267 is NOT a duplicate. The \`git commit failed: cannot lock ref HEAD\` error during Add comment is a new/unique failure mode — no existing task addresses it. Prior fixes (OOMPAH-204, OOMPAH-233) addressed \`_sync_from_remote()\` diverged-branch recovery (push phase), not the commit phase.

2. **Relevant files and evidence**:
   - \`oompah/oompah_md_tracker.py\` line ~1040: \`_commit_and_push()\` — performs git add, git commit, git push. The git commit at line ~1053 raises TrackerError which bubbles up and triggers error_watcher.
   - \`oompah/oompah_md_tracker.py\` line 207: \`self._write_lock = threading.RLock()\` — this is a per-instance, per-process lock. If multiple tracker instances exist (e.g., one per request) or multiple server processes share the same repo, this lock does NOT protect across them.
   - Sibling open issue: OOMPAH-268 (\`git add\` fails with index.lock exists) — same root cause, different git operation.
   - Prior merged fixes: OOMPAH-204 + OOMPAH-233 fixed \`_sync_from_remote()\` but left the commit phase unprotected.

3. **Remaining work and risks**:
   - Root cause may be per-request tracker instantiation (each request gets a new tracker object, so each has its own \`_write_lock\` — no serialization). Check how tracker is created in \`server.py\`.
   - Fix options: (a) Make tracker a singleton (one lock guards all commits), (b) add retry loop in \`_commit_and_push()\` on \`cannot lock ref HEAD\` error, (c) use a file-based lock (e.g., lockfile) for cross-process/instance serialization.
   - Test: must add regression test that triggers concurrent git commit and verifies retry/recovery.
   - Sibling OOMPAH-268 should probably be addressed in the same PR.

4. **Recommended next focus**: bug/feature implementation agent to fix \`_commit_and_push()\` for the concurrent-commit HEAD lock error.
---
author: oompah
created: 2026-07-20 17:02
---
Agent completed successfully in 344s (9830 tokens)
---
author: oompah
created: 2026-07-20 17:02
---
Run #2 [attempt=2, profile=deep, role=deep -> Claude/default]
- Turns: 59, Tool calls: 34
- Tokens: 22 in / 9.8K out [9.8K total]
- Cost: $0.0000
- Exit: normal, Duration: 5m 44s
- Log: OOMPAH-267__20260720T165724Z.jsonl
---
author: oompah
created: 2026-07-20 17:03
---
Focus handoff from `duplicate_detector` is complete. Queued a fresh agent run for the next applicable focus. The next agent should begin with the preceding Focus handoff comment.
---
author: oompah
created: 2026-07-20 17:04
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-20 17:04
---
Focus: Technical Writer
---
author: oompah
created: 2026-07-20 17:06
---
Understanding: As Technical Writer, I'm picking up from the duplicate_detector's handoff. The issue is a concurrent git commit race condition in oompah_md_tracker.py where two operations race to commit to the same git repo, causing 'cannot lock ref HEAD' errors. My job is to document the concurrency architecture and the fix approach (in plans/) so the implementation agent has a clear spec and future maintainers understand the design. I'll also check existing docs for anything that needs updating.
---
author: oompah
created: 2026-07-20 17:13
---
Discovery: Root cause identified. The race condition happens during graceful reload (make graceful / orchestrator.reload_config()). Here is the sequence:

1. reload_config() calls _project_trackers.clear()
2. An in-flight add_comment still holds the OLD OompahMdTracker instance and its _write_lock
3. A new add_comment request gets a NEW OompahMdTracker via _tracker_for_project() — a new _write_lock
4. Both instances run _commit_and_push() concurrently (each with its own lock acquired)
5. Both spawn git commit subprocesses; git's atomic ref-update catches the race with 'cannot lock ref HEAD'

The per-instance threading.RLock in _write_lock (oompah_md_tracker.py:207) serializes threads within ONE tracker instance, but does NOT protect against concurrent operations across TWO instances sharing the same git repo.

Fix options (for implementor):
- (Recommended) Replace per-instance RLock with a module-level dict keyed by resolved repo path — all tracker instances for the same git repo share one lock, eliminating the cross-instance race.
- (Simpler) Catch 'cannot lock ref HEAD' in _commit_and_push, sync from remote, and retry the commit once.

Writing plans/concurrent-git-tracker-writes.md with full design spec and updating operator docs now.
---
author: oompah
created: 2026-07-20 17:19
---
Implementation: Added three documentation artifacts:

1. plans/concurrent-git-tracker-writes.md — Design document covering root cause (two OompahMdTracker instances after graceful reload/cache clear each have their own _write_lock, allowing concurrent git commits), fix options (A: module-level lock dict keyed by repo path; B: catch-and-retry), and implementation plan with test requirements and files to change.

2. docs/native-markdown-tracker.md — New 'Concurrency and Single-Instance Requirement' section explaining the serialization model, what errors occur when violated, and how to diagnose/recover.

3. docs/operator-runbook.md — New §6.6 troubleshooting entry for concurrent git write errors with symptom, cause, immediate workaround (re-issue the failed request; kill any stale processes), and pointer to the permanent fix in plans/.

No code changed — this is documentation-only. The code fix is tracked separately and described in the plans document.
---
author: oompah
created: 2026-07-20 17:19
---
Focus handoff: docs

1. **Outcome**: Documentation phase complete. Root cause is fully documented. No code was changed.

   - Root cause: `reload_config()` calls `_project_trackers.clear()`, causing a new `OompahMdTracker` instance to be created while an in-flight write still uses the old instance. Both instances have separate `threading.RLock` objects and can run `git commit` concurrently, triggering git's atomic ref-update failure ('cannot lock ref HEAD').

2. **Relevant files, evidence, decisions**:
   - `plans/concurrent-git-tracker-writes.md` — full design doc with fix options, test requirements, files to change
   - `docs/native-markdown-tracker.md` — new Concurrency section
   - `docs/operator-runbook.md` — new §6.6 troubleshooting entry
   - Key code: `oompah/oompah_md_tracker.py` line 207 (`_write_lock = threading.RLock()`), line 1040 (`_commit_and_push`), `oompah/orchestrator.py` line 1631 (`_project_trackers.clear()`)

3. **Remaining work**:
   - Implement Option A from the design doc: add `_repo_write_locks` module-level dict + `_repo_write_lock()` factory in `oompah_md_tracker.py`, replace per-instance `threading.RLock()` with the shared lock
   - Add regression test in `tests/test_oompah_md_tracker.py` that creates two tracker instances for the same `tmp_path` and verifies they serialize concurrent `_commit_and_push` calls
   - Clear `_repo_write_locks` between tests to prevent lock leakage
   - OOMPAH-268 (index.lock sibling) is fixed by the same change

4. **Recommended next focus**: `feature` — implement the module-level lock described in `plans/concurrent-git-tracker-writes.md`
---
author: oompah
created: 2026-07-20 17:19
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 0, Tool calls: 63
- Tokens: 89 in / 2.5K out [2.6K total]
- Cost: $0.0000
- Exit: terminated, Duration: 15m 27s
- Log: OOMPAH-267__20260720T170502Z.jsonl
---
author: oompah
created: 2026-07-20 17:20
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-07-20 17:20
---
Focus: Software Engineer
---
author: oompah
created: 2026-07-20 17:21
---
Understanding: Picking up from the docs handoff. The root cause is that OompahMarkdownTracker uses a per-instance threading.RLock (_write_lock at line 207). After a graceful reload, reload_config() clears _project_trackers, and a new tracker instance is created while an in-flight write still uses the old instance. Both instances have their own lock objects, so both can run git commit concurrently, triggering 'cannot lock ref HEAD'. Fix: implement Option A from plans/concurrent-git-tracker-writes.md — add a module-level _repo_write_locks dict keyed by resolved repo path, and replace the per-instance RLock with a shared lock for each git repo. This also fixes sibling OOMPAH-268 (index.lock conflict on git add). Will add a regression test proving two instances for the same repo block each other.
---
author: oompah
created: 2026-07-20 17:27
---
Implementation: Applied Option A from plans/concurrent-git-tracker-writes.md.

Changes in oompah/oompah_md_tracker.py:
1. Added module-level _repo_write_locks dict (keyed by resolved repo path) + _repo_write_locks_guard threading.Lock() + _repo_write_lock() factory function.
2. In OompahMarkdownTracker.__init__, replaced 'self._write_lock = threading.RLock()' with 'self._write_lock = _repo_write_lock(str(self._root))'.

All tracker instances for the same git repo now share one RLock, regardless of when each instance was created. This eliminates the cross-instance race that produced 'cannot lock ref HEAD' after graceful reload (OOMPAH-267) and also fixes the sibling 'index.lock exists' error on git add (OOMPAH-268).

Tests added in tests/test_oompah_md_tracker.py (class TestRepoWriteLock, 3 tests):
- test_two_instances_same_path_share_write_lock: confirms shared identity of lock objects
- test_two_instances_different_paths_have_different_write_locks: confirms isolation across repos
- test_shared_lock_blocks_concurrent_commit_and_push: threading regression test verifying second instance waits for first to release before running git operations
---
author: oompah
created: 2026-07-20 17:28
---
Verification: All 9414 tests pass (36 skipped). New TestRepoWriteLock tests (3/3) confirm: (1) same repo → shared lock object, (2) different repos → independent locks, (3) concurrent _commit_and_push calls serialize correctly via the shared lock.
---
author: oompah
created: 2026-07-20 17:28
---
Completion: Implemented module-level per-repo write lock in oompah/oompah_md_tracker.py to eliminate the concurrent git commit race condition.

Root cause: per-instance threading.RLock did not protect across two OompahMarkdownTracker instances created when reload_config() cleared the tracker cache while an in-flight write held the old instance's lock.

Fix: _repo_write_locks dict keyed by resolved repo path ensures all instances for the same git repo share one RLock. Two commits can no longer race on 'git commit' or 'git add', eliminating both the 'cannot lock ref HEAD' error (OOMPAH-267) and the 'index.lock exists' error (OOMPAH-268).

Delivered: 2 files changed (229 insertions), 3 new tests passing, full test suite green (9414 passed). Branch OOMPAH-267 pushed to origin.
---
author: oompah
created: 2026-07-20 17:28
---
Fixed concurrent git commit race: replaced per-instance RLock with module-level per-repo lock dict in oompah_md_tracker.py. All tests pass (9414).
---
author: oompah
created: 2026-07-20 17:29
---
Run #2 [attempt=2, profile=deep, role=deep -> Claude/default]
- Turns: 0, Tool calls: 26
- Tokens: 52 in / 756 out [808 total]
- Cost: $0.0000
- Exit: terminated, Duration: 8m 42s
- Log: OOMPAH-267__20260720T172026Z.jsonl
---
<!-- COMMENTS:END -->
