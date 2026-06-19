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

Native tracker projects skip Backlog.md compatibility checks and Backlog task
conflict repair because `.oompah/tasks` is the task source of truth.
