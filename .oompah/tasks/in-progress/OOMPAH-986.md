---
id: OOMPAH-986
type: bug
status: In Progress
priority: 1
title: Prevent terminal-audit churn from starving unrelated workflow publication
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-10T04:41:10.778919Z'
updated_at: '2026-08-10T04:41:33.306226Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Triggered by: OOMPAH-981

Live regression on 2026-08-10 after OOMPAH-979: OOMPAH-981 PR #793 reached green protected CI with mergeStateStatus=CLEAN, but project proj-14849f1b repeatedly logged durable workflow publication superseded at 04:26:08, 04:36:54, and 04:39:50 UTC because OOMPAH-983's long-running terminal-audit disposition changed during each corpus-wide collection. OOMPAH-979 bounded the project publication lock and correctly added project-wide revision fences, but legitimate activity in the terminal-audit lane can now invalidate every full-project cut indefinitely and starve unrelated review/integration decisions. Implement task- or lane-scoped publication authority (or an equivalent convergent partial/retry mechanism) so a terminal-audit disposition mutation supersedes decisions that depend on that task/audit while unrelated exact review/merge decisions can publish. Preserve fail-closed same-task terminal authority, OOMPAH-968 absent-to-retained provenance fencing, tracker/workflow owner authority fencing, atomic durable snapshot/job publication, restart idempotence, and cross-project isolation. Relevant code: oompah/workflow_runtime.py, workflow fact/publication authority composition, terminal-audit metadata/lane proof sources, and tests/test_workflow_runtime.py. Required tests: deterministically hold a 200-task publication while one In Validation audit advances through repeated disposition/heartbeat changes and one unrelated In Review PR becomes green; prove the audit-dependent projection supersedes or is refreshed while the unrelated review_merge effect publishes exactly once without waiting for audit completion; prove a same-task audit/provenance race cannot publish stale authority; prove a project pause/owner mutation still fences all affected dispatch; prove restart/replay and repeated churn converge without duplicate effects. Acceptance: continuous terminal-audit progress cannot starve an unrelated review/integration lane; exact authority remains atomic at the affected task/lane boundary; focused workflow/runtime, audit, review, persistence, and scaling tests pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

