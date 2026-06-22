---
id: OOMPAH-34
type: task
status: In Progress
priority: 1
title: Write the 1.0 service operator runbook
parent: OOMPAH-32
children: []
blocked_by:
- OOMPAH-28
labels: []
assignee: null
created_at: '2026-06-22T01:17:23.758648Z'
updated_at: '2026-06-22T01:56:27.753067Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 22349e9f-935b-4726-b62a-69f4c43ff8fa
---
## Summary

Plan: plans/oompah-1.0-release.md#operator-and-project-documentation

WHAT TO DO
Write a 1.0 service operator runbook covering configuration, start/restart, health checks, managed repo soundness checks, and basic troubleshooting.

HOW TO VERIFY
An operator can use the runbook to verify the service is running and identify common stuck states without reading implementation code.

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
author: oompah
created: 2026-06-22 01:53
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-06-22 01:54
---
Understanding: OOMPAH-34 asks for a 1.0 service operator runbook covering configuration, start/restart, health checks, managed repo soundness checks, and basic troubleshooting. Duplicate investigation complete — no duplicate exists. The sibling tasks (OOMPAH-33, 35, 36) cover different doc areas. This is a distinct docs task. Blocker OOMPAH-28 is Done. Proceeding with the runbook by exploring the service codebase, Makefile, .env.example, and existing docs.
---
author: oompah
created: 2026-06-22 01:56
---
Discovery: OOMPAH-34 is unique — no duplicate exists. Key findings from codebase exploration: (1) Makefile provides start/stop/restart/graceful/status/logs targets; (2) All config goes in .env (reference: .env.example); (3) Health check via GET /api/v1/state and 'make status'; (4) Managed repo soundness via ensure_repo_sound() in oompah/repo_health.py — runs automatically as the 'repo_heal' maintenance job; (5) Stuck states: budget_exceeded, paused (global/per-project), stalled agents, reject_streak for stuck issues, stuck_epic alerts, provider failures; (6) Webhook degradation shows in dashboard alerts and log. Writing the runbook now at docs/operator-runbook.md.
---
<!-- COMMENTS:END -->
