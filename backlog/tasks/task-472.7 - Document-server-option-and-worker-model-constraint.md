---
id: TASK-472.7
title: Document --server option and worker-model constraint
status: Backlog
assignee: []
created_date: '2026-06-09 04:19'
labels:
  - 'needs:backend'
dependencies: []
parent_task_id: TASK-472
priority: medium
ordinal: 196000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Update README/AGENTS.md/.env.example for the --server {uvicorn,granian} option. Document why granian must run workers=1 (shared in-process orchestrator + _ws_clients state) and guard against misconfiguration (reject workers>1 or warn).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Docs describe --server and the workers=1 constraint
- [ ] #2 workers>1 under granian is rejected or clearly warned
<!-- AC:END -->
