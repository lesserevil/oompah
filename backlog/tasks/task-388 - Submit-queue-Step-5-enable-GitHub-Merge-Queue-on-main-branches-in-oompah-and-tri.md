---
id: TASK-388
title: 'Submit queue Step 5: enable GitHub Merge Queue on main branches in oompah
  and trickle'
status: To Do
assignee: []
created_date: 2026-05-05 20:08
updated_date: 2026-05-05 20:08
labels:
- beads-migrated
dependencies:
- TASK-383
- TASK-386
priority: high
ordinal: 1000
type: task
beads:
  id: oompah-zlz_2-0c3
  state: open
  parent_id: oompah-zlz_2-btf
  dependencies:
  - oompah-zlz_2-7fp
  - oompah-zlz_2-d7o
  branch_name: oompah-zlz_2-0c3
  target_branch: null
  url: null
  created_at: '2026-05-05T20:08:07Z'
  updated_at: '2026-05-05T20:08:07Z'
  closed_at: null
parent: TASK-382
---
## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The actual cutover. Repository-level configuration on GitHub:

1. Settings → Branches → Branch protection rule for `main` → Require merge queue.
2. Pick required status checks to gate the queue:
   - oompah: test (3.11), test (3.12), test (3.13)
   - trickle: ci's matrix (test-linux, test-macos, test-windows, lint, smoke-deb), e2e
3. Configure batch size, build concurrency, and timeout per repo's CI duration:
   - For trickle's 60-min CI: batch_size=1 (no batching), build_concurrency=2-3 (parallel speculative checks). Avoids amplifying flake risk via shared batches; gives parallel throughput.
   - For oompah's faster CI (~3 min): batch_size=2-3 acceptable, build_concurrency=2.

Per-repo config-only — no oompah code change. This is the bead that flips the actual switch.

Depends on Step 1 (merge_group triggers) and Step 4 (enqueue-mode YOLO) both being live. Step 2 (.beads/issues.jsonl merge driver) and Step 3 (configurable concurrency cap) can land in parallel; their absence just means we can't yet raise the concurrency cap above 1 even after this bead lands.

Parent: oompah-zlz_2-btf.
Plan: docs/submit-queue.md (Step 5).
<!-- SECTION:DESCRIPTION:END -->

## Comments
<!-- COMMENTS:BEGIN -->
<!-- COMMENTS:END -->
