---
id: OOMPAH-768
type: epic
status: Needs Human
priority: 1
title: Migrate every workflow domain to shared decisions and durable jobs
parent: OOMPAH-763
children:
- OOMPAH-781
- OOMPAH-782
- OOMPAH-788
- OOMPAH-791
- OOMPAH-793
- OOMPAH-804
- OOMPAH-812
- OOMPAH-813
- OOMPAH-819
blocked_by:
- OOMPAH-866
- OOMPAH-867
start_blocked_by: &id001
- OOMPAH-766
labels:
- rebase-requested
assignee: null
created_at: '2026-08-04T13:55:59.817364Z'
updated_at: '2026-08-06T23:25:16.629608Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.start_blocked_by: *id001
oompah.terminal_audit:
  queued_comment_posted: true
  applied_result_attempts:
    infrastructure-exhausted-audit-d5cd537191ed-1: '2026-08-06T22:16:10.385491+00:00'
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-768
    target_state: Done
    evidence_fingerprint: db765ca23847f4d117699f2b10474ae6eed749091fd9c26036c808c5a6ab0f59
    audit_ids:
    - audit-d5cd537191ed
    kind: result
    applied: true
    retired_at: '2026-08-06T22:16:10.385502+00:00'
  oompah.terminal_audit_result_intents:
  - project_id: proj-14849f1b
    task_id: OOMPAH-768
    audit_id: audit-d5cd537191ed
    attempt_id: infrastructure-exhausted-audit-d5cd537191ed-1
    target_state: Done
    evidence_fingerprint: db765ca23847f4d117699f2b10474ae6eed749091fd9c26036c808c5a6ab0f59
    status: Needs Human
    audit_ids:
    - audit-d5cd537191ed
    applied: true
    created_at: '2026-08-06T22:16:10.385519+00:00'
    applied_at: '2026-08-06T22:16:22.576275+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-d5cd537191ed
    project_id: proj-14849f1b
    task_id: OOMPAH-768
    target_state: Done
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: db765ca23847f4d117699f2b10474ae6eed749091fd9c26036c808c5a6ab0f59
    attempts:
    - version: 1
      attempt_id: attempt-ce475e01ee0b
      target_state: Done
      request_state: pending
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: db765ca23847f4d117699f2b10474ae6eed749091fd9c26036c808c5a6ab0f59
      created_at: '2026-08-06T22:15:30.198053+00:00'
      provider_id: prov-651d553c
      model: haiku
      started_at: '2026-08-06T22:15:30.198053+00:00'
      branch_key: OOMPAH-768
      failure_classification: infrastructure_error
      ended_at: '2026-08-06T22:15:48.143037+00:00'
      failure_reason: 'terminal audit evidence has no safely resolvable revision for
        OOMPAH-768 (tried: origin/OOMPAH-768)'
      next_retry_at: '2026-08-06T22:15:58.142998+00:00'
    - version: 1
      attempt_id: infrastructure-exhausted-audit-d5cd537191ed-1
      target_state: Done
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: db765ca23847f4d117699f2b10474ae6eed749091fd9c26036c808c5a6ab0f59
      verdict: needs_human
      failure_classification: infrastructure_error
      created_at: '2026-08-06T22:16:10.385378+00:00'
      completed_at: '2026-08-06T22:16:10.385378+00:00'
    requested_by:
      version: 1
      identity: orchestrator
    previous_state: Open
    created_at: '2026-08-06T22:15:02.037452+00:00'
    updated_at: '2026-08-06T22:16:10.385378+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-ce475e01ee0b
    target_state: Done
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: db765ca23847f4d117699f2b10474ae6eed749091fd9c26036c808c5a6ab0f59
    created_at: '2026-08-06T22:15:30.198053+00:00'
    provider_id: prov-651d553c
    model: haiku
    started_at: '2026-08-06T22:15:30.198053+00:00'
    branch_key: OOMPAH-768
    failure_classification: infrastructure_error
    ended_at: '2026-08-06T22:15:48.143037+00:00'
    failure_reason: 'terminal audit evidence has no safely resolvable revision for
      OOMPAH-768 (tried: origin/OOMPAH-768)'
    next_retry_at: '2026-08-06T22:15:58.142998+00:00'
---
## Summary

