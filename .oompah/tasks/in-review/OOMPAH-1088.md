---
id: OOMPAH-1088
type: bug
status: In Review
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
updated_at: '2026-08-11T15:39:54.879838Z'
work_branch: OOMPAH-1088
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/826
review_number: '826'
review_head: 59619d68f092fd5e6078599f2a6efcce555f52f9
merged_at: null
oompah.create_once:
  version: 1
  project_id: proj-14849f1b
  operation_kind: api_task_create
  creation_marker: oompah-1084-ghost-runtime-authority-wait-20260811
  request_fingerprint: c98e8d47cff8518ba6b61b5b4d7732332ff6772202a465bb517416cd137201f1
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: standalone
  task_branch: OOMPAH-1088
  base_branch: main
  base_sha: 6449341d762d9c7645271b8479dfa406e648be54
  head_sha: 59619d68f092fd5e6078599f2a6efcce555f52f9
  submitted_at: '2026-08-11T15:21:04.895192+00:00'
  updated_at: '2026-08-11T15:39:51.523713+00:00'
  wait_reason: review_generation_requeue
  wait_generation: review:8b3e696f1994e807a80257e4aff1be9705939fb5898e05198c7556e5828c409b
oompah.work_branch: OOMPAH-1088
oompah.review_url: https://github.com/lesserevil/oompah/pull/826
oompah.review_number: '826'
oompah.target_branch: main
oompah.review_head: 59619d68f092fd5e6078599f2a6efcce555f52f9
---
## Summary

Triggered by: OOMPAH-1084

