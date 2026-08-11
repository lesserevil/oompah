---
id: OOMPAH-1088
type: bug
status: In Progress
priority: 1
title: Bound dispatch and submission authority waits and retire pre-provider ghost
  runtimes
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-11T14:17:03.737871Z'
updated_at: '2026-08-11T14:17:38.354485Z'
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
  creation_marker: oompah-1084-ghost-runtime-authority-wait-20260811
  request_fingerprint: c98e8d47cff8518ba6b61b5b4d7732332ff6772202a465bb517416cd137201f1
---
## Summary

Triggered by: OOMPAH-1084

Incident: during OOMPAH-1084 recovery on 2026-08-11, the scheduler published a RunningEntry for a Needs CI Fix repair at 14:03:36, but provider_started remained false and no provider process, session, events, tokens, or workspace ever existed. An exact task submission at 14:04:05 then waited indefinitely in the submission authority lock through CrossLoopTaskLock. A supported direct-owner claim revoked and retired the visible ghost runtime, but the blocked submission handler retained authority or task mutex state and caused its workflow job to quarantine. The quarantine-triggered graceful restart reached running=0 yet hung indefinitely waiting for the orphaned request connection, requiring make force-restart. Scope: place deterministic bounded waits around dispatch publication, provider startup, direct-owner takeover, submission authority acquisition, and request teardown; automatically retire pre-provider runtime generations that fail to establish a provider/session by their deadline; guarantee retirement releases all cross-loop task locks and cancels or completes waiting request handlers; make owner-claim and exact submission converge idempotently after a race; and expose actionable structured evidence without creating false active-agent UI state. Relevant areas include orchestrator dispatch lifecycle, RunningEntry publication, submission authority locks, CrossLoopTaskLock ownership, implementation workflow direct_owner_claim, workflow quarantine recovery, and graceful restart connection drainage. Required tests: pre-provider dispatch followed by owner claim and exact submit must complete within a bounded deadline; provider startup failure must not leave a visible runtime or lock; concurrent claim/submit orderings must converge exactly once; cancellation and restart must release request handlers and task mutexes; repeated replay must be idempotent; a real started provider must retain normal fencing. Acceptance: no API request can wait indefinitely on orphaned task authority, zero-work graceful restart cannot be held open by a retired submission handler, pre-provider ghosts self-retire with durable evidence, focused race/restart tests and terminal mutation scan pass, and the full protected gate is green.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

