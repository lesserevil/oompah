---
id: TASK-382
title: '[epic] Submit queue: replace strict open_review gate with GitHub Merge Queue
  + parallel in-flight PRs'
status: Done
assignee: []
created_date: 2026-05-05 20:03
updated_date: 2026-05-05 20:10
labels:
- epic
- beads-migrated
dependencies: []
priority: high
ordinal: 1000
type: epic
beads:
  id: oompah-zlz_2-btf
  state: closed
  parent_id: null
  dependencies: []
  branch_name: oompah-zlz_2-btf
  target_branch: null
  url: null
  created_at: '2026-05-05T20:03:06Z'
  updated_at: '2026-05-05T20:10:50Z'
  closed_at: '2026-05-05T20:10:50Z'
---
## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
oompah's per-project dispatch is gated by `_project_has_open_review` (orchestrator.py:840), which refuses any non-P0 dispatch while ANY non-draft PR is open. With trickle's CI taking ~60 min (Linux/Windows/macOS matrix + e2e), this caps throughput at one PR per hour per project. Today's session sat idle for 30+ min stretches with 41 ready beads and 5 free agent slots simply waiting on CI.

GitHub Merge Queue (GA 2023) replaces the trunk-safety reason for this gate: the platform tests every speculative combination of stacked PRs before atomically merging, so main is provably never broken regardless of how many PRs are in flight.

This epic plans the full cutover: enable merge_group CI triggers, reduce the .beads/issues.jsonl write-contention that would otherwise punish parallel PRs, soften the binary in-flight gate to a configurable per-project concurrency limit, update YOLO auto-merge to enqueue mode, then enable GitHub Merge Queue on both repos.

Full design: docs/submit-queue.md.

Children of this epic:
- Step 1 (P0): Add merge_group CI triggers to both repos.
- Step 2 (P1): Reduce .beads/issues.jsonl merge contention.
- Step 3 (P1): Soften _project_has_open_review to a configurable concurrency limit.
- Step 4 (P1): Update YOLO auto-merge to support enqueue mode.
- Step 5 (P0): Enable GitHub Merge Queue on main branches in both repos.
<!-- SECTION:DESCRIPTION:END -->

## Comments
<!-- COMMENTS:BEGIN -->
<!-- COMMENT:BEGIN -->
index: 019df9be-32fb-7ac9-bf17-3975d841d097
author: oompah
created: 2026-05-05T20:04:45Z

Agent dispatched (profile: deep)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df9be-5817-782d-84d5-b12686c3785b
author: oompah
created: 2026-05-05T20:04:54Z

Focus: DevOps Engineer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df9c0-07ad-77eb-a8ba-bdd7a94035cc
author: oompah
created: 2026-05-05T20:06:45Z

Understanding: This is the umbrella epic. Children oompah-zlz_2-7fp/win/pt4/d7o/zen are the implementation steps. The epic-level deliverable per the description is docs/submit-queue.md — the full design covering the throughput problem, GitHub Merge Queue mechanics, and the 5-step rollout (merge_group CI triggers → .beads merge driver → soften open_review gate → YOLO enqueue mode → enable Merge Queue). I will write that design doc now so children can reference it; each child will own its own implementation+tests.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df9c2-ef5f-7a29-bc31-7522f7e0ec3e
author: oompah
created: 2026-05-05T20:09:55Z

Discovery: All 5 child steps already exist as beads (oompah-zlz_2-7fp/win/pt4/d7o/0c3) and link to this epic as their parent. Step 5 (oompah-zlz_2-0c3) was filed previously and was missing from the original description's child enumeration; the design doc now lists its real ID. Code references confirmed: gate at oompah/orchestrator.py:881, YOLO merge call at oompah/scm.py:400 (PUT .../pulls/{N}/merge merge_method=squash — will 405 once Merge Queue is required). Existing CI workflow at .github/workflows/ci.yml has only push+pull_request triggers — Step 1 needs to add merge_group there.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df9c3-12a6-7e7b-baa0-9b082efd3f7c
author: oompah
created: 2026-05-05T20:10:04Z

Implementation: wrote docs/submit-queue.md (274 lines) covering: (1) the throughput problem with measurements, (2) why the gate exists and why GitHub Merge Queue is a strictly stronger replacement for trunk safety, (3) goals/non-goals, (4) per-step rollout with mermaid sequence diagram, code snippets, validation, and rollback for all 5 steps, (5) risk/rollback matrix, (6) success criteria. Each child issue is referenced by ID so future agents can find them. No code changes — all implementation work belongs to the children, which is why they were filed as separate beads.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df9c3-35b3-7e25-b7a4-3cb9ce2bb811
author: oompah
created: 2026-05-05T20:10:13Z

Verification: docs/submit-queue.md is a docs-only change so no code tests are needed; per project convention test coverage lands with each child step's implementation. make test surfaces a pre-existing venv ModuleNotFoundError (httpx/fastapi missing) on this worktree — unrelated to this change. Mermaid block validated by inspection (no ASCII art used). All file/symbol references in the doc match the actual code: orchestrator.py:881 _project_has_open_review, scm.py:400 GitHubProvider.merge_review, .github/workflows/ci.yml current triggers.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df9c3-9f3d-7b75-a795-e64cef53c747
author: oompah
created: 2026-05-05T20:10:40Z

Completion: docs/submit-queue.md committed and pushed on branch oompah-zlz_2-btf (commit c903271). The 5 implementation children (oompah-zlz_2-7fp Step 1, win Step 2, pt4 Step 3, d7o Step 4, 0c3 Step 5) are tracked separately and dispatched independently; this epic's planning deliverable is complete. Closing the epic.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df9c3-cb72-7a2d-a9ba-13c73fdf9431
author: oompah
created: 2026-05-05T20:10:52Z

Agent completed successfully in 367s (729783 tokens)
<!-- COMMENT:END -->
<!-- COMMENTS:END -->
