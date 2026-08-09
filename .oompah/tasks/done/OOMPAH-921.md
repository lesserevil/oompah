---
id: OOMPAH-921
type: task
status: Done
priority: null
title: Stop direct-owner terminal overrides from self-invalidating evidence
parent: OOMPAH-763
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-08T16:33:49.292212Z'
updated_at: '2026-08-09T05:15:15.139501Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-e2eca5ede2ee
    project_id: proj-14849f1b
    task_id: OOMPAH-921
    target_state: Done
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 4be6968dd35bf10100e79b8932709044b2561159cbfd2d3ffe3fd968a5707767
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: Direct project-owner completion after exact-head full-gate and live enforce
      verification.
    created_at: '2026-08-09T05:15:02.724855+00:00'
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-921
    target_state: Done
    evidence_fingerprint: 4be6968dd35bf10100e79b8932709044b2561159cbfd2d3ffe3fd968a5707767
    audit_ids: []
    kind: override
    applied: true
    retired_at: '2026-08-09T05:15:13.554794+00:00'
  oompah.terminal_audit_result_intents: []
  version: 1
  pending_chain: []
  attempt_history: []
---
## Summary

Live recurrence on deployed d796a4b after OOMPAH-889: OOMPAH-588 is direct-owner claimed and In Progress; its historical landed head a3a577a489650c602ec3c62bd242eb53de631af4 is contained in origin/main and parent OOMPAH-584 is Merged, yet two fresh authenticated project-owner Done overrides both return evidence_fingerprint_mismatch. The API appears to compute terminal evidence before an ownership/dispatch-fence or native rollup mutation changes the same task, so the request invalidates itself rather than rejecting genuinely stale caller evidence. Trace server terminal transition staging, owner-claim retirement/revocation, TerminalTransitionCoordinator fingerprint CAS, and native parent rollup. Preserve genuine stale/tampered evidence rejection and ordinary shared-epic Merged landing checks. Add production-shaped regression coverage for an In Progress direct-owner-claimed historically landed nested epic: a fresh Done override succeeds atomically and remains Done across refresh/reconciliation; a concurrent external metadata mutation still fails closed. Run focused tests, terminal mutation scan, secret scan, and exact full Makefile gate. Acceptance: OOMPAH-588 can be restored to stable Done through the authenticated API without hand-editing tracker/state files or recreating pruned branches.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-08 18:13
---
Implemented the complete direct-owner claim lifecycle fix at exact head 78b1c08cfc312e29203ce07f41f4c18cea72b89b. The change retires captured claims only after committed status transitions, persists and rolls back claim mutations, isolates exact-claim revocations in per-claim durable workflow lanes, preserves ABA replacements and valid Open preclaims, reconciles enqueue/refresh/exhaustion failures live, and recovers the postcommit crash boundary from immutable transition-request timestamps. Focused impacted suites are green (619-test broad slice plus targeted transition/owner suites), terminal mutation scan passed, and secret scan passed. Starting the exact full Makefile gate now.
---
author: oompah
created: 2026-08-08 18:39
---
Full branch gate at 78b1c08 exposed a compatibility regression: the new post-commit owner-claim capture assumed _owner_claims_lock on deliberately minimal Orchestrator.__new__ integrations, causing 33 cascading failures. Added a narrow absent-runtime guard and regression coverage in 3fd4a37c78c242111b5293cfd3f5601ab8740787. Exact failed nodes now pass 33/33; affected suites pass 710/710; scans pass. Mandatory full gate is rerunning at exact clean head 3fd4a37.
---
author: oompah
created: 2026-08-08 19:12
---
Live shadow validation at 3fd4a37 passed the 31-sample rollout canary but exposed a production wiring gap: owner_claim_retirements was registered only in legacy step5c, while runtime-bound production ticks schedule _run_non_lifecycle_housekeeping exclusively. Startup pruned 43 expired claims, but unexpired terminal claims therefore remained. Fixed the durable-runtime boundary with exact callback/architecture regressions in 6a995d1d99914964465c025b1054a763563eb973. Focused 430 tests and repository scans pass; mandatory exact-head full gate is running.
---
author: oompah
created: 2026-08-09 05:14
---
Direct project-owner completion verified on composed rollout head dec2c35bb9e61bd286e271bcd03fcb0700f69a6e: exact full gate passed (18,874 passed, 7 skipped, 2 xfailed), all four durable workflow domains are live in enforce mode, no actionable global alerts remain, and current durable exhaustion/expired leases are zero.
---
author: oompah
created: 2026-08-09 05:15
---
Override by oompah-cli: terminal transition to Done applied by project owner.

Reason: Direct project-owner completion after exact-head full-gate and live enforce verification.
---
<!-- COMMENTS:END -->
