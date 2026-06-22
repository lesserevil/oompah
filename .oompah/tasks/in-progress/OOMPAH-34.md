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
updated_at: '2026-06-22T02:03:53.067778Z'
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
author: oompah
created: 2026-06-22 02:03
---
Implementation: Created docs/operator-runbook.md (608 lines) covering all required areas:

1. Configuration — .env (required + commonly-tuned vars), WORKFLOW.md hot-reload behavior, per-project settings via dashboard only.
2. Installation — make setup (idempotent), make install-gh-extensions.
3. Start/stop/restart — make start/stop/restart/graceful with guidance on when to use hard vs graceful restart.
4. Health checks — make status, GET /api/v1/state with key field table, port check, make logs, provider health test endpoint.
5. Managed repo soundness — describes what repo_heal maintenance job does automatically; manual git checks for branch, merge/rebase-in-progress, .oompah/tasks directory layout, worktree inspection.
6. Troubleshooting — covers no dispatch (6 ordered checks), reject streak (table of reasons+fixes), stalled agents, webhook degradation, stuck epics, bad checkout manual recovery, and 5 unexpected-exit causes.
7. Makefile quick reference, key files table, and state snapshot reference with Mermaid diagram.

Committed and pushed to branch epic-OOMPAH-32.
---
author: oompah
created: 2026-06-22 02:03
---
Verification: This is a documentation task — no code changes, no tests required. The runbook was validated by cross-referencing against: Makefile targets (start/stop/restart/graceful/status/logs), .env.example (all referenced vars exist), oompah/__main__.py (startup flags, error messages), oompah/repo_health.py (ensure_repo_sound logic), oompah/orchestrator.py (_should_dispatch reject reasons, stall/budget/stuck logic), oompah/server.py (health endpoints), and existing docs/webhook-forwarding.md (referenced in §6.4). All sections are verifiable by an operator without reading implementation code.
---
author: oompah
created: 2026-06-22 02:03
---
Completion: docs/operator-runbook.md delivered. Covers: configuration (.env required/tuned vars, WORKFLOW.md, per-project JSON), installation, start/stop/restart/graceful, health checks (make status, GET /api/v1/state, port, providers), managed repo soundness (automatic repo_heal + manual git checks + .oompah/tasks integrity), and 7 troubleshooting scenarios for common stuck states. An operator can verify the service is running and identify any common stuck state using only this runbook. No duplicate found.
---
<!-- COMMENTS:END -->
