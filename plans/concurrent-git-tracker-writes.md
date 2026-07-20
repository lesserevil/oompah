# Concurrent Git Tracker Writes: Race Condition and Fix

**Status:** Proposed fix — see OOMPAH-267 / OOMPAH-268  
**Root cause first seen:** OOMPAH-267 (`git commit: cannot lock ref 'HEAD'`)  
**Sibling issue:** OOMPAH-268 (`git add: index.lock already exists`)

---

## Background

The native Markdown tracker (`OompahMdTracker`) stores task state in
`.oompah/tasks` inside the managed project's git repository. Each write
operation (create, update, comment, set-status, …) ends by calling
`_commit_and_push`, which runs three git subprocesses in sequence:

```
git add .oompah/tasks
git commit -m "<subject>"
git push origin HEAD:<default-branch>
```

To prevent two threads from interleaving these subprocesses, the tracker
holds a `threading.RLock` called `_write_lock`. Every public write method
acquires this lock before touching the filesystem or running git:

```python
# oompah/oompah_md_tracker.py
def add_comment(self, identifier, text, author="oompah"):
    with self._write_lock:              # ← serializes threads on this instance
        ...
        self._commit_and_push(...)
```

This works correctly when a single `OompahMdTracker` instance is in use for a
given git repository.

---

## The Race Condition

### When it occurs

The race occurs whenever **two distinct `OompahMdTracker` instances** both try
to commit to the **same git repository** at the same time. This happens after a
graceful reload:

1. `POST /api/v1/orchestrator/restart` (or `make graceful`) triggers
   `orchestrator.reload_config()`.
2. `reload_config` calls `self._project_trackers.clear()` to flush the
   per-project tracker cache.
3. Any in-flight write (e.g., an API call to `POST /api/v1/issues/<id>/comments`)
   already holds a reference to the **old** tracker instance and its
   `_write_lock`.  
4. The next write request calls `_tracker_for_project()`, which finds the cache
   empty and creates a **new** tracker instance with a **new** `_write_lock`.
5. Both old and new instances have their respective locks acquired and both
   launch `git commit` subprocesses concurrently.
6. Git's atomic ref-update fails for the second subprocess:

   ```
   fatal: cannot lock ref 'HEAD': is at df6135ea... but expected 46558c30...
   ```

   The "expected" hash is what the losing process read at step 3 or 4;
   "is at" is the hash written by the winning process's commit.

### Why the lock doesn't help

`threading.RLock` serializes threads that share the **same lock object**.
Two different `OompahMdTracker` instances have **different** lock objects, so
they don't serialize each other — both believe they are the exclusive writer.

### Sibling issue: index.lock

OOMPAH-268 exhibits the same root cause at an earlier stage. When two
concurrent `git add` subprocesses run, the first creates `.git/index.lock` and
the second fails with:

```
fatal: Unable to create '.git/index.lock': File exists.
```

---

## Scope and Constraints

| What it IS | What it is NOT |
|---|---|
| A within-process race between two tracker instances | A cross-process race (uvicorn runs workers=1 by default and the `workers` parameter is not passed to uvicorn.Config, so it cannot create multiple worker processes) |
| Triggered by graceful reload (reload_config → cache clear) | Triggered by normal steady-state operation |
| Reproducible with concurrent API requests immediately after a graceful reload | A design flaw in the `_write_lock` concept for single-instance use |

---

## Fix Options

### Option A (Recommended): Module-level lock keyed by repo path

Replace the per-instance `threading.RLock` with a **module-level dict** that
maps each resolved repo path to a single shared lock:

```python
# oompah/oompah_md_tracker.py (new module-level code)
import threading
from pathlib import Path

_repo_write_locks: dict[str, threading.RLock] = {}
_repo_write_locks_guard = threading.Lock()


def _repo_write_lock(repo_path: str) -> threading.RLock:
    """Return the shared write lock for the given resolved repo path.

    All OompahMdTracker instances that point to the same git repository
    share the same RLock, regardless of when each instance was created.
    This prevents concurrent git commits across tracker instances created
    during graceful reload.
    """
    with _repo_write_locks_guard:
        if repo_path not in _repo_write_locks:
            _repo_write_locks[repo_path] = threading.RLock()
        return _repo_write_locks[repo_path]
```

