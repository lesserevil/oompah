---
id: OOMPAH-1090
type: bug
status: In Progress
priority: 1
title: Keep standalone delivery authority alive across long gates and terminal staging
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-11T14:26:47.067526Z'
updated_at: '2026-08-11T14:27:55.424571Z'
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
  creation_marker: standalone-delivery-long-effect-authority-20260811
  request_fingerprint: b6ba9251b85b875b51c6525abdd27dc17cfb827d712b3b17797b91d5087ce666
---
## Summary

Triggered by: OOMPAH-1084

Live incident: OOMPAH-1084 was exactly resubmitted at accepted merged head cf3578ff00f5564a06ea31650553dca337280427 after stale audit recovery. Its durable standalone_delivery job acquired a 30-second workflow lease, then ran the canonical exact branch gate for about 190 seconds. The gate passed, but workflow authority had been revoked before publication, so the pass was discarded as a superseded delivery and the job retried. The retry reused the exact cached pass, discovered merged PR 821, and entered terminal staging, but the synchronous bridge timed out after 15 seconds while the detached operation retained task ownership; the outer delivery then recorded superseded authority and the detached operation failed its later authority CAS. Scope: give long exact gates and terminal-transition staging a dedicated lease-renewed or durable continuation whose authority remains valid for the admitted exact task, branch, head, target, review, and evidence generation; ensure an outer bridge timeout cannot revoke a detached operation that still owns the exact generation; publish one current gate result and one terminal-stage intent; cancel promptly and discard late outcomes only when exact evidence truly changes; and recover deterministically across restart. Relevant areas include integration_workflow standalone_delivery effects, workflow lease heartbeat and interruption, standalone delivery authorities, BranchQualityGate callbacks/result publication, terminal staging bridge, detached operation ownership, and transition coordinator waits. Required tests: a gate longer than the workflow lease, terminal staging longer than the bridge timeout, interruption during each phase, concurrent replacement submission, restart during the continuation, and replay after cached pass must prove one current pass/stage, no duplicate full gate, no stale mutation, and bounded cancellation. Acceptance: a normal multi-minute make test cannot self-revoke its delivery job, detached exact terminal staging is not invalidated merely because a bridge wait expires, OOMPAH-1084-style recovery reaches exact terminal audit without exhausting retries, focused workflow/gate/transition tests and terminal mutation scan pass, and protected CI is green.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-11 14:27
---
Direct owner claimed from live OOMPAH-1084 recovery. Evidence: standalone_delivery workflow-job-05cb980d332b404abbdc4b30515eced9 admitted exact cf3578ff, the roughly 190-second canonical gate passed but its outcome was discarded after the short workflow authority expired, and the cached-pass retry then exceeded the 15-second terminal-staging bridge while its detached operation still owned the task. Worktree is prepared from deployed main 6a0f7210; implementation will preserve exact cancellation while separating admitted long effects from short outer waits.
---
<!-- COMMENTS:END -->
