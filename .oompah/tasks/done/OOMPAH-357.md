---
id: OOMPAH-357
type: task
status: Done
priority: 1
title: Define actionable epic branch synchronization policy
parent: OOMPAH-356
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-22T01:23:49.686725Z'
updated_at: '2026-07-22T01:29:48.061384Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 951c7d25-3fe7-4b6a-9775-c7c46d7014fd
---
## Summary

Audit every orchestrator path that currently detects, schedules, or performs epic branch merge/rebase work. Implement a single policy decision point that classifies a request as allowed or suppressed.\n\nRules:\n- Suppress automatic synchronization solely because main advanced.\n- Always suppress direct synchronization between two epic branches.\n- Allow synchronization only for: explicit operator request; an epic PR being opened/refreshed; a merge-blocking conflict or required-base condition; or a configured staleness threshold for a long-lived branch.\n- Return a machine-readable reason for both allowed and suppressed decisions.\n\nTests:\n- Unit tests for each allow and suppress case.\n- Regression test that an incomplete stale epic is reported but no rebase/merge action is queued.\n\nAcceptance criteria:\n- All epic synchronization callers use the policy decision point.\n- The default policy has no automatic main-to-epic synchronization.\n- Direct epic-to-epic synchronization is impossible through Oompah automation.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-22 01:29
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-22 01:29
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
