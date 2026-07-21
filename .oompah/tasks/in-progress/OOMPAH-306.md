---
id: OOMPAH-306
type: bug
status: In Progress
priority: 1
title: Reconcile dashboard task state with canonical state-branch records
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-21T16:27:56.291769Z'
updated_at: '2026-07-21T16:42:22.489418Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 1a5b4d70-8711-4a4d-ba70-e5528bd0c3db
---
## Summary

Fix the dashboard/API task-state display when it disagrees with Oompah’s canonical state branch.\n\nReproduction: OOMPAH-286 displays as Merged even though the canonical record on oompah/state/proj-14849f1b has status=Backlog, parent=OOMPAH-285, and null work_branch, review_url, and merged_at.\n\nRequirements:\n- For state-branch-enabled native projects, every board/list/detail/CLI read must use the current configured state-branch revision, not source-branch files or stale snapshots.\n- Cache keys/invalidation must include project ID, state branch, tracker revision, and task identifier.\n- Board, drawer, API, and CLI must agree on status, parent, branch, review URL, and merged timestamp.\n- If state reads are stale/unavailable, display an explicit indicator; never silently render obsolete state as authoritative.\n- Do not mutate task data to repair this display problem.\n\nTests:\n- Regression fixture where stale source/cache says Merged but state branch says Backlog; all views show Backlog.\n- Checkpoint update invalidates task list/detail caches without restart.\n- Verify per-project isolation and null merged_at cannot render Merged.\n- Verify degraded reads retain no false terminal status.\n\nAcceptance criteria:\n- Dashboard, detail pane, CLI/API, and canonical Markdown agree.\n- A task is Merged only when canonical state records it.\n- Operators can identify stale tracker data.\n- Relevant Makefile tests pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-21 16:40
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-07-21 16:40
---
Focus: Frontend Developer
---
author: oompah
created: 2026-07-21 16:40
---
Understanding: I will trace dashboard task list/detail rendering and its API payloads, then ensure the UI does not present a terminal state when the state-branch read is stale or unavailable. I will add focused regression coverage and hand off any canonical tracker/cache routing work outside frontend scope.
---
author: oompah
created: 2026-07-21 16:41
---
Discovery: dashboard.html fetchIssues() discards the server's X-Oompah-Issues-Stale header, while board/detail render the returned fields as authoritative. server.py snapshot cache is keyed only as issues:all and detail:{project}:{identifier}:actor, so canonical state-branch revision routing/invalidation is backend work. Frontend scope: render an explicit accessible stale-state warning from API freshness and preserve it across board refreshes.
---
author: oompah
created: 2026-07-21 16:42
---
Implementation (frontend): added an accessible task-state freshness banner in dashboard.html. fetchIssues() now consumes X-Oompah-Issues-Stale, warns on stale or failed reads, and clears only on a fresh response. Added tests/test_dashboard_state_read_warning.py covering the banner and stale/unavailable behavior.
---
author: oompah
created: 2026-07-21 16:42
---
Verification: git diff --check passed. make test could not start because the environment's astral-uv launcher failed creating a transient DBus scope (Makefile .venv/.uv-setup, exit 46), before pytest collection. Frontend regression test is included but has not run in this environment.
---
<!-- COMMENTS:END -->