And in `__init__`:

```python
def __init__(self, ...):
    ...
    self._root = Path(cwd or os.getcwd()).resolve()
    # Shared per-repo lock — all tracker instances for the same git repo
    # serialize through this lock, even across graceful reloads.
    self._write_lock = _repo_write_lock(str(self._root))
```

**Pros:**  
- Eliminates the cross-instance race entirely at the serialization layer.  
- Handles both the graceful-reload scenario and any future multi-instance case.  
- No change to the calling code or the error-handling path.

**Cons:**  
- Module-level mutable state; needs care in tests (clear `_repo_write_locks`
  between test runs that create multiple tracker instances for `tmp_path`).

### Option B: Catch and retry in `_commit_and_push`

Catch the `cannot lock ref 'HEAD'` and `index.lock exists` errors and convert
them to retryable failures:

```python
def _commit_and_push(self, subject: str) -> None:
    ...
    try:
        self._git(["commit", "-m", message], check=True)
    except TrackerError as exc:
        if "cannot lock ref" in str(exc) or "index.lock" in str(exc):
            # Another tracker instance raced and committed first.
            # Re-sync from the new HEAD and try once more.
            branch = self.default_branch or self._infer_default_branch() or "main"
            self._sync_from_remote(branch)
            self._git(["add", TASKS_DIR], check=True)
            self._git(["commit", "-m", message], check=True)
        else:
            raise
```

**Pros:**  
- Minimal change; handles the race symptomatically.  
- Does not require module-level state.

**Cons:**  
- Still allows the race; it just recovers from it.  
- The re-add + commit after `_sync_from_remote` may silently drop one of the
  two concurrent changes if they touched the same task file.  
- Does not fix the `index.lock` sibling issue (git add fails before commit).

### Option C: Drain in-flight operations before invalidating cache

Before clearing `_project_trackers`, wait for in-flight operations to complete.
This is complex to implement correctly (requires reference counting or a
per-tracker shutdown protocol) and is not recommended over Option A.

---

## Recommended Implementation Plan

1. Implement **Option A** (module-level lock dict) in `oompah/oompah_md_tracker.py`.  
2. Add a regression test in `tests/test_oompah_md_tracker.py` that creates two
   `OompahMdTracker` instances for the same `tmp_path` and verifies they block
   each other on concurrent `_commit_and_push` calls (i.e., one must wait for
   the other to release the shared lock before proceeding).  
3. Update the test helpers to clear `_repo_write_locks` between test runs to
   prevent lock leakage across tests.
4. Address OOMPAH-268 (`index.lock`) in the same PR: the same module-level lock
   serializes `git add` too, since `git add` is also inside the `_write_lock`
   scope.

---

## Files to Change

| File | Change |
|---|---|
| `oompah/oompah_md_tracker.py` | Add `_repo_write_locks` dict + `_repo_write_lock()` factory; replace `threading.RLock()` with `_repo_write_lock(str(self._root))` in `__init__` |
| `tests/test_oompah_md_tracker.py` | Add regression test for two-instance concurrent commit; add teardown that clears `_repo_write_locks` |

---

## Related Issues

| Issue | Status | Relationship |
|---|---|---|
| OOMPAH-204 | Merged | Fixed `_sync_from_remote` ff-only fallback (push phase, not commit phase) |
| OOMPAH-233 | Merged | Added `git reset --hard` as third fallback in `_sync_from_remote` |
| OOMPAH-265 | In Progress | Remote ref lock during push — different phase, same concurrent-git theme |
| OOMPAH-268 | Open | `git add` fails with `index.lock` — same root cause, earlier in the sequence |