Incident: during OOMPAH-1084 recovery on 2026-08-11, the scheduler published a RunningEntry for a Needs CI Fix repair at 14:03:36, but provider_started remained false and no provider process, session, events, tokens, or workspace ever existed. An exact task submission at 14:04:05 then waited indefinitely in the submission authority lock through CrossLoopTaskLock. A supported direct-owner claim revoked and retired the visible ghost runtime, but the blocked submission handler retained authority or task mutex state and caused its workflow job to quarantine. The quarantine-triggered graceful restart reached running=0 yet hung indefinitely waiting for the orphaned request connection, requiring make force-restart. Scope: place deterministic bounded waits around dispatch publication, provider startup, direct-owner takeover, submission authority acquisition, and request teardown; automatically retire pre-provider runtime generations that fail to establish a provider/session by their deadline; guarantee retirement releases all cross-loop task locks and cancels or completes waiting request handlers; make owner-claim and exact submission converge idempotently after a race; and expose actionable structured evidence without creating false active-agent UI state. Relevant areas include orchestrator dispatch lifecycle, RunningEntry publication, submission authority locks, CrossLoopTaskLock ownership, implementation workflow direct_owner_claim, workflow quarantine recovery, and graceful restart connection drainage. Required tests: pre-provider dispatch followed by owner claim and exact submit must complete within a bounded deadline; provider startup failure must not leave a visible runtime or lock; concurrent claim/submit orderings must converge exactly once; cancellation and restart must release request handlers and task mutexes; repeated replay must be idempotent; a real started provider must retain normal fencing. Acceptance: no API request can wait indefinitely on orphaned task authority, zero-work graceful restart cannot be held open by a retired submission handler, pre-provider ghosts self-retire with durable evidence, focused race/restart tests and terminal mutation scan pass, and the full protected gate is green.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-11 14:18
---
Direct-owner recovery claimed. Reproduced from the live OOMPAH-1084 incident: a pre-provider scheduler runtime retained submission authority after retirement, quarantined the owner-claim job, and held graceful shutdown open at running=0. Implementation is starting from deployed main 6a0f7210 with focused concurrent claim/submit, provider-start failure, lock release, and restart-drain regressions.
---
author: oompah
created: 2026-08-11 14:34
---
Implemented the exact pre-provider ghost/deadlock repair on the claimed branch. CrossLoopTaskLock now supports bounded acquisition; exact submission returns structured retryable submission_authority_busy instead of retaining an HTTP connection; durable direct-owner claims retry cleanly instead of quarantining; and canceled/slow pre-provider contributor evidence releases task authority within a bounded grace period without provider/workspace contact, with structured retirement evidence and budget rollback. Focused evidence currently green: 224 authority/owner/provider tests, 340 submission/handoff tests, 51 workflow-boundary/event-loop tests, compileall, and terminal mutation scan (21/21 allowlisted). Final diff/secret checks and push are in progress; not submitted or merged.
---
author: oompah
created: 2026-08-11 14:37
---
Implementation is committed and pushed for independent exact-head review at be44b790c626d061747b205853ec21f602821c63 on origin/OOMPAH-1088. Exact working-tree evidence: 422 authority/owner/provider/submission/workflow-boundary tests passed; full task-handoff suite 123 passed; focused deadlock regressions 7 passed; compileall passed; make terminal-audit-scan passed (21 identified, 21 allowlisted); paranoid secret scan and commit hooks passed. Branch is clean and matches origin. The task remains In Progress and has not been submitted or merged, per handoff.
---
author: oompah
created: 2026-08-11 14:57
---
Independent-review blockers repaired and replacement exact head pushed: 9df3e881490b5a7c5eb5bbf304e07a0695c72fd3 on origin/OOMPAH-1088, rebased onto origin/main fe9599111d478b8221a2949c878fecb61d558760. The durable workflow worker-exit path now removes the exact RunningEntry and scheduler claims after publishing its successor disposition, eliminating the provider_started=false ghost. Contributor provenance read/merge/write now has a metadata-only per-task serialization lane independent of lifecycle authority; a late timed-out write retains that lane until it settles, and successor generations retire before provider contact instead of racing a stale whole-document write. New deterministic regressions cover timeout -> real worker exit -> running/claims absent -> implementation retry plus direct-owner/submission lane availability, and late provider A vs successor provider B evidence preservation/contact fencing. Exact final evidence: 502 authority/owner/provider/provenance/submission/workflow-boundary tests passed; full task-handoff suite 123 passed; compileall and git diff --check passed; terminal mutation scan passed 21/21; paranoid secret scan and commit hooks passed. Branch is clean and matches origin. Task remains In Progress and is not submitted or merged pending independent exact-head re-review.
---
author: oompah
created: 2026-08-11 15:13
---
Independent-review blockers are repaired and replacement exact head 59619d68f092fd5e6078599f2a6efcce555f52f9 is pushed on origin/OOMPAH-1088, rebased onto origin/main 6449341d762d9c7645271b8479dfa406e648be54. Synchronous legacy task-authority locks are now polled only through non-blocking acquisition, never block the event loop through a bare acquire call, and are released exactly when owned; bounded async acquisition is preserved. Deterministic unlocked and contended regressions cover both the submission and direct-owner lanes. Terminal-provenance retain and new-revision operations now return structured retryable control_busy 503 evidence on task-authority contention and prove no metadata/status mutation. The prior exact ghost-runtime retirement and late-contributor serialization fixes remain intact. Fresh evidence: 471 broad authority/provider/provenance/submission/handoff/event-loop/restart/transition tests passed; terminal mutation scan passed 21/21; compileall, git diff check, focused ruff, paranoid secret scan, and commit hooks passed. Branch is clean and matches origin. Task remains In Progress and is not submitted or merged pending fresh independent exact-head review.
---
author: oompah
created: 2026-08-11 15:21
---
Fresh independent exact-head review ACCEPTED 59619d68f092fd5e6078599f2a6efcce555f52f9 on current main 6449341d762d9c7645271b8479dfa406e648be54. Reviewer verified exact pre-provider ghost RunningEntry/claim retirement; late contributor-writer serialization and pre-contact fencing; bounded nonblocking sync legacy-lock handling with exact finally release; bounded async/CrossLoop behavior; structured retryable submission/control-busy responses for submit, owner, and both terminal-provenance paths; and preserved final provider authority fences. Evidence: 358 independent focused tests, terminal mutation scan 21/21, compileall, diff check; branch clean and remote exact. Ready for canonical gate and integration.
---
author: oompah
created: 2026-08-11 15:21
---
Bound authority waits, retire pre-provider ghost runtimes, serialize contributor evidence, and return structured retryable contention without blocking the event loop.
---
author: oompah
created: 2026-08-11 15:31
---
Branch quality gate passed for `59619d68f092fd5e6078599f2a6efcce555f52f9` using `make test` in 183.4s. Review creation may proceed.
---
<!-- COMMENTS:END -->
