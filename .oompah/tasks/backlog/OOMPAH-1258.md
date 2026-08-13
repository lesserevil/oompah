---
id: OOMPAH-1258
type: task
status: Backlog
priority: null
title: Complete direct epic maintenance through the durable workflow
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-13T22:41:28.315466Z'
updated_at: '2026-08-13T23:11:58.708415Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.create_once:
  version: 1
  project_id: proj-14849f1b
  operation_kind: api_task_create
  creation_marker: cc0c5a04-711a-4b53-9ccb-aa96ce836044
  request_fingerprint: c9ce64ee590cb20387926be736d3c23fe19e5d785cc955861f8d6da1d7b17b01
---
## Summary

Live follow-up to OOMPAH-1257. In all-enforce mode, a recognized direct epic rebase helper can be audited to Done while its exact integration record remains state=ready. The disabled legacy _process_integration_queues sweep is currently the only code that calls complete_direct_epic_maintenance_submission to reconcile the published parent ref, persist maintenance_publication_proven/integrated, cancel the stale ordinary queue row, and converge the parent rebase label. The durable IntegrationWorkflow instead evaluates the Done helper as ordinary landing work and exhausts integration_landing_refresh (live reproducer TRICKLE-141 / parent TRICKLE-130). Implement a task-scoped durable integration action for recognized direct maintenance ready evidence, with exact project/task/branch/head/evidence-generation revalidation and idempotent observation/apply/verification. It must call the existing guarded completion primitive without enabling any project-wide legacy lifecycle writer; supersede the generic landing-refresh generation once proof is durable; reuse already-completed exact audit evidence safely; and preserve fail-closed behavior for spoofed metadata, changed heads/targets, stale jobs, pause, restart, and ordinary queue tasks. Relevant files: oompah/work_decision.py, oompah/integration_workflow.py, workflow action routing/receipts, and focused workflow/integration tests. Required tests: production-shaped noncanonical helper in Ready and Done with state=ready schedules only the maintenance-completion action; action persists integrated proof and parent convergence; restart/replay observes success without repeating unsafe publication; stale/foreign/spoofed generations are rejected; ordinary tasks remain unchanged. Acceptance: after deployment TRICKLE-141 naturally converges without SQLite/task-ledger edits, TRICKLE-130 loses stale rebasing state, no retry.exhausted alert remains for the helper, and only Trickle remains resumed.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-13 22:41
---
Claimed for direct implementation after live all-enforce reproduction: TRICKLE-141 is correctly classified as a noncanonical direct helper, but state=ready is routed to generic integration_landing_refresh because the only ready-to-proven conversion remains in the disabled legacy project sweep. Implementing a task-scoped durable maintenance-completion action; no project-wide writer will be re-enabled.
---
author: oompah
created: 2026-08-13 23:11
---
Implementation underway on branch OOMPAH-1258. Added a durable direct_epic_maintenance_completion integration action selected for exact Ready/Done helpers instead of generic landing refresh; it revalidates project/task/status/branch/head/evidence under the shared task mutex, calls the existing guarded completion primitive, observes proof plus parent rebase-state/label convergence, and handles the post-cancel/pre-label crash boundary idempotently. Validation: 729 focused workflow/runtime/orchestrator tests passed; 424 direct affected tests passed; terminal mutation scan 21/21; diff check clean. Independent review in progress.
---
<!-- COMMENTS:END -->
