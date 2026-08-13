---
id: OOMPAH-1232
type: task
status: Open
priority: null
title: Rearm runnable workflow jobs when blocking evidence changes
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-13T10:08:08.871557Z'
updated_at: '2026-08-13T10:38:38.297950Z'
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
  creation_marker: c5389a39-0475-4191-ada8-e49be43cf34d
  request_fingerprint: 93e69203bf22fff1b3823d66fe5518d3cdd5e33c5e812ee0770173ee78c214c4
oompah.lifecycle_revision: 1
---
## Summary

Bug reproduced live on TRICKLE-138 and TRICKLE-139 after OOMPAH-1223 repaired nested hierarchy evidence. Canonical work decisions now say dispatch.eligible with current implementation_start durable jobs and no unmet prerequisites, but the current workflow rows remain retry_wait/effect_pending until roughly one hour after their prior nested_lineage_unavailable failure. Separate queued nested_dispatch_topology_repair rows also remain, so repaired evidence does not promptly retire obsolete repair authority or rearm runnable work. Implementation scope: when a decision/evidence generation changes from blocked policy to runnable, atomically supersede the obsolete retry/repair generation and materialize or make immediately available exactly one current implementation job; preserve backoff when the same failure evidence remains current; fence late effects from the old generation; work across restart and concurrent topology repair. Required tests: TRICKLE-138-shaped nested-lineage failure with long backoff, topology evidence becomes valid, next reconciliation supersedes old retry and admits one current job immediately; unchanged evidence preserves retry_at; topology-repair completion racing reconciliation cannot duplicate dispatch; restart converges; unrelated tasks/projects unchanged. Acceptance: a task projected dispatch.eligible cannot remain hidden behind retry_at inherited from superseded blocking evidence, obsolete topology repair jobs retire, and focused implementation scheduler/workflow job/liveness plus complete Makefile gates pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-13 10:38
---
Claimed directly. Root cause refined from live durable rows: nested preflight enqueues and synchronously drives nested_dispatch_topology_repair from inside a leased implementation_start job, but WorkflowJobStore.claim_next rejects every repair because any running job for the same task blocks the claim. The implementation job then administratively defers and repeats, leaving the repair queued forever. Fix will permit only this explicitly safe pre-effect implementation→topology-repair overlap, preserve all other per-task exclusion, and test restart/retry convergence and unrelated-action isolation.
---
<!-- COMMENTS:END -->
