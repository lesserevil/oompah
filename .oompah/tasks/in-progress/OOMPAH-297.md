---
id: OOMPAH-297
type: task
status: In Progress
priority: 1
title: Generate and maintain repository maps on Git-backed state branches
parent: OOMPAH-293
children: []
blocked_by:
- OOMPAH-294
- OOMPAH-296
labels:
- focus-complete:duplicate_detector
assignee: null
created_at: '2026-07-21T15:14:07.528667Z'
updated_at: '2026-07-21T22:13:23.776188Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 4b99067b-519f-49a7-a4f8-9b72d99a53b8
---
## Summary

Connect repository-map generation to Oompah project synchronization. For a managed project checkout, reuse a fresh artifact for the exact target commit or generate one from the Tree-sitter extractor and ranked renderer. Write it atomically to the configured project state branch using the lifecycle from OOMPAH-294; never write generated map files to the managed repository main or release branches. Coalesce duplicate requests for the same project/SHA and retain only the configured bounded history.\n\nGeneration must run as a bounded background operation. A failed, stale, or partial index must be reported and must not block normal task dispatch.\n\nTests:\n- Integration tests with a temporary Git remote prove maps land only on the state branch.\n- Verify same-SHA requests reuse the artifact and changed-SHA requests regenerate it.\n- Verify concurrent requests coalesce and atomic writes never expose partial JSON.\n- Verify failures/timeouts leave task dispatch usable and emit a diagnostic state.\n\nAcceptance criteria:\n- One fresh artifact is available per successfully indexed project commit.\n- No repository code branch receives index-only commits.\n- Storage retention and failure behavior match the design document.\n- Tests pass through the Makefile target.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-21 22:08
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-21 22:08
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-21 22:13
---
Duplicate screening complete: no duplicate found.

Searched all .oompah/tasks/ directories (archived ~200+ tasks, done, merged ~50+ tasks, backlog, needs-ci-fix, needs-rebase) and plans/ for: repository-map, repo-map, repomap, repo_map, state-branch, coalesce, bounded background, background generation, SHA reuse, project synchronization, atomic write + map, tree-sitter. Zero matches for any of these terms in an overlapping scope.

Closest reviewed tasks and evidence:
- OOMPAH-294 (Done): Defines the artifact schema and state-branch lifecycle — this is the upstream foundation that OOMPAH-297 builds on, not a duplicate.
- OOMPAH-295 (Done): Adds Tree-sitter extraction (input layer) — out of scope for generation/maintenance orchestration.
- OOMPAH-296 (Merged): Implements ranking and bounded rendering (output layer) — out of scope for the integration/orchestration tier.
- OOMPAH-298/299/300 (Open): Downstream consumers (prompt injection, config/docs, observability) — distinct from generation/maintenance.
- plans/repo-map-artifact.md: Design doc (OOMPAH-294 output) covers schema/lifecycle only, not the generation orchestrator.
- No archived or merged task covers: project-sync integration, duplicate-request coalescing, background-bounded generation, per-SHA cache reuse, state-branch integration tests, or concurrent-write atomicity.

OOMPAH-297 is net-new implementation work: the orchestration/integration layer that connects Tree-sitter extraction + ranking to the state-branch persistence lifecycle.
---
<!-- COMMENTS:END -->
