---
id: OOMPAH-512
type: bug
status: In Progress
priority: 1
title: Route managed tracker mutations through project-scoped trackers
parent: OOMPAH-511
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-28T15:16:42.904572Z'
updated_at: '2026-07-28T15:17:22.359359Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Implementation scope

Remove writable legacy/global tracker use from managed-project runtime paths. Audit Orchestrator construction and every server, watcher, maintenance, release-delivery, and fallback call site that reads or mutates orch.tracker/self.tracker. For any operation associated with a managed project, resolve the tracker through _tracker_for_project(project_id) (or a single shared public helper) so OompahMarkdownTracker receives the project's repository path, state_branch_enabled, state_branch_name, shadow-write, and migration-stage settings. Do not silently use os.getcwd() when a project store exists. Preserve an explicit standalone tracker path only for deployments with no managed project store.

Relevant files

oompah/orchestrator.py, oompah/server.py, oompah/error_watcher.py and other confirmed orch.tracker consumers, plus tests following existing project-scoped tracker patterns.

Required tests

Add unit regressions for managed-project construction and each changed consumer. Prove mutation paths use the requested project tracker and never the process-cwd tracker. Prove standalone/no-project-store behavior still works. Run focused orchestrator/server/watcher tests and make test.

Acceptance criteria

No managed-project mutation path can reach a writable cwd-derived tracker; project-specific state-branch settings are present on every managed OompahMarkdownTracker; ambiguous operations fail with an actionable error instead of guessing; standalone compatibility remains covered; all tests pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-28 15:17
---
Implementation started manually in the isolated epic worktree. First step is to inventory every legacy/global tracker consumer and define the explicit managed versus standalone tracker contract.
---
<!-- COMMENTS:END -->
