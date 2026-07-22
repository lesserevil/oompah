---
id: OOMPAH-300
type: task
status: In Progress
priority: 2
title: Add end-to-end repository-map observability and regression coverage
parent: OOMPAH-293
children: []
blocked_by:
- OOMPAH-298
- OOMPAH-299
labels:
- focus-complete:duplicate_detector
assignee: null
created_at: '2026-07-21T15:14:10.495385Z'
updated_at: '2026-07-22T00:02:35.495007Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 7ff0b818-35c7-43c6-a3a0-069888d7829d
---
## Summary

Add API/UI-neutral diagnostics and end-to-end tests proving the complete repository-map workflow. Report per-project index status, analyzed SHA, artifact schema version, generation duration, cache reuse, file/symbol counts, failure reason, and prompt inclusion status. Ensure diagnostics expose metadata only by default, not complete repository source. Exercise a managed-project fixture from sync through state-branch persistence and agent prompt construction.\n\nTests:\n- End-to-end fixture proves first dispatch generates a map, a second dispatch reuses it, and a commit change regenerates it.\n- Verify source/release branches remain unchanged by indexing.\n- Verify timeout, parse failure, and state-branch write failure leave agents runnable with no map.\n- Verify diagnostic responses do not leak full source contents or credentials.\n\nAcceptance criteria:\n- Operators can distinguish generating, fresh, stale, unavailable, and failed states.\n- The full workflow is covered by automated regression tests.\n- Failure behavior is demonstrably safe and non-blocking.\n- Tests pass through the Makefile target.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-21 23:59
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-21 23:59
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-22 00:02
---
Focus handoff: duplicate_detector

**Outcome:** OOMPAH-300 is NOT a duplicate. Duplicate screening complete.

**Closest reviewed tasks and evidence:**
- OOMPAH-293 (epic, parent): 'Epic: Git-backed Oompah state branches and coalesced metadata checkpoints' — parent epic; OOMPAH-300 is a child of this epic.
- OOMPAH-294: Defined repo-map artifact schema and state-branch lifecycle (implemented, merged per plans/repo-map-artifact.md).
- OOMPAH-297 (committed): 'Generate and maintain repository maps on state branches' — covers the generator and state-branch write path.
- OOMPAH-298 (committed): 'Inject task-relevant repository maps into agent focus startup prompts' — covers prompt injection.
- OOMPAH-299 (committed): 'Add repo-map configuration, bootstrap defaults, and operator documentation' — covers config and docs.

**Key finding:** OOMPAH-300's scope (observability diagnostics for per-project index status, analyzed SHA, artifact schema version, generation duration, cache reuse, file/symbol counts, failure reason, prompt inclusion status; plus end-to-end managed-project fixtures testing the complete workflow) is NOT covered by any existing task. Existing tests (test_repo_map_generator.py, test_repo_map.py, test_repo_map_ranker.py, test_repo_map_bootstrap.py, test_repo_map_prompt.py) cover individual units and some generator-level scenarios, but no E2E fixture tests the full sync → state-branch → agent-prompt pipeline.

**Relevant files:**
- oompah/repo_map.py, oompah/repo_map_generator.py, oompah/repo_map_prompt.py, oompah/repo_indexer.py
- tests/test_repo_map_generator.py (has STATUS_FRESH/GENERATED/FAILED/TIMEOUT states but no E2E managed-project fixture)
- docs/repository-map.md, plans/repo-map-artifact.md
- Branch: epic-OOMPAH-293 (all prior repo-map work committed here)

**Remaining work:** Implement diagnostics layer and E2E tests per the task description. The feature is on branch epic-OOMPAH-293 and all blockers (OOMPAH-298, OOMPAH-299) are already committed.

**Recommended next focus:** feature (implement the diagnostics module and E2E test suite)
---
<!-- COMMENTS:END -->
