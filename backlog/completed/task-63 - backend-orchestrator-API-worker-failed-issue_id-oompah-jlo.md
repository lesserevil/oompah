---
id: TASK-63
title: '[backend:orchestrator] API worker failed issue_id=oompah-jlo'
status: Done
assignee: []
created_date: 2026-03-08 02:34
updated_date: 2026-03-08 02:38
labels:
- archive:yes
- needs:backend
- bug
- beads-migrated
dependencies: []
priority: medium
ordinal: 1000
type: bug
beads:
  id: oompah-i9v
  state: closed
  parent_id: null
  dependencies: []
  branch_name: oompah-i9v
  target_branch: null
  url: null
  created_at: '2026-03-08T02:34:39Z'
  updated_at: '2026-03-08T02:38:36Z'
  closed_at: '2026-03-08T02:38:36Z'
---
## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
API worker failed issue_id=oompah-jlo

Traceback (most recent call last):
  File "/Users/shedwards/src/oompah/oompah/projects.py", line 249, in create_worktree
    subprocess.run(
    ~~~~~~~~~~~~~~^
        ["git", "worktree", "add", "-b", branch_name, wt_path, base],
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    ...<4 lines>...
        timeout=30,
        ^^^^^^^^^^^
    )
    ^
  File "/Users/shedwards/.local/share/uv/python/cpython-3.13.12-macos-aarch64-none/lib/python3.13/subprocess.py", line 577, in run
    raise CalledProcessError(retcode, process.args,
                             output=stdout, stderr=stderr)
subprocess.CalledProcessError: Command '['git', 'worktree', 'add', '-b', 'oompah-jlo', '/Users/shedwards/.oompah/worktrees/oompah/oompah-jlo', 'origin/main']' returned non-zero exit status 255.

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/Users/shedwards/src/oompah/oompah/projects.py", line 262, in create_worktree
    subprocess.run(
    ~~~~~~~~~~~~~~^
        ["git", "worktree", "add", wt_path, branch_name],
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
        cwd=project.repo_path,
        ^^^^^^^^^^^^^^^^^^^^^^
        capture_output=True, text=True, check=True, timeout=30,
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/Users/shedwards/.local/share/uv/python/cpython-3.13.12-macos-aarch64-none/lib/python3.13/subprocess.py", line 577, in run
    raise CalledProcessError(retcode, process.args,
                             output=stdout, stderr=stderr)
subprocess.CalledProcessError: Command '['git', 'worktree', 'add', '/Users/shedwards/.oompah/worktrees/oompah/oompah-jlo', 'oompah-jlo']' returned non-zero exit status 128.

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/Users/shedwards/src/oompah/oompah/orchestrator.py", line 1112, in _run_api_worker
    workspace_path, focus, prompt = await loop.run_in_executor(
                                    ^^^^^^^^^^^^^^^^^^^^^^^^^^^
        self._tick_pool, _setup_worker
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/Users/shedwards/.local/share/uv/python/cpython-3.13.12-macos-aarch64-none/lib/python3.13/concurrent/futures/thread.py", line 59, in run
    result = self.fn(*self.args, **self.kwargs)
  File "/Users/shedwards/src/oompah/oompah/orchestrator.py", line 1081, in _setup_worker
    wp = self.project_store.create_worktree(
        issue.project_id, issue.identifier)
  File "/Users/shedwards/src/oompah/oompah/projects.py", line 269, in create_worktree
    raise ProjectError(f"git worktree add failed: {stderr2}")
oompah.projects.ProjectError: git worktree add failed: Preparing worktree (checking out 'oompah-jlo')
fatal: Unable to create '/Users/shedwards/src/oompah/.git/worktrees/oompah-jlo1/index.lock': File exists.

Another git process seems to be running in this repository, e.g.
an editor opened by 'git commit'. Please make sure all processes
are terminated then try again. If it still fails, a git process
may have crashed in this repository earlier:
remove the file manually to continue.
<!-- SECTION:DESCRIPTION:END -->

## Comments
<!-- COMMENTS:BEGIN -->
<!-- COMMENT:BEGIN -->
index: 9af0742c-976a-4071-969c-e6788e5cc764
author: oompah
created: 2026-03-08T02:38:06Z

Agent dispatched (profile: default)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: a89f908a-0bbc-4b85-a631-60b044d9a136
author: oompah
created: 2026-03-08T02:38:07Z

Agent dispatched (profile: default)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 7fd51331-beda-4455-8e6f-a7b229347bc2
author: oompah
created: 2026-03-08T02:38:09Z

Focus: Bug Investigator & Fixer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 47e71887-1841-47cf-afcc-6926f4b6976b
author: Shawn Edwards
created: 2026-03-08T02:38:12Z

I understand the issue: the API worker failed with issue_id=oompah-jlo. My plan is to investigate the root cause of the failure and implement the necessary fixes.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: ed07e040-9ef6-48a6-95a1-a3398379a40e
author: oompah
created: 2026-03-08T02:38:12Z

Agent failed: git worktree add failed: Preparing worktree (checking out 'oompah-i9v')
fatal: '/Users/shedwards/.oompah/worktrees/oompah/oompah-i9v' already exists. Retrying in 10s (attempt #1)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: c8dbed8b-cc53-4371-a83c-b97a58b214ba
author: oompah
created: 2026-03-08T02:38:24Z

Agent dispatched (profile: default)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 5e32fa16-7fb1-4755-9bc9-0b817f7f79af
author: oompah
created: 2026-03-08T02:38:26Z

Focus: Bug Investigator & Fixer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 81214282-c65d-4cfc-a77f-6e59908cecea
author: Shawn Edwards
created: 2026-03-08T02:38:29Z

I understand the issue: the API worker failed with issue_id=oompah-jlo. My plan is to investigate the root cause of the failure and implement the necessary fixes.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: f18dbc45-c0b9-4abb-ac6d-61bf9ef5e535
author: Shawn Edwards
created: 2026-03-08T02:38:30Z

Found the bug: the issue is caused by a race condition in the data fetching logic. The  command fails due to a lock file existing in the repository. To fix this, we need to remove the lock file before running the command.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 699b1cba-ce1c-455a-bc90-0ff4a5019dae
author: oompah
created: 2026-03-08T02:38:37Z

Agent completed successfully in 31s (37625 tokens)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 491900d1-2525-498f-9532-5fc230f27a3b
author: oompah
created: 2026-03-08T02:38:42Z

Agent completed successfully in 18s (25351 tokens)
<!-- COMMENT:END -->
<!-- COMMENTS:END -->
