---
id: OOMPAH-357
type: task
status: Open
priority: 1
title: Define actionable epic branch synchronization policy
parent: OOMPAH-356
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-22T01:23:49.686725Z'
updated_at: '2026-07-22T01:27:30.418017Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Audit every orchestrator path that currently detects, schedules, or performs epic branch merge/rebase work. Implement a single policy decision point that classifies a request as allowed or suppressed.\n\nRules:\n- Suppress automatic synchronization solely because main advanced.\n- Always suppress direct synchronization between two epic branches.\n- Allow synchronization only for: explicit operator request; an epic PR being opened/refreshed; a merge-blocking conflict or required-base condition; or a configured staleness threshold for a long-lived branch.\n- Return a machine-readable reason for both allowed and suppressed decisions.\n\nTests:\n- Unit tests for each allow and suppress case.\n- Regression test that an incomplete stale epic is reported but no rebase/merge action is queued.\n\nAcceptance criteria:\n- All epic synchronization callers use the policy decision point.\n- The default policy has no automatic main-to-epic synchronization.\n- Direct epic-to-epic synchronization is impossible through Oompah automation.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

