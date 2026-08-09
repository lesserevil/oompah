---
id: OOMPAH-961
type: bug
status: Open
priority: 1
title: Retire exhausted authority across zero-job and lifecycle handoffs
parent: OOMPAH-940
children: []
blocked_by: []
start_blocked_by: []
labels:
- human-only
assignee: null
created_at: '2026-08-09T14:20:19.752110Z'
updated_at: '2026-08-09T15:21:36.608571Z'
work_branch: OOMPAH-961
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: queue
  task_branch: OOMPAH-961
  base_branch: epic-OOMPAH-940
  base_sha: 2dd74be288b81265ea4a242d7467ecc1ed9f1435
  head_sha: b4d84c207fe2160dfbd502ffd9b0f95ff561142a
  submitted_at: '2026-08-09T15:03:16.196887+00:00'
  updated_at: '2026-08-09T15:03:16.196887+00:00'
oompah.work_branch: OOMPAH-961
---
## Summary

Add an atomic durable authority marker for canonical zero-obligation decisions and workflow-domain/lifecycle handoffs so superseded exhausted jobs stop overriding the current decision only after the replacement cut is fully published. Current production evidence shows 12 Done tasks whose newer canonical landing.waiting decision materializes no job, seven managed integration/standalone exhaustions surviving transition to terminal-audit or terminal lifecycle, and three terminal epic_cleanup exhaustions remaining globally current. Do not weaken _CURRENT_EXHAUSTION_PREDICATE based on cursor movement alone. Persist a fail-closed no-job disposition or handoff tombstone in the same authority transaction, teach current-exhaustion and WorkDecisionController invariants to honor only that proof, and retain ambiguous/partial cuts as actionable. Add tests for zero-job blocked/action decisions, managed-to-event terminal-audit handoff, lifecycle-final task and epic retirement, rollback, restart, concurrent publication, ABA generation changes, and cursor-only fail-closed behavior. Acceptance: stale rows no longer produce task alerts or fail rollout health, genuinely current exhausted work remains actionable, and focused tests plus the configured branch gate pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-09 14:23
---
Implementation started on dedicated branch OOMPAH-961 at ba0859da9. Mapping durable snapshot publication, managed/event cursor authority, and current-exhaustion invariants before adding the atomic no-job/handoff proof.
---
author: oompah
created: 2026-08-09 15:00
---
Implemented durable exact-publication retirement proofs for managed zero-job/decision cuts, terminal-audit handoffs, and lifecycle-final cuts, including production runtime coordinator wiring. Proofs remain fail-closed until their exact snapshot publishes; immediate event handoffs survive snapshot rollback; active jobs are marked before late failure; current replay jobs and unrelated event lanes remain actionable; rearm clears proofs for ABA safety. Focused affected suites pass (301 + 84 tests), new targeted migration/runtime/race tests pass, terminal mutation scan and secret scan pass. Rebasing onto current main next, then repeating focused validation.
---
author: oompah
created: 2026-08-09 15:03
---
Review-ready head b4d84c207fe2160dfbd502ffd9b0f95ff561142a is pushed on OOMPAH-961 after rebasing onto current main 4b31fb659. Validation: 392 affected workflow tests passed; make terminal-audit-scan passed; make check-secrets passed. The exact-publication proof covers blocked/action zero-job decisions, production Done landing.waiting, managed-to-terminal-audit, final task/epic lifecycle, rollback/restart, skipped generations, concurrent publication, late completion, cross-domain isolation, current replay, and ABA rearm.
---
author: oompah
created: 2026-08-09 15:03
---
Implemented exact published retirement proofs for superseded exhausted authority across zero-job, terminal-audit, and lifecycle handoffs; 392 focused tests and safety scans pass at b4d84c207fe2160dfbd502ffd9b0f95ff561142a.
---
author: oompah
created: 2026-08-09 15:20
---
Addressed exact-head review blocker: the read predicate now accepts only terminal_audit_handoff NULL proofs that name a real exact terminal-audit job, or managed/lifecycle proofs whose exact cursor/final revision and snapshot publication relationships hold. Write paths reject kind/job-cut mismatches, missing proof relationships, and non-final lifecycle statuses such as Open; runtime excludes terminal maintenance identities from lifecycle-final retirement. Added corruption regressions for unknown kinds, blank/missing revisions, illegal NULL/published generation shapes, wrong managed revision, forged lifecycle-final:Open, active membership, and kind/cut mismatch. Affected suite passes: 402 tests; terminal mutation and secret scans pass. Preparing amended pushed head.
---
author: oompah
created: 2026-08-09 15:21
---
Exact corrected head 5f2814dccf069fa8a65d74421a05621fdb31e6eb is pushed and PR #769 now targets it. 402 affected tests plus terminal mutation and secret scans pass; hosted CI is queued/running on the new head.
---
<!-- COMMENTS:END -->
