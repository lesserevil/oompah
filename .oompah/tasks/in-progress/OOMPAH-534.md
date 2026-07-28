---
id: OOMPAH-534
type: task
status: In Progress
priority: 3
title: Add end-to-end duplicate-preflight regressions and operator documentation
parent: OOMPAH-528
children: []
blocked_by:
- OOMPAH-533
labels: []
assignee: null
created_at: '2026-07-28T21:20:02.804008Z'
updated_at: '2026-07-28T21:50:01.541065Z'
work_branch: epic-OOMPAH-528
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 22022e37-b177-4771-9154-d26c50ae9604
oompah.work_branch: epic-OOMPAH-528
---
## Summary

Complete the feature with cross-component regression coverage, compatibility cleanup, and user-facing operator documentation after OOMPAH-529 through OOMPAH-533 are implemented.

Implementation scope:
- Add an end-to-end orchestrator test that creates an unchecked Open native Markdown task, starts preflight with spare capacity, applies a no-duplicate verdict, and then dispatches a different real implementation agent without ever presenting preflight as In Progress.
- Add the duplicate path: only a non-terminal match moves the task to Duplicate Candidate and terminal tasks are ignored.
- Add restart tests for running claim recovery and persisted checked evidence.
- Add edit invalidation: change title, description, parent/dependencies, or relevant labels after a pass and prove the task becomes stale and is re-screened before implementation.
- Add capacity tests that mix checked implementation work, unchecked Open work, multiple projects, and concurrency auto-scaling.
- Review existing focus-complete:duplicate_detector tests and compatibility code. Retain only compatibility that is still required; document a safe future removal path rather than silently changing old task records.
- Add user-facing documentation under docs/ explaining the lifecycle, task states, OOMPAH_DUPLICATE_PREFLIGHT_MAX_AGENTS, why an Open task may wait for screening, retry/Needs Human behavior, metrics/log messages, and troubleshooting. Use Mermaid for any diagram.
- Update any relevant configuration reference generated from .env.example.

Required tests/quality gates:
- New end-to-end tests for pass, duplicate, stale edit, claim recovery, capacity reservation, and pause/resume.
- Existing duplicate-detection, focus-handoff, scheduler, API, and dashboard suites pass.
- Run make test before completion.

Acceptance criteria:
1. End-to-end coverage proves the full preflight-to-implementation sequence and failure recovery.
2. Regression coverage proves terminal tasks are never duplicate comparison targets.
3. Documentation gives operators enough information to configure, observe, and troubleshoot the feature.
4. Legacy screened labels cannot accidentally unlock a changed or unverified task.
5. make test passes with no new failures, and the epic branch is ready for one final review/merge request only after all children are complete.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-28 21:44
---
Claimed by the current interactive Codex session before OOMPAH-533 completion. Final cross-component regression and quality-gate work remains; do not dispatch another agent.
---
author: oompah
created: 2026-07-28 21:48
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-28 21:48
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-28 21:50
---
Duplicate screening complete: No duplicate confirmed.

**Finding**: OOMPAH-534 is a distinct final validation and documentation phase, not a duplicate of OOMPAH-529-533.

**Evidence reviewed**: 
- OOMPAH-529: Revision-aware metadata persistence (focused tests pass)
- OOMPAH-530: Atomic claims and recovery (concurrency/recovery tests pass)
- OOMPAH-531: Spare-capacity scheduler integration (scheduler regressions pass)
- OOMPAH-532: Verdict completion lifecycle (completion regressions pass)
- OOMPAH-533: API/dashboard observability (1716 tests pass)

**Scope gap**: Each predecessor task includes focused component tests, but OOMPAH-534 requires:
1. End-to-end orchestrator test proving full preflight-to-implementation workflow
2. Cross-component regression verification across duplicate-detection, focus-handoff, scheduler, API, and dashboard
3. Comprehensive operator-facing documentation (none exists yet)
4. Edit invalidation, restart recovery, and terminal-task regression tests
5. .env.example configuration reference updates

This is the validation, regression, and documentation closure of the epic, not an implementation duplicate.
---
<!-- COMMENTS:END -->
