---
id: OOMPAH-507
type: bug
status: Backlog
priority: 1
title: Drain active agents before deployment restarts
parent: OOMPAH-502
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-28T15:06:07.476394Z'
updated_at: '2026-07-28T15:06:07.476394Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Problem: make restart performs an immediate stop/start and terminates active agents. The recent deployment interrupted OOMPAH-456, orphaned its running entry, and forced a fresh agent to reread and recover work.

Implementation: make the normal Makefile restart path request the existing process-level graceful restart, pause dispatch, wait for active agents to finish, exec the updated process, and verify service health before returning. Add an environment-only configurable drain timeout with a safe long default. If the deadline expires, persist undrained task identities exactly once and re-dispatch them after restart as today. Provide an explicitly named emergency force-restart target for operators; do not silently fall back to killing agents when the healthy API is reachable. Preserve user pause state, PID/port handling, auto-update restarts, and Granian/Uvicorn behavior.

Tests: graceful-restart unit/integration tests for zero, one, and multiple running agents; completion during drain; timeout recovery deduplication; repeated restart requests; user-paused state; process exec/health wait; Makefile contract tests proving normal restart drains and force-restart is explicit. Update operator docs and AGENTS guidance.

Acceptance criteria: normal deployments do not terminate active agents; dispatch remains paused during drain; code changes are loaded after exec; timeout recovery is lossless and observable; emergency force restart remains available.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

