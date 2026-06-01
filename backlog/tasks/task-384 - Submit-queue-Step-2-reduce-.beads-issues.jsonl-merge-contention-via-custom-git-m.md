---
id: TASK-384
title: >-
  Submit queue Step 2: reduce .beads/issues.jsonl merge contention via custom
  git merge driver
status: Done
assignee: []
created_date: '2026-05-05 20:04'
updated_date: '2026-06-01 16:01'
labels:
  - ci-fix
  - feature
  - beads-migrated
dependencies: []
priority: high
ordinal: 1000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Every agent's `bd close` / `bd update` / `bd comments add` writes to `.beads/issues.jsonl`. Two PRs with non-overlapping code changes still conflict in that one file. With the current single-PR-in-flight gate this never matters, but the moment Step 3 raises the concurrency cap the bead-jsonl conflicts will become the new bottleneck — every parallel PR after the first will hit a merge conflict, the YOLO watchdog will dispatch conflict-resolution agents, and we'll burn agent compute on the same problem repeatedly.

Three viable shapes:

(a) Custom git merge driver. Register `merge=beads-jsonl` in `.gitattributes` for `.beads/issues.jsonl`, point it at a script that merges by issue id (last-writer-wins per id, plus deduplication of comment events by their id field). Conflicts resolved mechanically with no human input.

(b) Per-PR fragment files. Agents append to `.beads/fragments/<run-id>.jsonl` instead of mutating `.beads/issues.jsonl`. A post-merge hook (or scheduled coalescer) merges fragments into the canonical file.

(c) Stop tracking `.beads/issues.jsonl` in git altogether. Canonical state lives in Dolt; PRs only carry code. Cleanest, biggest change.

Recommendation: start with (a). Smallest change, addresses immediate pain, the merge-by-id heuristic is well-understood. (b) and (c) are followups if (a)'s mechanical merges ever produce surprising history.

Parent: oompah-zlz_2-btf.
Plan: docs/submit-queue.md (Step 2).
<!-- SECTION:DESCRIPTION:END -->

## Comments
<!-- COMMENTS:BEGIN -->
<!-- COMMENT:BEGIN -->
index: 019df9bf-feb6-764d-8a87-91bc844e1e8c
author: oompah
created: 2026-05-05T20:06:43Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df9c0-2ab3-7a19-9fd1-48ce7588aced
author: oompah
created: 2026-05-05T20:06:54Z

Focus: Merge Conflict Resolver
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df9c1-2968-721b-bf0b-11e031900323
author: oompah
created: 2026-05-05T20:07:59Z

Understanding: This is a new feature issue (not a merge conflict resolution task). I need to implement option (a) from the description: a custom git merge driver for .beads/issues.jsonl that merges by issue ID (last-writer-wins per id, deduplication of comments by their id field). Plan: (1) Create scripts/beads-merge.sh - the merge driver script; (2) Create .gitattributes registering .beads/issues.jsonl merge=beads-jsonl; (3) Update oompah/projects.py to install the merge driver in newly-cloned repos (idempotent); (4) Write tests for the merge driver and projects.py integration; (5) Create docs/submit-queue.md documenting the driver behavior. The branch is currently at origin/main with no prior commits, so this is a fresh implementation.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df9c8-12d6-7bfe-aa9b-25a859c1a569
author: oompah
created: 2026-05-05T20:15:32Z

Discovery: The codebase already has _bootstrap_lfs() as a pattern for post-clone configuration in oompah/projects.py (installs git lfs + writes .gitattributes). I'll follow the same pattern: add _install_beads_merge_driver() that idempotently runs git config merge.beads-jsonl.driver. The issues.jsonl format is JSONL with one JSON object per line, each with id, updated_at, and comments[] containing objects with id/created_at. The merge strategy is clear: last-writer-wins per id by updated_at, comments unioned by id.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df9cb-a2f5-717a-a228-996918962a3b
author: oompah
created: 2026-05-05T20:19:26Z

