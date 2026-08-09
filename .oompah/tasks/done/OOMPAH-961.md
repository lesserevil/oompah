---
id: OOMPAH-961
type: bug
status: Done
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
updated_at: '2026-08-09T17:42:23.094418Z'
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
oompah.terminal_audit:
  queued_comment_posted: true
  oompah.terminal_audit_tracker_projections:
  - version: 1
    audit_id: audit-27f83a2fcb9b
    project_id: proj-14849f1b
    task_id: OOMPAH-961
    digest: ec437060ca69f1d6bcea6931fd5a53a1b42b0ad7d3566aef0ccd130899c9f4cc
  - version: 1
    audit_id: audit-d86ef4ac6f35
    project_id: proj-14849f1b
    task_id: OOMPAH-961
    digest: ec437060ca69f1d6bcea6931fd5a53a1b42b0ad7d3566aef0ccd130899c9f4cc
  oompah.terminal_override_records:
  - version: 1
    override_id: override-269d8d039c82
    project_id: proj-14849f1b
    task_id: OOMPAH-961
    target_state: Done
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: ec437060ca69f1d6bcea6931fd5a53a1b42b0ad7d3566aef0ccd130899c9f4cc
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: Direct-owner completion after exact combined hosted CI and independent
      no-blocker review.
    created_at: '2026-08-09T17:42:06.021455+00:00'
    selected_ref: b4d84c207fe2160dfbd502ffd9b0f95ff561142a
    selected_sha: b4d84c207fe2160dfbd502ffd9b0f95ff561142a
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-961
    target_state: Done
    evidence_fingerprint: ec437060ca69f1d6bcea6931fd5a53a1b42b0ad7d3566aef0ccd130899c9f4cc
    audit_ids:
    - audit-27f83a2fcb9b
    - audit-d86ef4ac6f35
    kind: override
    applied: true
    retired_at: '2026-08-09T17:42:15.226156+00:00'
  oompah.terminal_audit_result_intents: []
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-27f83a2fcb9b
    project_id: proj-14849f1b
    task_id: OOMPAH-961
    target_state: Done
    request_state: cancelled
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: ec437060ca69f1d6bcea6931fd5a53a1b42b0ad7d3566aef0ccd130899c9f4cc
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: Open
    created_at: '2026-08-09T17:41:58.996428+00:00'
    selected_ref: b4d84c207fe2160dfbd502ffd9b0f95ff561142a
    selected_sha: b4d84c207fe2160dfbd502ffd9b0f95ff561142a
    updated_at: '2026-08-09T17:42:15.226113+00:00'
  - version: 1
    audit_id: audit-d86ef4ac6f35
    project_id: proj-14849f1b
    task_id: OOMPAH-961
    target_state: Merged
    request_state: cancelled
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: ec437060ca69f1d6bcea6931fd5a53a1b42b0ad7d3566aef0ccd130899c9f4cc
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: Open
    created_at: '2026-08-09T17:41:58.996428+00:00'
    selected_ref: b4d84c207fe2160dfbd502ffd9b0f95ff561142a
    selected_sha: b4d84c207fe2160dfbd502ffd9b0f95ff561142a
    updated_at: '2026-08-09T17:42:15.226140+00:00'
  attempt_history: []
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
author: oompah
created: 2026-08-09 15:25
---
Final composition head e62a46da73246fe7f27ff857e9a153f6dc008784 is pushed. It merges current main be4ec5d95 (including OOMPAH-960) into the corrected proof-validation head; origin/main is an ancestor. Combined overlap validation: 606 workflow/integration/epic tests passed, terminal mutation scan passed, and secret scan passed. PR #769 points to this exact head and hosted CI has restarted (3.11/3.12 running, 3.13 queued at observation).
---
author: oompah
created: 2026-08-09 15:38
---
Exact-head correction is implemented and locally green. Published retirement now references an immutable per-task authority cut, so a later bounded-unselected cursor snapshot or membership-only snapshot cannot resurrect retired exhaustion; explicit rearm still deletes the per-job proof and restores actionability. Tests: 98 workflow-job tests and 606 OOMPAH-960/961 composition tests passed; terminal-audit and secret scans passed. Preparing the commit and current-main composition now.
---
author: oompah
created: 2026-08-09 15:39
---
Exact corrected head c5cafe260119d383d4ff30055f82702db69e2c03 is pushed on PR #769. Durable immutable per-task authority cuts prevent later bounded-unselected cursor or membership-only publications from resurrecting retired exhaustion; explicit rearm remains the ABA boundary. Exact-tree validation: 98 workflow-job tests and 606 combined OOMPAH-960/961 tests passed; terminal-audit scan, secret scan, and diff check passed. origin/main be4ec5d95 is an ancestor; hosted CI is running on 3.11/3.12/3.13.
---
author: oompah
created: 2026-08-09 16:03
---
Final exact head 2d693d7b17df91cb6fe781fa47451a72638bc4e2 fixes rollback-vs-explicit-rearm ABA with append-only event-sequence fencing. Independent re-review found no blockers: capture/rearm/rollback/fresh exhaustion remains actionable; all prior proof-shape/durable-cut cases and OOMPAH-960 composition pass. 443 affected review tests and 607 author tests passed. Hosted 3.13 failed only the unrelated loaded delivery-test race now corrected by OOMPAH-957 PR #772; compose after that merge.
---
author: oompah
created: 2026-08-09 17:32
---
Final no-rewrite composition pushed at exact head c5644a86a4ccd9e223f298ae8b6b50262340217a on PR #769, with exact combined OOMPAH-962 parent dd2e18fc263f16717a7b31802968f235a4401525 and landed OOMPAH-964/O965 main. Retirement proofs, quarantine restore fencing, callback settlement, and publication-supersession regressions are all present. Validation: 22 focused workflow tests, 269 intake/webhook tests, 1,193 combined tests, critical Ruff/compile, terminal mutation, secret, and diff checks pass. Hosted exact matrix and independent final composition review are running in parallel with PR #770.
---
author: oompah
created: 2026-08-09 17:42
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-09 17:42
---
Override by oompah-cli: terminal transition to Done applied by project owner.

Reason: Direct-owner completion after exact combined hosted CI and independent no-blocker review.
---
author: oompah
created: 2026-08-09 17:42
---
Merged PR #769 at d5418fa5b2345e486f94ee29ea790b8d00faa5b1. Exact combined head c5644a86a4ccd9e223f298ae8b6b50262340217a passed independent no-blocker review, 1,193 local combined tests, and hosted CI run 31326649929 on Python 3.11/3.12/3.13. Expected, branch, and landed trees all equal ab8755d263b151e505bf1784566d5588cf25b127.
---
<!-- COMMENTS:END -->
