---
id: TASK-386
title: >-
  Submit queue Step 4: update YOLO auto-merge to support enqueue mode for
  merge-queue-enabled projects
status: Done
assignee: []
created_date: '2026-05-05 20:04'
updated_date: '2026-06-01 16:01'
labels:
  - feature
  - beads-migrated
dependencies: []
priority: high
ordinal: 1000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Today's YOLO auto-merge flow (orchestrator.py:_yolo_review_actions_sync, ~line 1370+) directly calls `provider.merge_review(slug, review_id)` once CI is green and the PR is mergeable. With merge queue enabled, the right action is to *enqueue* the PR (label-and-wait) and let GitHub serialize the merge atomically — direct-merge bypasses the queue's correctness guarantees.

This bead adds enqueue mode as a per-project alternative. The watchdog logic stays mostly the same. Only the action taken when "CI is green and PR is mergeable" differs:

- direct mode: call merge_review (today's behavior, default)
- queue mode: enable auto-merge on the PR (or apply a configured queue label), hand off control to GitHub Merge Queue, watch for `merge_group` webhook events to update bead state when the queue's commit hits main.

Webhook handler (server.py) needs to recognize `merge_group` events alongside the existing `pull_request` and `push` (commit f6c00a5). When the queue dequeues a PR successfully, oompah needs to label the underlying bead as merged and trigger the source sync — same actions as today's manual auto-merge.

Parent: oompah-zlz_2-btf.
Plan: docs/submit-queue.md (Step 4).
<!-- SECTION:DESCRIPTION:END -->

## Comments
<!-- COMMENTS:BEGIN -->
<!-- COMMENT:BEGIN -->
index: 019df9c7-355e-7e4c-ab27-6981d3d623e5
author: oompah
created: 2026-05-05T20:14:35Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df9c7-56e1-7138-bd42-77a4431fb5ff
author: oompah
created: 2026-05-05T20:14:44Z

Focus: Feature Developer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df9c8-6e4a-7cec-bd65-ecb7ddd26127
author: oompah
created: 2026-05-05T20:15:55Z

Understanding + Plan:

The task is to add 'enqueue mode' as a per-project alternative to direct merge in the YOLO auto-merge flow.

Key changes needed:
1. **models.py**: Add  field to  dataclass (per acceptance criteria, this is a bool flag, not a string enum). Update , , .

2. **scm.py**: Add  method to  and implement in  (via GitHub's enable-auto-merge REST API). GitLab falls back to direct merge.

3. **orchestrator.py**: Update  to dispatch to  vs  based on .

4. **webhooks.py**: Add  event parsing in  / .

5. **server.py**: Update  and  to handle  events (label bead as merged + trigger source sync) and accept  field in project CRUD.

6. **projects.py**: Add  to .

7. **Tests**: Cover all acceptance criteria cases.

This preserves backward compat: default  means direct mode unchanged.
<!-- COMMENT:END -->
<!-- COMMENTS:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Completed and merged on main as commit 89584e2 / PR #62. Closing stale In Progress state; no active agent or worktree remains.
<!-- SECTION:FINAL_SUMMARY:END -->
