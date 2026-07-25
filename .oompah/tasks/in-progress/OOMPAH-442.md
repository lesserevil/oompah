---
id: OOMPAH-442
type: bug
status: In Progress
priority: 2
title: '[backend:orchestrator] ACP worker failed issue_id=EXOCOMP-29'
parent: null
children: []
blocked_by: []
labels:
- external:github
assignee: null
created_at: '2026-07-25T02:09:54.140002Z'
updated_at: '2026-07-25T02:11:11.376190Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.external.github:
  id: lesserevil/oompah#552
  owner: lesserevil
  repo: oompah
  number: '552'
  url: https://github.com/lesserevil/oompah/issues/552
  requestor_login: NVShawn
  imported_comment_ids: []
  last_synced_status: Backlog
  last_synced_at: '2026-07-25T02:10:44.804403+00:00'
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
  last_validated_at: '2026-07-25T02:09:59.615495+00:00'
---
## Summary

### Problem

Oompah detected a backend error from `backend:orchestrator`:

> ACP worker failed issue_id=EXOCOMP-29

**Error detail:**

```
ACP worker failed issue_id=EXOCOMP-29

Traceback (most recent call last):
  File "/home/shedwards/src/oompah/oompah/projects.py", line 1985, in _create_worktree_locked
    _git_worktree_add_with_recovery(
  File "/home/shedwards/src/oompah/oompah/projects.py", line 720, in _git_worktree_add_with_recovery
    subprocess.run(
  File "/home/shedwards/.local/share/uv/python/cpython-3.12.12-linux-x86_64-gnu/lib/python3.12/subprocess.py", line 571, in run
    raise CalledProcessError(retcode, process.args,
subprocess.CalledProcessError: Command '['git', 'worktree', 'add', '-b', 'epic-EXOCOMP-4', '/home/shedwards/.oompah/worktrees/exocomp/EXOCOMP-29', 'origin/main']' returned non-zero exit status 255.

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/home/shedwards/src/oompah/oompah/projects.py", line 1995, in _create_worktree_locked
    _git_worktree_add_with_recovery(
  File "/home/shedwards/src/oompah/oompah/projects.py", line 720, in _git_worktree_add_with_recovery
    subprocess.run(
  File "/home/shedwards/.local/share/uv/python/cpython-3.12.12-linux-x86_64-gnu/lib/python3.12/subprocess.py", line 571, in run
    raise CalledProcessError(retcode, process.args,
subprocess.CalledProcessError: Command '['git', 'worktree', 'add', '/home/shedwards/.oompah/worktrees/exocomp/EXOCOMP-29', 'epic-EXOCOMP-4']' returned non-zero exit status 128.

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/home/shedwards/src/oompah/oompah/orchestrator.py", line 16364, in _run_acp_worker
    workspace_path, prompt, _attachment_paths = await loop.run_in_executor(
                                                ^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/shedwards/.local/share/uv/python/cpython-3.12.12-linux-x86_64-gnu/lib/python3.12/concurrent/futures/thread.py", line 59, in run
    result = self.fn(*self.args, **self.kwargs)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
…(truncated)
```

### Desired Behavior

The operation in `backend:orchestrator` should complete successfully, or degrade gracefully with a clear actionable message. No unhandled error should be auto-filed as a task during normal operation.

### Steps to Reproduce

1. Run oompah with `backend:orchestrator` active.
2. Let oompah execute the operation that involves `backend:orchestrator` (tracker: `github_issues:lesserevil/oompah`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior

An error occurs in `backend:orchestrator` and is recorded by oompah's `error_watcher`:

> ACP worker failed issue_id=EXOCOMP-29

### Acceptance Criteria

- The error from `backend:orchestrator` no longer occurs, or is handled gracefully so `error_watcher` is not triggered.
- The root cause is identified and resolved, or documented as a known acceptable failure with explicit handling.
- No regression: other error types continue to be reported correctly by `error_watcher`.

---
*Auto-filed by oompah error_watcher*
- source_project: global
- tracker: github_issues:lesserevil/oompah
- tracker_kind: github_issues
- fingerprint: 1c90798644935be7
- dedup_fingerprint: 1c90798644935be7
- tracker_owner: lesserevil
- tracker_repo: oompah
- source_issue: EXOCOMP-29

## External GitHub Issue

- URL: https://github.com/lesserevil/oompah/issues/552
- Requestor: @NVShawn
- Reference: lesserevil/oompah#552

## Notes


