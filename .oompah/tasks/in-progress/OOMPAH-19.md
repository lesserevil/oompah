---
id: OOMPAH-19
type: task
status: In Progress
priority: 1
title: Support force-movable 1.0 draft release tags
parent: OOMPAH-17
children: []
blocked_by:
- OOMPAH-18
labels:
- release:1.0
assignee: null
created_at: '2026-06-22T01:14:56.553408Z'
updated_at: '2026-06-22T01:53:40.034790Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 38a39be3-c5f4-4b24-a732-9221d485957a
---
## Summary

Plan: plans/oompah-1.0-release.md#release-shape

WHAT TO DO
Teach release validation to accept v1.0.0-draft as a draft release tag that maintainers may force-move during release-candidate iteration, while preserving strict validation for the immutable final v1.0.0 tag.

DETAILS
Draft validation should be explicit rather than a broad wildcard that weakens final release checks. Rerunning the workflow after force-moving the draft tag should validate the checked-out source and update the draft release artifacts cleanly.

HOW TO VERIFY
Automated tests cover both v1.0.0-draft and v1.0.0. Final release validation still rejects a tag that does not match project.version.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-22 01:53
---
Agent dispatched (profile: default)
---
<!-- COMMENTS:END -->
