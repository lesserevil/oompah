---
id: OOMPAH-979
type: task
status: In Progress
priority: null
title: Bound terminal publication locks so owner control cannot starve
parent: OOMPAH-940
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-10T00:01:51.280685Z'
updated_at: '2026-08-10T00:02:55.561889Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Triggered by OOMPAH-974 live rollout on 2026-08-09. On exact deployed main eb3ca86e56dbe87a078d81f97cfa6054b94a5ee6, authenticated project-owner terminal overrides for OOMPAH-974 and OOMPAH-978 kept /healthz responsive but waited about 214s and 193s. Evidence correlates the wait with WorkflowRuntime generation 919 terminal snapshot publication for 211 project members: TerminalTransitionCoordinator.override_transition waits on project_store.project_write_lock while terminal_audit_publication_lock holds the same project lock across corpus-wide proof/publication. Implementation scope: replace the generation-wide lock proof window with a bounded project terminal-authority revision/digest CAS or equivalent short critical section; publication must collect outside the lock, atomically revalidate exact terminal authority, and supersede/retry on a racing owner mutation. Add lock wait/hold metrics and a bounded fail-closed API response rather than indefinite waits. Preserve OOMPAH-968 absent-to-retained fencing, exact publication rollback, cross-project isolation, and atomic native tracker writes. Relevant files: oompah/workflow_runtime.py, terminal publication/proof helpers, oompah/terminal_transition_service.py or coordinator paths, server control API, observability. Required tests: a 200-task terminal publication racing an owner override completes the override promptly and makes stale publication supersede/retry; owner mutation racing absent-to-retained remains fenced; lock wait/hold observability is truthful; timeout returns a safe retryable response; restart/replay and cross-project concurrency remain idempotent. Acceptance: owner terminal/provenance control has a documented bounded latency independent of project corpus size; stale publication cannot commit after owner authority changes; focused workflow, provenance, transition, server-control and rollout tests pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-10 00:02
---
Direct owner claimed this live control-plane starvation regression. Implementation will use an isolated OOMPAH-979 worktree while root continues the deployed rollout and provenance retirement checks.
---
<!-- COMMENTS:END -->
