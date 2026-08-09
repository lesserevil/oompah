---
id: OOMPAH-952
type: bug
status: In Progress
priority: 1
title: Retire obsolete landed reviews and exact capacity reservations
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-09T10:48:29.754525Z'
updated_at: '2026-08-09T11:17:16.229707Z'
work_branch: OOMPAH-952
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: standalone
  task_branch: OOMPAH-952
  head_sha: 8e1ac57e2ec2e8503fd380e75c05639badcc5fba
  submitted_at: '2026-08-09T11:17:06.915915+00:00'
  updated_at: '2026-08-09T11:17:06.915915+00:00'
oompah.work_branch: OOMPAH-952
---
## Summary

Triggered by: OOMPAH-764

Triggered by OOMPAH-764 / GitHub PR #748 on 2026-08-09. A Done nested epic whose three accepted source commits were all patch-equivalent in its authoritative immediate target retained a conflicting open review and committed review-capacity reservation for more than a day. With max_in_flight_prs=1, that obsolete row blocked otherwise eligible OOMPAH-946 and OOMPAH-949. Existing OOMPAH-782/837 contracts require capacity release and restart convergence, but no open task covers this live regression.

Implementation scope: in the durable review/epic reconciliation path, bind an open review and its reservation to exact project, task, source branch, submitted head, target branch, task authority generation, and current landing fact. When authoritative exact ancestry or complete patch-equivalence proves that accepted work is already landed and the task is terminal/landing-eligible, retire the obsolete open review and release only its matching committed reservation. Preserve legitimate Done-but-unlanded reviews, wrong-target reviews, partial/ambiguous patch equivalence, advanced source heads, nonterminal revisions, forge uncertainty, and stale workflow generations. Make close/release idempotent and restart-safe, and prevent a later stale cache publication from re-adopting the retired review.

Relevant code: oompah/review_workflow.py, oompah/review_workflow_adapter.py, oompah/epic_workflow.py, oompah/epic_workflow_adapter.py, oompah/review_capacity.py, orchestrator live-review reconciliation/standalone or epic cleanup. Tests: reproduce OOMPAH-764 with a conflicted open review plus exact complete patch-equivalent landing and capacity=1; assert exact review close and reservation release unblock the next delivery. Add ancestry, restart/idempotence, stale-cache race, wrong target, partial/conflicting proof, advanced head, nonterminal and forge-failure fail-closed cases. Acceptance: an obsolete exact review cannot hold project capacity after authoritative landing is proven; valid in-flight reviews are never retired; the next eligible Ready task naturally acquires the released slot.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-09 11:16
---
Implemented durable epic auto-close retirement: revalidate exact landed source/target/head, authoritatively inspect open reviews, bind and retire only matching review capacity under issue/project locks, persist exact epic review reservation authority/head, and fail closed on source drift, wrong targets, conflicting capacity routes, or unavailable forge state. Verification: 503 related workflow/review/capacity tests passed; focused epic workflow suite 88 passed; terminal mutation scan and secret scan passed.
---
<!-- COMMENTS:END -->