Implementation: (1) scripts/beads-merge.sh — shell wrapper + embedded Python: parses %A (current) and %B (other) as JSONL, merges by issue id using last-writer-wins on updated_at, unions comments by comment id (deduped), writes result to %A in-place, exits 0. Blank/invalid JSON lines are skipped. (2) .gitattributes — registers '.beads/issues.jsonl merge=beads-jsonl'. (3) oompah/projects.py — added _install_beads_merge_driver() that idempotently sets git config merge.beads-jsonl.driver; called from create() after _bootstrap_lfs(). (4) tests/test_beads_merge_driver.py — 25 tests covering: script presence/executability, non-overlapping issues, last-writer-wins, comment union/dedup, output ordering, robustness (blank lines, invalid JSON, missing base), full git conflict fixture (real git repos with two conflicting branches merge cleanly), install_beads_merge_driver idempotency and failure modes, and failure fallback (broken driver → conflict markers, not corruption).
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df9cc-6ea3-7111-bb30-4e3f1edb1a74
author: oompah
created: 2026-05-05T20:20:18Z

Verification: 25 new tests in tests/test_beads_merge_driver.py all pass. Pre-existing test failures (20 collection errors due to missing fastapi/httpx in this Python env) are unchanged from baseline on main — confirmed by running on main before changes. Tests cover: (1) script presence/executability, (2) non-overlapping issue merges, (3) last-writer-wins on updated_at, (4) comment union by id with dedup, (5) output ordering, (6) robustness (blank/invalid lines), (7) full git conflict fixture with real repo + real merge, (8) install_beads_merge_driver idempotency, (9) failure fallback (broken driver -> git produces conflict markers, file not corrupted).
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df9cc-94f1-71b5-872a-5d19b8f8950e
author: oompah
created: 2026-05-05T20:20:28Z

Completion: Delivered option (a) from the issue description — custom git merge driver for .beads/issues.jsonl. Deliverables: (1) scripts/beads-merge.sh — shell+Python merge driver, merges by issue id (last-writer-wins on updated_at), unions comments (deduped by id), exits 0 on success; (2) .gitattributes — .beads/issues.jsonl merge=beads-jsonl; (3) oompah/projects.py — _install_beads_merge_driver() function, idempotent, called from ProjectStore.create(); (4) tests/test_beads_merge_driver.py — 25 tests including synthetic git conflict fixture. All acceptance criteria met. The docs/submit-queue.md was already written comprehensively by the parent issue oompah-zlz_2-btf and includes Step 2 documentation.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df9cc-b607-73fb-b777-177582eb1476
author: oompah
created: 2026-05-05T20:20:36Z

Agent completed successfully in 833s (2727717 tokens)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df9cf-0034-79a8-a0e3-46297fb8280d
author: oompah
created: 2026-05-05T20:23:06Z

YOLO: CI tests failed on MR #58. Fix the failing tests so this MR can merge. Do NOT rewrite the feature — only fix test failures. IMPORTANT: Paths in CI logs are not trustworthy. Run tests locally to get accurate paths and errors.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df9d2-649d-7a5c-b5f5-a2ac88d466b6
author: oompah
created: 2026-05-05T20:26:48Z

Focus: Merge Conflict Resolver
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df9d2-6bd2-710d-9e09-497ec8455356
author: oompah
created: 2026-05-05T20:26:50Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df9d2-a342-7246-b083-95ef2338ded8
author: oompah
created: 2026-05-05T20:27:04Z

Understanding: CI tests are failing after the feature implementation. I need to rebase onto main and fix the failing tests. Starting with rebase then local test run to identify failures.
<!-- COMMENT:END -->
<!-- COMMENTS:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Completed and merged on main as commit 303766c / PR #58. Closing stale In Progress state; no active agent or worktree remains.
<!-- SECTION:FINAL_SUMMARY:END -->
