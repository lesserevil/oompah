---
id: OOMPAH-25
type: task
status: Open
priority: 1
title: Verify lightweight wheel contents and dependency boundary
parent: OOMPAH-22
children: []
blocked_by:
- OOMPAH-24
labels: []
assignee: null
created_at: '2026-06-22T01:16:46.207414Z'
updated_at: '2026-06-22T01:35:27.685953Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Plan: plans/oompah-1.0-release.md#cli-and-api-contract

WHAT TO DO
Verify the lightweight wheel includes the modules required by oompah task and oompah project-bootstrap, while keeping server runtime dependencies behind the server extra.

HOW TO VERIFY
A clean wheel install can run the supported CLI commands, and dependency metadata does not force-install the full service runtime for normal CLI users.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