Cut over all task-progression domains to WorkflowFacts, WorkDecision, durable jobs, and TaskTransitionService in staged .env-controlled shadow/enforce modes. Domain scope: (1) integration queue eligibility, claiming, ancestry repair, UI waiting_on, retries, and fairness; (2) terminal-audit selection, launch, finalization, retry, and exhaustion; (3) In Review PR/CI/merge/missing-branch/capacity reconciliation; (4) implementation claims, direct-owner leases, worker exit, handoff, and retry; (5) epic/nested-epic rollup using first-class LandingFact(source,target,revision,proof) rather than status cycles. Remove duplicated predicates as each cutover completes. Required tests per domain include real native tracker and temporary Git/forge doubles plus restart and event-order races, with historical regressions preserved. Acceptance: each domain has exactly one eligibility/recovery decision, one durable owner, UI explanations match executor decisions, no parent-child proof cycles remain, and legacy domain writers/reconcilers are disabled after shadow parity.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-05 16:16
---
Direct-owner continuation: while OOMPAH-807's exact gate runs, the domain stack has been reconstructed in isolated scratch refs on candidate parent b1c089614. Duplicate patch-equivalent commits are omitted; OOMPAH-813 exact-project/replacement-run fences are composed with OOMPAH-815 accepted-branch and recovery-publication authority. A static review caught and repaired the composed project_id_val recovery-path NameError before testing. Authoritative epic-OOMPAH-768 will not be rewritten or pushed until OOMPAH-807 lands and combined tests pass.
---
author: oompah
created: 2026-08-05 16:32
---
Integration checkpoint advanced: OOMPAH-807 passed the combined-tree gate and integrated at b1c089614. The refreshed OOMPAH-768 composition is based on that exact root and contains only the accepted durable integration/implementation/review plus OOMPAH-813 authority fixes; two conflict-repair corrections normalize project identity and preserve OOMPAH-815 recovery scope. Static checks are clean. Focused composition tests are intentionally waiting for the single shared validation lane, currently occupied by OOMPAH-523's legitimate make test; no duplicate test load is being introduced.
---
author: oompah
created: 2026-08-06 00:15
---
Critical-path parent rebase completed while dispatch was paused. epic-OOMPAH-768 was rebased from ce2526a8b7e67426c3919cf890a9b3b1cdca20ad onto exact epic-OOMPAH-763 head 58ffd477b19f370c7ed53a191e1a05580b016c85 and pushed at 16d83ea3eaf409338cc22449e1447be088bea7df. Upstream-equivalent OOMPAH-805/819 patches dropped naturally; OOMPAH-813 conflicts were combined with the newer root recovery fences, including exact scoped project identity. Verification: 489 focused workflow, submission, review, integration, long-tick, and terminal-transition tests passed; pycompile, diff check, and make check-secrets passed. OOMPAH-807 code is now reachable on this parent.
---
author: oompah
created: 2026-08-06 22:15
---
Queued for terminal transition to Done. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-06 22:15
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/haiku)
---
author: oompah
created: 2026-08-06 22:15
---
Run #1 [attempt=1, profile=auditor, role=— -> unknown/unknown]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 3s
---
author: oompah
created: 2026-08-06 22:15
---
Auditor attempt ended: terminal audit evidence has no safely resolvable revision for OOMPAH-768 (tried: origin/OOMPAH-768). A different independent auditor will be tried on the next scheduler tick.
---
author: oompah
created: 2026-08-06 22:16
---
Needs Human — Done audit requires operator input.

Independent auditor launches exhausted their retry budget because the audit workspace or transport failed before review began. Restore the audit infrastructure, then have a project owner rearm this terminal audit; do not reopen implementation work.
---
author: oompah
created: 2026-08-06 23:25
---
Composition repair checkpoint: initial 3,280-test focused gate was 3,261 passed / 18 failed. First repair rerun reduced this to 6 passed / 12 failed; second-order fixes are now applied across stale duplicate projection, restart commit fencing, startup-queued event loss, alert-lock legacy restore, null-mode identity, reparent target authority, and audit recovery/coalescence. Current uncommitted scratch diff SHA256 0584257e585225eab04a16fca3b395a4243ce3eadb058e2c25952cc8925138b6; AST and diff checks pass. Exact rerun is paused while dedicated CI consumes the box outside the validation lease.
---
<!-- COMMENTS:END -->
