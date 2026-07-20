# Native Markdown Tracker

The native oompah Markdown tracker stores task state in the managed project
repository under `.oompah/tasks`. It is selected with `tracker_kind=oompah_md`
on a managed project, and new projects created from the Projects page or
`POST /api/v1/projects` use it by default.

Use this tracker when you want task data to be visible in git without using
GitHub Issues or a third-party task manager. Oompah is the only intended writer.
Humans can inspect the files on the default branch.

## Repository Layout

Each task is a Markdown file with YAML front matter:

```text
.oompah/tasks/
  proposed/
  backlog/
  open/
  in-progress/
  needs-human/
  in-review/
  done/
  merged/
  archived/
```

Example:

```markdown
---
id: REPO-12
type: task
status: Open
priority: 2
title: Add release branch picker
parent: REPO-7
children: []
blocked_by: []
labels:
  - ui
created_at: "2026-06-19T12:00:00Z"
updated_at: "2026-06-19T12:00:00Z"
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Add the release branch picker to the task editor.

## Acceptance Criteria

- [ ] The task editor can select a target branch.

## Notes
```

Task IDs default to the repository directory name as a prefix, for example
`TRICKLE-1`. A project can set `.oompah/tasks/config.yml` with:

```yaml
task_prefix: OVA
```

## Write Behavior

When git sync is enabled, oompah writes task changes only from the managed
source checkout on the project's default branch. Before a write it pulls the
default branch. After a write it commits `.oompah/tasks` and pushes back to
`origin`.

Set `OOMPAH_MD_TRACKER_GIT_SYNC=0` only for tests or one-off local experiments.
With sync disabled, oompah writes files without committing or pushing them.

Native tracker projects use `.oompah/tasks` as the task source of truth.

## Concurrency and Single-Instance Requirement

Oompah serializes all git writes through a per–git-repository lock. Every
write operation (create, update, comment, set-status, …) acquires this lock
before touching the filesystem or running `git add` / `git commit` /
`git push`. This prevents two concurrent API requests from interleaving git
subprocesses against the same repository.

**Do not run multiple oompah server instances pointing at the same managed
repository.** The lock is in-process only. Two separate oompah processes (or
two uvicorn workers, if the `workers` parameter were ever passed through) would
each have their own lock object and could race on git commits, producing errors
like:

```
fatal: cannot lock ref 'HEAD': is at <sha> but expected <sha>
fatal: Unable to create '.git/index.lock': File exists.
```

The default configuration (`OOMPAH_SERVER_WORKERS` unset, uvicorn backend) runs
a single process with a single in-process lock, so this constraint is satisfied
automatically.

If you see either of these errors in `oompah.log`, check whether two server
processes are running against the same repository at the same time (for example,
after an incomplete restart where the old process did not exit before the new
one started):

```bash
ps -ef | grep "oompah server" | grep -v grep
cat .oompah.pid
```

If a stale process is found, stop it with `kill <pid>` and then run
`make restart` to start a clean instance.

For implementation details and the fix for cross-instance races that can occur
during graceful reloads, see `plans/concurrent-git-tracker-writes.md`.

## Optional GitHub Issue Intake

Native projects can also accept customer-facing intake from GitHub Issues
without making GitHub the task tracker. Enable `github_issue_intake_enabled`
on the project and set `tracker_owner` / `tracker_repo` to the GitHub
repository that receives external issues.

The workflow is:

1. A customer opens or comments on a GitHub issue.
2. Oompah validates the GitHub issue in GitHub, but does not decompose work
   there.
3. Oompah creates an internal `.oompah/tasks` issue in `Proposed` with
   `oompah.external.github` metadata referencing the GitHub issue.
4. Intake readiness and decomposition happen on the internal Markdown issue.
   If decomposition is needed, the imported issue becomes the epic and child
   tasks are created under it.
5. Oompah works from the internal Markdown issue graph. On internal status
   changes, oompah posts a status comment to the originating GitHub issue.
6. When the internal issue reaches `Merged` or `Archived`, oompah closes the
   originating GitHub issue.

GitHub comments are copied into the internal issue once. Comments authored by
oompah on GitHub are ignored, and comments made on internal Markdown tasks are
not copied back to GitHub.
