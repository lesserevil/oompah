---
id: OOMPAH-1130
type: bug
status: Backlog
priority: 1
title: Prevent exhausted terminal-audit recovery from starving project workflow publication
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-11T22:58:51.766509Z'
updated_at: '2026-08-11T22:58:51.766509Z'
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
  creation_marker: incident-20260811-trickle-exhausted-audit-publication-starvation
  request_fingerprint: a23088f523c0d76bd968ffb741359d6773e64e242e6d9e82e2bd933678778eb0
---
## Summary

Triggered by: OOMPAH-1127

After the Trickle GitHub-to-GitLab migration, TRICKLE-99, TRICKLE-114, and TRICKLE-115 have exhausted terminal audits. Recovery repeatedly fails with "current task evidence could not be refreshed" while the terminal-audit disposition revision changes. Every durable workflow reconciliation is then superseded with "terminal-audit disposition changed before publication". As a result, work-decision requests return 503 and none of 16 unrelated Open Trickle tasks can dispatch. A normal service restart does not converge the state.

Implementation scope:
- Audit exhausted-audit recovery in oompah/orchestrator.py and terminal-authority publication fencing in oompah/workflow_runtime.py.
- Ensure a failed/no-op attempt to route an exhausted audit does not advance terminal authority or continuously supersede workflow publication.
- Isolate an unrecoverable audit task so unrelated task decisions for the same project can still be published safely.
- Make native-tracker evidence refresh after a forge cutover either succeed with the current project binding or produce one bounded actionable recovery state.
- Apply retry backoff and stable diagnostics rather than a five-second mutation/publication loop.

Required tests:
- Reproduce an exhausted terminal audit whose evidence refresh fails on every attempt and assert terminal authority remains stable after the first recorded failure.
- Verify workflow publication and implementation admission continue for unrelated Open tasks in the same project.
- Verify the affected audit task is retained in an actionable safe state and cannot be incorrectly terminalized.
- Cover restart reconstruction and project forge/credential cutover bindings.

Acceptance criteria:
- One unrecoverable terminal audit cannot starve project-wide workflow publication.
- Work-decision endpoints remain available for unaffected tasks.
- Retries are bounded/backed off, observable, and do not create a tight log loop.
- The three affected Trickle audits can converge or be routed for operator action without manual database edits.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

