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
updated_at: '2026-08-10T00:53:16.559194Z'
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
author: oompah
created: 2026-08-10 00:10
---
Additional live race evidence from generation 923: collection observed newly created OOMPAH-979 as Backlog, the supported owner claim changed it to In Progress by 00:02 UTC, but generation 923 still published at 00:08:37 with the stale Backlog decision. Liveness then reported exactly one unexplained divergence (evidence.task_status_mismatch) while current exhausted was zero. The authority revision/digest fence must cover task lifecycle/owner-control mutations as well as terminal metadata, causing stale publication to supersede/retry.
---
author: oompah
created: 2026-08-10 00:51
---
Implemented generation-wide publication authority fencing and bounded owner-control latency. Final stable coverage includes native state-branch CAS, explicit legacy grouped digest fallback, generic unversioned fail-closed behavior, terminal metadata/workflow authority revisions, 200-task terminal-provenance scaling with no final per-task tracker refresh, pause/owner races, structured retryable 503s, and lock observability. Combined touched suites: 760 passed; make check-secrets and git diff --check passed. Preparing the reviewed commit/push; task is intentionally not submitted and service is not restarted.
---
author: oompah
created: 2026-08-10 00:53
---
Implementation is committed and pushed on branch OOMPAH-979 at 7fc8bc8ea4a36c952a96349406a173c6b85ec94e. Exact pushed head verification: 760 touched-suite tests passed in 10.38s; make check-secrets passed; git diff --check clean; worktree is clean and up to date with origin/OOMPAH-979. Final review found no remaining correctness or lock-order blockers. Per handoff, the task has not been submitted and the server has not been restarted.
---
<!-- COMMENTS:END -->
