---
id: TASK-339
title: 'Multi-source task ingest: abstract tracker beyond beads (GitHub/GitLab Issues,
  Jira)'
status: Done
assignee: []
created_date: 2026-05-05 00:38
updated_date: 2026-05-05 00:40
labels:
- feature
- beads-migrated
dependencies: []
priority: low
ordinal: 1000
type: feature
beads:
  id: oompah-zlz_2-atk
  state: closed
  parent_id: null
  dependencies: []
  branch_name: oompah-zlz_2-atk
  target_branch: null
  url: null
  created_at: '2026-05-05T00:38:02Z'
  updated_at: '2026-05-05T00:40:44Z'
  closed_at: '2026-05-05T00:40:44Z'
---
## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Today every dispatched task comes from beads via BeadsTracker. The system has no abstraction for fetching tasks from other backends, even though the project access_token field added in oompah-j12-followup would let us authenticate against GitHub/GitLab issue APIs.

Goal: refactor task ingest behind a Tracker ABC so the orchestrator can pull from multiple sources, with the first new implementation being GitHub Issues. WORKFLOW.md should branch its beads cheat sheet on the source so agents get the right CLI commands for the task they're handed (e.g. `gh issue comment` vs `bd comments add`).

Why now: the access_token plumbing just landed, the prompt restructure just landed, and the orchestrator's tracker call sites are all funneled through `_tracker_for_project` — the moment to swap a single dispatch site for a factory is before more code accumulates around the beads-only assumption.
<!-- SECTION:DESCRIPTION:END -->

## Comments
<!-- COMMENTS:BEGIN -->
<!-- COMMENT:BEGIN -->
index: 019df592-65fa-74c2-9c79-3296c176dda4
author: oompah
created: 2026-05-05T00:38:26Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df592-7eda-7aaa-9632-2e90012f8008
author: oompah
created: 2026-05-05T00:38:32Z

Focus: Feature Developer
<!-- COMMENT:END -->
<!-- COMMENTS:END -->
