---
id: OOMPAH-16
type: epic
status: Backlog
priority: 1
title: Oompah 1.0 release readiness
parent: null
children:
- OOMPAH-17
- OOMPAH-22
- OOMPAH-27
- OOMPAH-32
- OOMPAH-37
blocked_by: []
labels:
- release:1.0
- draft
assignee: null
created_at: '2026-06-22T01:14:40.055430Z'
updated_at: '2026-06-22T01:17:30.701308Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Plan: plans/oompah-1.0-release.md

WHAT TO DO
Coordinate the full oompah 1.0 release readiness effort across release automation, CLI packaging, managed-project workflow validation, documentation, and release execution.

RELEASE FORMAT
- Release branch: release/1.0
- Draft tag: v1.0.0-draft
- Final tag: v1.0.0
- Package version: 1.0.0
- Draft release tags may be force-moved during release-candidate iteration.
- Final release tags are immutable and must not be force-moved.

DONE WHEN
All child epics are complete, the draft release has been verified, the final v1.0.0 release has been published, and post-release install/bootstrap smoke checks pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

