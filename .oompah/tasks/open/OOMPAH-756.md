---
id: OOMPAH-756
type: bug
status: Open
priority: 1
title: Reconcile already-landed nested epics from In Review
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-04T11:07:47.294756Z'
updated_at: '2026-08-04T11:08:50.284281Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: d89af1c468e2957d88adc6c1ed1ca4f822c1739f339ee7236032fa6b1c81379e
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: d6bfb83a-1575-4dd8-bdd9-975cc515c36f
  claim_owner: bb82706b-fb95-42cd-a68d-43d670f815c6
  claimed_at: '2026-08-04T11:08:29.581253+00:00'
  claim_expires_at: '2026-08-04T11:38:29.581253+00:00'
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 29f767ab-dd9e-407b-aa72-6231c26c409d
---
## Summary

Triggered by: EXOCOMP-128

Regression/incomplete implementation of OOMPAH-748 on live revision 5368e236. EXOCOMP-128 remains In Review with no open review even though GitHub PR 21 merged epic-EXOCOMP-128 into its authoritative immediate target epic-EXOCOMP-127 at merge commit 2476a39252e92b4690337d7fe706d1b28781bd60, that merge commit is reachable from origin/epic-EXOCOMP-127, and multiple independent terminal auditors previously returned PASS for Merged. OOMPAH-748 head d4282363 is live, but it changed only _epic_auto_close_check. Existing nested epics already routed to In Review by the old lifecycle cycle do not naturally re-enter that auto-close path. The live scheduler instead repeatedly runs epic review readiness, reports historical child task branches as unverifiable, and defers EXOCOMP-128 as if a new review were needed, despite the authoritative merged review already existing. This continues to block parent EXOCOMP-127. Implementation scope: make merged-review and stale-In-Review reconciliation target-relative for nested epics; recognize an authoritative provider review whose source is the nested epic branch, target is the immediate parent branch, and merge commit is reachable from that parent; route terminal state through the coordinator using existing Done/Merged audit evidence or a fresh bounded audit; do not reopen a review or require deleted/private child branch refs after the epic review has landed; make restart reconciliation idempotent and preserve wrong-target, missing-merge, source-advanced, and premature-root protections. Relevant code: _epic_auto_close_check, _label_merged_epics, stale/deferred In Review reconciliation, _open_epic_main_prs readiness ordering, nested target resolution, terminal lifecycle coordinator, and provider review evidence. Required tests: exact EXOCOMP-128 restart state (In Review, merged PR to parent, merge reachable, prior passing audits); source branch present and deleted; historical child private refs absent; wrong target; merge not reachable; parent not yet on main; later parent landing; duplicate ticks/restarts. Acceptance criteria: a nested epic already landed on its immediate parent cannot remain In Review waiting for a new review or root-main landing; it reaches the target-relative audited terminal state and unblocks its parent, while root epics still cannot become Merged before main landing; focused epic, review reconciliation, audit lifecycle, and restart tests plus make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-04 11:08
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-04 11:08
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
