---
id: OOMPAH-823
type: task
status: In Validation
priority: null
title: Bootstrap lifecycle reconciliation retry backoff onto main
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-05T06:45:32.566233Z'
updated_at: '2026-08-05T07:54:06.861997Z'
work_branch: OOMPAH-823
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/719
review_number: '719'
review_head: d509c08214c45bb7c0e4f93c1d42e57a01633f87
merged_at: null
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  task_branch: OOMPAH-823
  head_sha: d509c08214c45bb7c0e4f93c1d42e57a01633f87
  submitted_at: '2026-08-05T07:26:16.478559+00:00'
  updated_at: '2026-08-05T07:26:16.478559+00:00'
oompah.review_url: https://github.com/lesserevil/oompah/pull/719
oompah.review_number: '719'
oompah.work_branch: OOMPAH-823
oompah.target_branch: main
oompah.review_head: d509c08214c45bb7c0e4f93c1d42e57a01633f87
oompah.terminal_audit:
  queued_comment_posted: true
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-a40e05f2de1d
    project_id: proj-14849f1b
    task_id: OOMPAH-823
    target_state: Done
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 40cf76507cb99b49895f29bbefc51870fbbed30c3e0e012c48a97d0f6d6f6a34
    attempts: []
    requested_by:
      version: 1
      identity: yolo-merge
      source: oompah
    previous_state: In Review
    created_at: '2026-08-05T07:53:06.996118+00:00'
  - version: 1
    audit_id: audit-76196b8784e7
    project_id: proj-14849f1b
    task_id: OOMPAH-823
    target_state: Merged
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 40cf76507cb99b49895f29bbefc51870fbbed30c3e0e012c48a97d0f6d6f6a34
    attempts: []
    requested_by:
      version: 1
      identity: yolo-merge
      source: oompah
    previous_state: In Review
    created_at: '2026-08-05T07:53:06.996118+00:00'
  attempt_history: []
---
## Summary

Urgent standalone deployment bootstrap for systemic child OOMPAH-822. The currently deployed main server retry-spins failed terminal lifecycle reconciliation rows OOMPAH-452/453/455/456 above 30,000 attempts, rewriting+fsyncing ~835 KiB service state 10-13 times/sec and starving the only OOMPAH-814 exact gate. Implement on current main the bounded scheduler/ledger fix specified by OOMPAH-822: pending-first fair cursor, durable failed-row next-at exponential backoff and bounded exhaustion/action-required state, one coalesced persistence checkpoint per batch (except pre-external-effect intent where required), scheduler delay from earliest due retry with a nonzero floor, restart/transient recovery, and observability without a hot loop. Required tests: four permanent failed rows plus later pending rows; retry not due/due across restart; no starvation; bounded persist and reschedule counts; transient recovery; schedule coalescing; state endpoint responsiveness. Acceptance: deploying this standalone patch stops continuous lifecycle fsync immediately, drains pending rows fairly, preserves fail-closed reconciliation, and lets exact validation gates run. OOMPAH-822 will record the reviewed logical patch on epic-OOMPAH-763 after this main bootstrap merges.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-05 07:06
---
Implementation is complete and pushed for independent review at exact head 2f9984c6a03c1c5d846d7a6c1970fed1bd4b49a8 on origin/OOMPAH-823 (base origin/main 9ea2b552). The patch adds pending-first cursor selection, durable exponential due-at/backoff and bounded exhaustion/action-required state, operator-change retry epochs, one coalesced outcome checkpoint per batch with fail-closed pre-effect intent durability, earliest-due scheduler timing with a nonzero floor, and single-timer wakeup coalescing. Verification: 194 focused tests passed in the branch-local environment (terminal audit enforcement, config, and orchestrator state persistence), terminal mutation scan 8/8 passed, check-secrets passed, and diff checks are clean. Owner claim is intentionally retained and the task has not been submitted pending exact-head review/landing.
---
author: oompah
created: 2026-08-05 07:22
---
Independent-review repairs are complete and pushed at new exact head d509c08214c45bb7c0e4f93c1d42e57a01633f87 on origin/OOMPAH-823. P1: project snapshot failures now defer that scope without consuming row attempts, and absence exhaustion reopens when the task becomes visible. P2: discovery events arriving during an active lifecycle future are retained as one coalesced rediscovery edge and replayed after completion, including otherwise idle/exhausted results. P3: a deterministic API regression holds the third repeated serialized 850 KiB lifecycle checkpoint blocked while /api/v1/state responds from its cached snapshot. Verification: 217 focused tests passed in the branch-local environment; terminal mutation scan 8/8 passed; check-secrets and diff checks passed. The task remains unsubmitted and the owner claim is retained for exact-head independent review/landing.
---
author: oompah
created: 2026-08-05 07:26
---
Bounded lifecycle reconciliation retries, pending-first fairness, durable backoff/exhaustion, lossless rediscovery, coalesced persistence, and responsive state API verified at exact head d509c08214c45bb7c0e4f93c1d42e57a01633f87.
---
author: oompah
created: 2026-08-05 07:41
---
Branch quality gate passed for `d509c08214c45bb7c0e4f93c1d42e57a01633f87` using `make test` in 772.9s. Review creation may proceed.
---
author: oompah
created: 2026-08-05 07:53
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-05 07:54
---
YOLO: merged PR #719.
---
<!-- COMMENTS:END -->
