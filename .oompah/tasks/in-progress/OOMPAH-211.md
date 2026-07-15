---
id: OOMPAH-211
type: feature
status: In Progress
priority: 2
title: Deliver new task comments to running agents
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-15T20:52:07.206772Z'
updated_at: '2026-07-15T20:56:43.773446Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 100e3af3-206e-4110-8473-9c52e2294053
---
## Summary

Triggered by: OOMPAH-210

When a comment is added to a task with an active agent run, deliver it into that agent's live context rather than only exposing it on a future dispatch. Define ordering, idempotency, audit logging, retry behavior, and graceful fallback for providers that cannot accept mid-run messages. Add unit and integration tests proving a running agent receives a newly posted task comment exactly once.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-15 20:54
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-15 20:54
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-15 20:55
---
Understanding: OOMPAH-211 asks for delivering new task comments to running agents mid-run. Triggered by OOMPAH-210. My role is Duplicate Investigator — I will search for existing tasks covering the same ground before any implementation begins. Searching now for candidate duplicates.
---
author: oompah
created: 2026-07-15 20:56
---
Discovery: OOMPAH-211 is NOT a duplicate. Searched all task states (in-progress, done, archived, merged), plans/, docs/, README.md and WORKFLOW.md for tasks covering: deliver/inject task comments to running agents mid-run, live context injection, mid-flight messages, human-in-loop injection, idempotent comment delivery. No existing task or plan covers this scenario. OOMPAH-210 (the trigger) is about GitHub check-run 403 errors — a completely different topic. This feature request is genuinely new and requires backend feature implementation: comment-delivery pipeline to active agent runs, ordering/idempotency guarantees, audit logging, retry behavior, provider fallback, and unit/integration tests.
---
<!-- COMMENTS:END -->
