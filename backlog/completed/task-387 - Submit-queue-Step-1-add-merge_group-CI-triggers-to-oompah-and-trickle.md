---
id: TASK-387
title: 'Submit queue Step 1: add merge_group CI triggers to oompah and trickle'
status: Done
assignee: []
created_date: 2026-05-05 20:07
updated_date: 2026-05-05 20:10
labels:
- beads-migrated
dependencies:
- TASK-383
priority: high
ordinal: 1000
type: task
beads:
  id: oompah-zlz_2-vk0
  state: closed
  parent_id: oompah-zlz_2-btf
  dependencies:
  - oompah-zlz_2-7fp
  branch_name: oompah-zlz_2-vk0
  target_branch: null
  url: null
  created_at: '2026-05-05T20:07:41Z'
  updated_at: '2026-05-05T20:10:12Z'
  closed_at: '2026-05-05T20:10:12Z'
parent: TASK-382
---
## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Add `merge_group:` triggers to GitHub Actions CI workflows in both oompah and trickle repos so the same jobs run on the speculative branches GitHub Merge Queue creates (gh-readonly-queue/<base>/...).

Today both workflows trigger only on `push` (to main) and `pull_request` (targeting main). Without `merge_group`, enabling the queue would result in zero status checks running on speculative-stack branches, which means GitHub Merge Queue would either fail open (allow merges with no CI) or block forever (waiting for required checks that never run).

Cost: ~2 lines of YAML per repo. No behavior change until merge queue is actually enabled (Step 5). This is the foundation.

Parent: oompah-zlz_2-btf.
Plan: docs/submit-queue.md (Step 1).
<!-- SECTION:DESCRIPTION:END -->

## Comments
<!-- COMMENTS:BEGIN -->
<!-- COMMENTS:END -->
