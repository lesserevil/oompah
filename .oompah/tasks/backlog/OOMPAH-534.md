---
id: OOMPAH-534
type: task
status: Backlog
priority: 3
title: Add end-to-end duplicate-preflight regressions and operator documentation
parent: OOMPAH-528
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-28T21:20:02.804008Z'
updated_at: '2026-07-28T21:20:02.804008Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
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

