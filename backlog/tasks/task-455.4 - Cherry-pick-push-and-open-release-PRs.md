---
id: TASK-455.4
title: 'Cherry-pick, push, and open release PRs'
status: In Progress
assignee: []
created_date: '2026-06-08 17:29'
updated_date: '2026-06-08 23:25'
labels:
  - task
dependencies:
  - TASK-455.2
  - TASK-455.3
parent_task_id: TASK-455
priority: high
ordinal: 99000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Apply the resolved commits to the target worktree, commit if needed, push the child branch, open a PR against the release branch, mark the child task In Review, and write PR metadata back to the source and child tasks.
<!-- SECTION:DESCRIPTION:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-08 22:59
---
Agent dispatched (profile: default)
---

author: oompah
created: 2026-06-08 22:59
---
Focus: Duplicate Investigator
---

author: oompah
created: 2026-06-08 22:59
---
Agent failed: RuntimeError: Codex exec exited with code 1: . Retrying in 10s (attempt #1)
---

author: oompah
created: 2026-06-08 22:59
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/default]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 19s
- Log: TASK-455.4__20260608T225911Z.jsonl
---

author: oompah
created: 2026-06-08 23:01
---
Agent dispatched (profile: standard)
---

author: oompah
created: 2026-06-08 23:03
---
Understanding: This is NOT a duplicate. After searching for cherry-pick/push/PR/backport tasks, no prior work covers this scope. Dependencies TASK-455.2 (commit resolver) and TASK-455.3 (child task + worktree creation) are both Done. Plan: (1) Add a cherry-pick executor that applies resolved commits to the child worktree; (2) Push the child branch via git; (3) Open a PR against the release branch via SCM API; (4) Mark child task In Review; (5) Write PR metadata (PR URL, PR number) back to both source and child tasks. Will extend release_pick_reconciler.py and add a new cherry_pick_pr_creator.py module.
---

author: oompah
created: 2026-06-08 23:10
---
Discovery: Key findings: (1) reconcile_release_picks() handles waiting→task_created but stops there; TASK-455.4 needs to add task_created+commits→pr_open/conflict. (2) ReviewRequest.url is the PR URL field. (3) Branch name = _sanitize_identifier(child.identifier). (4) Worktree path = project_store.worktree_path_for(project_id, child.identifier). (5) SCM provider: detect_provider(project.repo_url, access_token=project.access_token); repo slug: extract_repo_slug(project.repo_url). (6) tracker.update_issue(child_id, status=IN_REVIEW) marks In Review. Plan: create cherry_pick_pr_creator.py with apply_cherry_pick/push_branch/open_backport_pr/cherry_pick_push_and_open_pr; extend reconcile_release_picks with scm/repo params; update orchestrator to pass them.
---

author: oompah
created: 2026-06-08 23:25
---
Implementation: Created oompah/cherry_pick_pr_creator.py with: CherryPickConflictError/CherryPickError exceptions; apply_cherry_pick() (idempotent: skips if worktree already has commits ahead of target); push_branch() (git push -u --force-with-lease); open_backport_pr() (scm.create_review); cherry_pick_push_and_open_pr() orchestrator. Extended release_pick_reconciler.py: added scm/repo params to reconcile_release_picks/_reconcile_entries; new Case 2 advances task_created+commits → pr_open/conflict via _cherry_pick_and_open_pr(). Updated orchestrator._reconcile_release_picks_pass() to detect SCM provider and repo slug per project and pass to reconciler. Added 303 passing tests (42 new + 2 new orchestrator tests).
---
<!-- COMMENTS:END -->
