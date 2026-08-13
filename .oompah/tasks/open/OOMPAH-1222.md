---
id: OOMPAH-1222
type: task
status: Open
priority: null
title: Do not exhaust standalone delivery while waiting for review capacity
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-13T06:00:42.489158Z'
updated_at: '2026-08-13T07:23:21.561028Z'
work_branch: OOMPAH-1222
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.create_once:
  version: 1
  project_id: oompah
  operation_kind: api_task_create
  creation_marker: a69d81a1-c7cc-428e-96e5-30861dd2eeb2
  request_fingerprint: 282feaf6d1cba4c5475da05bde8327339074a59963c881e2aca2041aea61e268
oompah.lifecycle_revision: 1
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: standalone
  task_branch: OOMPAH-1222
  head_sha: 3769a6310e406692118d04c115b81254859de829
  submitted_at: '2026-08-13T07:23:12.795525+00:00'
  updated_at: '2026-08-13T07:23:12.795525+00:00'
oompah.work_branch: OOMPAH-1222
---
## Summary

Bug observed live on Trickle on 2026-08-13: Ready tasks TRICKLE-122/124/131/132/135/137 had exact accepted submissions and were correctly waiting behind the configured 1/1 forge-review cap, while standalone_delivery raised a transient WorkflowActionError on every pass. The durable workflow consumed its bounded substantive failure budget and projected retry.exhausted/action_required even though the same UI simultaneously reported a normal informational capacity wait. Scope: propagate exact pre-effect capacity/resource deferral from the task-scoped standalone delivery path as WorkflowAdministrativeDeferral (or equivalent non-substantive durable outcome), preserving generation/lease fences, bounded retry backoff, fairness, capacity-wakeup continuation, and truthful informational projection. Retire or supersede previously exhausted standalone_delivery authority when the exact accepted submission remains current so restart/live reconciliation naturally rearms it without operator action. Do not make forge failures, ambiguous post-effect results, gate failures, invalid submission metadata, or genuine delivery errors free. Relevant code includes oompah/orchestrator.py, oompah/integration_workflow.py, workflow worker/job exhaustion authority, and liveness projection. Required tests: more than max_attempts at-capacity passes preserve attempt budget and exact checkpoint; release of capacity executes the same generation; stale/replaced generations remain fenced; substantive failures still exhaust; existing exhausted capacity-wait rows recover; alerts remain informational and clear after progress. Acceptance: normal review-capacity waits never become human-action warnings, and the live Trickle Ready queue resumes automatically as capacity opens.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-13 06:07
---
Claiming directly from the live Trickle incident. OOMPAH-1221 is deployed; the remaining six Ready-task critical alerts are the exact capacity-wait exhaustion reproduction this task will fix.
---
author: oompah
created: 2026-08-13 06:52
---
Implementation complete and under full-gate verification. The fix maps only a positively proven full review queue to WorkflowAdministrativeDeferral, preserves the exact generation/checkpoint without consuming attempts, keeps unavailable forge state on substantive bounded retries, and restart-rearms only authoritative legacy exhausted rows whose exact checkpoint branch/head still matches the current Ready standalone submission. Focused integration/runtime/job/standalone suites: 528 passed; full make test is in progress.
---
author: oompah
created: 2026-08-13 07:23
---
Implemented exact non-substantive review-capacity deferrals and authoritative startup recovery for legacy exhausted standalone-delivery rows. Focused suites: 528 passed; full make test: 20,226 passed, 7 skipped, 2 xfailed; hosted Python 3.11/3.12/3.13 gates all passed. PR #852.
---
<!-- COMMENTS:END -->
