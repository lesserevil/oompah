---
id: OOMPAH-1221
type: task
status: Open
priority: null
title: Accepted integration submissions must preempt implementation dispatch
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-13T05:19:06.019608Z'
updated_at: '2026-08-13T05:58:24.869411Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.create_once:
  version: 1
  project_id: oompah
  operation_kind: api_task_create
  creation_marker: e27c0303-bd1e-4eda-a993-267b894fdfa2
  request_fingerprint: 5111a3df750124b1bb3921dfea79e59f57e7038b91724e04203367574ce50d73
oompah.lifecycle_revision: 1
---
## Summary

Bug: a task can carry an exact accepted integration record (integration.state=ready with branch/head/submitted_at) while tracker status remains Open or In Progress after a transition race or restart. The implementation decision currently ignores that accepted delivery authority for ordinary work, emits implementation_start/recovery, and eventually exhausts retries. Live examples on 2026-08-13 included TRICKLE-118/119/121/124/131/135 and redundant redispatch of TRICKLE-120/132/133. Scope: make exact accepted integration authority win before implementation eligibility/recovery and transition the task to Ready to Integrate through the generation-fenced transition service; suppress or supersede stale implementation jobs and revoke any redundant running implementation authority. Relevant code: oompah/work_decision.py, workflow controller/runtime/adapters, transition guards. Tests must reproduce Open and In Progress tasks with accepted standalone and queue submissions, restart reconstruction, exhaustion history, and a race where submission lands between decision publication and worker admission. Acceptance: accepted work is never reimplemented, task converges to Ready to Integrate, integration-owned jobs are materialized, stale implementation jobs/agents cannot mutate, alerts clear without operator action, and all focused/full tests pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-13 05:19
---
Claiming directly. The live reproduction has six exhausted completed submissions plus three redundant implementations admitted after restart; OOMPAH-1218 prevents status drift for new assignment transitions but accepted submission authority still needs to preempt implementation decisions.
---
author: oompah
created: 2026-08-13 05:58
---
Implemented and pushed 27c9bd1ae with PR #851. Accepted integration records now preempt implementation decisions and final worker admission; restart reconstruction materializes exact validation-submission recovery; Open recovery is restricted to orchestration authority. Verification: 541 focused tests passed, secret scan passed, and the broad gate reached 4,423 passing tests before it was restarted for the final authority-fence edit. Hosted Python 3.11/3.12/3.13 checks are running.
---
<!-- COMMENTS:END -->
