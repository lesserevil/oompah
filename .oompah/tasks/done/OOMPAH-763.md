---
id: OOMPAH-763
type: epic
status: Done
priority: 1
title: Build a unified, durable, live workflow engine
parent: null
children:
- OOMPAH-764
- OOMPAH-765
- OOMPAH-766
- OOMPAH-767
- OOMPAH-768
- OOMPAH-769
- OOMPAH-770
- OOMPAH-771
- OOMPAH-806
- OOMPAH-807
- OOMPAH-808
- OOMPAH-809
- OOMPAH-810
- OOMPAH-811
- OOMPAH-814
- OOMPAH-815
- OOMPAH-816
- OOMPAH-817
- OOMPAH-822
- OOMPAH-831
- OOMPAH-840
- OOMPAH-841
- OOMPAH-846
- OOMPAH-847
- OOMPAH-848
- OOMPAH-849
- OOMPAH-850
- OOMPAH-851
- OOMPAH-852
- OOMPAH-853
- OOMPAH-854
- OOMPAH-855
- OOMPAH-856
- OOMPAH-858
- OOMPAH-860
- OOMPAH-861
- OOMPAH-862
- OOMPAH-863
- OOMPAH-864
- OOMPAH-865
- OOMPAH-866
- OOMPAH-877
- OOMPAH-878
- OOMPAH-879
- OOMPAH-880
- OOMPAH-881
- OOMPAH-882
- OOMPAH-884
- OOMPAH-885
- OOMPAH-886
- OOMPAH-887
- OOMPAH-888
- OOMPAH-889
- OOMPAH-890
- OOMPAH-893
- OOMPAH-894
- OOMPAH-895
- OOMPAH-896
- OOMPAH-897
- OOMPAH-898
- OOMPAH-902
- OOMPAH-905
- OOMPAH-910
- OOMPAH-911
- OOMPAH-914
- OOMPAH-915
- OOMPAH-916
- OOMPAH-917
- OOMPAH-918
- OOMPAH-919
- OOMPAH-920
- OOMPAH-921
- OOMPAH-926
- OOMPAH-929
- OOMPAH-930
- OOMPAH-931
blocked_by: []
start_blocked_by: []
labels:
- human-only
- architecture
- rebase-requested
- epic:rebasing
assignee: null
created_at: '2026-08-04T13:54:42.220415Z'
updated_at: '2026-08-20T16:51:53.326296Z'
work_branch: epic-OOMPAH-763
target_branch: null
review_url: https://github.com/lesserevil/oompah/pull/749
review_number: '749'
review_head: null
merged_at: null
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-71aaab355b50
    project_id: proj-14849f1b
    task_id: OOMPAH-763
    target_state: Done
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 8f30f7e01d48c8701f6debe5b1115a245e38122796506c02741affcf247ca36d
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: Direct project-owner completion after all children/companions completed,
      exact-head full gate passed, and live all-enforce verification.
    created_at: '2026-08-09T05:17:28.523677+00:00'
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-763
    target_state: Done
    evidence_fingerprint: 8f30f7e01d48c8701f6debe5b1115a245e38122796506c02741affcf247ca36d
    audit_ids: []
    kind: override
    applied: true
    retired_at: '2026-08-09T05:17:37.959245+00:00'
  oompah.terminal_audit_result_intents: []
  oompah.terminal_provenance_suppression:
    version: 1
    suppressed: true
    authority_generation: 0
    reason: Historical audited Done record lacks safe exact current landing proof;
      retain immutable terminal provenance and retire recurring reassessment without
      creating new work.
    marked_at: '2026-08-10T01:20:02.063695+00:00'
    updated_at: '2026-08-10T01:20:02.063695+00:00'
    history:
    - kind: mark
      actor:
        version: 1
        identity: oompah-cli
        source: api
      reason: Historical audited Done record lacks safe exact current landing proof;
        retain immutable terminal provenance and retire recurring reassessment without
        creating new work.
      recorded_at: '2026-08-10T01:20:02.063695+00:00'
      authority_generation: 0
    actor:
      version: 1
      identity: oompah-cli
      source: api
  version: 1
  pending_chain: []
  attempt_history: []
oompah.review_url: https://github.com/lesserevil/oompah/pull/749
oompah.review_number: '749'
oompah.work_branch: epic-OOMPAH-763
---
## Summary

Problem: Oompah task progression is currently implemented by multiple local reconcilers, status writers, process-local authority maps, SQLite ledgers, Git/forge probes, watchdogs, and UI-specific eligibility summaries. Safety is generally fail-closed, but no single machine enforces transition legality or guarantees bounded progress, so operators repeatedly file bugs and manually recover stranded nonterminal work. Scope: implement the complete workflow-engine migration: formal lifecycle contract and liveness invariants; a single task-transition service and journal; unified versioned facts and pure WorkDecision evaluator; durable leased workflow jobs with restart-safe sagas; domain cutovers for integration, terminal audit, review, implementation ownership, and epic landing; a universal liveness controller and truthful alerts; model-based/fault-injection/100-task qualification; and final removal of legacy reconcilers plus orchestrator modularization. Preserve the native Markdown tracker as authoritative for user-visible task status, existing terminal safety guarantees, actor authorization, exact-head fencing, project scoping, and restart recovery throughout staged shadow/enforce rollout. Configuration flags must be OOMPAH_* values in .env/.env.example, not WORKFLOW.md. Required verification: focused tests for every child, complete make test at review-ready heads, state-machine safety and eventual-progress properties, kill/restart injection at every persistence boundary, historical incident replays for OOMPAH-562/731/732/739/748/749/751, and a multi-project 100-task soak. Acceptance: one transition writer, one shared decision for scheduler/UI/watchdogs, every nonterminal task has exactly one durable disposition and bounded reassessment, normal automatic recovery is not an operator warning, all historical incidents recover without manual mutation, legacy paths are deleted, and production workflow code is materially reduced after migration.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-04 14:07
---
Implementation ownership: this entire hierarchy is reserved for direct project-owner execution, not Oompah agent dispatch. Child tasks remain Backlog until their hard-start dependencies are complete; the active leaf will be owner-claimed in sequence so board state stays truthful. Foundation begins with OOMPAH-772. Accidental duplicate creations OOMPAH-799 through OOMPAH-802 were owner-archived; canonical children are OOMPAH-773, OOMPAH-774, OOMPAH-776, and OOMPAH-778.
---
author: oompah
created: 2026-08-04 21:31
---
Program graph repair: OOMPAH-775 now hard-starts after overlapping watchdog fix OOMPAH-806; OOMPAH-792 now hard-starts after production wiring OOMPAH-804; final retirement epic OOMPAH-771 waits for OOMPAH-769 and OOMPAH-806; qualification soak OOMPAH-797 waits for standalone gate-stability bug OOMPAH-805; obsolete historical OOMPAH-766 -> OOMPAH-769 start blocker removed. Independent audit found no cycles or missing refs after these changes.
---
author: oompah
created: 2026-08-05 06:05
---
Reconciled current main exact-head/cross-loop delivery fencing (OOMPAH-818/820) into the systemic workflow parent at ceafd8e14100964ee84821c4fbe75cf0ac772f43. The semantic merge keeps queue-generation/action-time CAS as the outer fence and routes the actual stalled-task reopen through OOMPAH-806 TaskTransitionService before posting the watchdog sentinel. Verification so far: 1,665 focused checks pass across watchdog/gate/transition authority, workflow shadow/durability, exact review-generation delivery, server/webhook/tracker behavior; terminal mutation scan 8/8 and secret scan pass. Branch is clean and pushed. A full exact-head gate will run after the currently active independent auditors release the four-worker resource lane.
---
author: oompah
created: 2026-08-05 14:48
---
Operator checkpoint boundary (2026-08-05): finish only the already-active OOMPAH-815 CI repair and the bounded in-flight batch OOMPAH-505/OOMPAH-523/OOMPAH-807/OOMPAH-821. Keep project dispatch paused; do not start the next systemic-program stage (including OOMPAH-781/OOMPAH-791/OOMPAH-804) in this work session. Once the active batch reaches safe terminal or clearly handed-off states, publish a concise clean-state handoff covering exact heads, tracker states, validation/alert health, remaining dependency order, and cleanup status, then stop.
---
author: oompah
created: 2026-08-05 14:53
---
Operator direction supersedes the prior checkpoint-only boundary: continue the systemic workflow program through completion, using child agents for safe independent work and allowing the Oompah server to implement dispatchable tasks where current capabilities permit. The project remains paused only while the bounded OOMPAH-505/523/807/821 validation batch and OOMPAH-815 repair drain; resume staged dispatch after that safe boundary.
---
author: oompah
created: 2026-08-07 14:11
---
Operator safety pause applied to the oompah project after duplicate helper OOMPAH-896 force-pushed an exact head before its full gate completed. Direct-owner work continues on O877/O846/O879; scheduler dispatch stays paused until the single-writer isolated server-owned publish path is safe or the canonical shared epic is green and explicitly reconciled.
---
author: oompah
created: 2026-08-07 21:48
---
Direct-owner composition checkpoint: current clean head 3a1928d6bb7d7b47a48a90a7d0e0a56e147bb96c includes current main and repairs the first full-gate failure (3 restart/cancellation regressions pass). The initial exact gate stopped at 1,457 passed on stale composed fixtures. Independent semantic review accepts workflow atomicity and the OOMPAH-843/OOMPAH-904 integration. Publication remains intentionally blocked while an isolated repair adds deterministic coverage for four review-lifecycle races: lock-order inversion, existing reservation duplicate-create suppression for epic/generic paths, close-between-create-and-publication fencing, and stale reviews API response preservation. A new exact full gate will run only after those blockers are composed.
---
author: oompah
created: 2026-08-07 22:13
---
Review-lifecycle blocker repair composed at ad15ee70bbb79ff3c5dc951603b3070ec3731998. It establishes canonical lifecycle-before-tracker lock order, treats acquired_new=false reservations as wait/adoption signals in epic and generic paths, fences created-review parent+child publication against close/merge under issue ownership, and preserves still-open sibling reviews in API/TTL state when a close overtakes a fetch. Validation: 7 deterministic race regressions and 725 broader affected review tests pass; terminal mutation scan 9/9, secret scan, and diff check pass. Independent review of this exact commit is active. Full exact gate remains deferred until direct-owner OOMPAH-887 and the reviewed OOMPAH-906 gate-harness repair are incorporated, avoiding redundant full-suite runs.
---
author: oompah
created: 2026-08-07 23:04
---
Direct composition checkpoint: independently accepted OOMPAH-887 exact stack through 5403e4b196cfae75cc7333d69b062d66c33fef8e is composed cleanly at systemic head a8b1d653ba8259dfc4e90603fdb075af85f9d77b. The landing path now freezes exact remote generations, fails closed for missing configured checkouts, fences both ref-movement mutation edges, and rechecks open-review publication after the final remote CAS. Brokered overlap suite tests/test_epic_strategy.py, tests/test_merged_labels_scope.py, and tests/test_standalone_ready_to_integrate.py: 355 passed. OOMPAH-906 remains isolated pending final hardening and independent exact-head review; no full gate or publication has started.
---
author: oompah
created: 2026-08-08 02:44
---
Exact candidate 200547fb75ced44e2c2005980a86e33c19501bf2 is under final validation. Focused quality-gate/parallel suite: 226 passed; terminal mutation scan passed; exact-head security/lifecycle review accepted after fixing the post-exchange canonical rollback race. Full make test is running under the validation lease.
---
author: oompah
created: 2026-08-08 03:54
---
Published exact systemic-workflow candidate e74449e4f9303f35c2cc2c1c5fc78ee979f4d268 to epic-OOMPAH-763 with a fresh force-with-lease. Exact validation: terminal mutation scan passed; secret scan passed; affected composition surface 392 passed; independent race/lifecycle/dashboard reviews accepted after two review-found consistency fixes; full make test passed 17,860 tests with 7 skipped and 1 expected failure in 22m06s. Remote main bb82f7f39510f0e02886307291812f2f8b3e6901 is an ancestor of the published head.
---
author: oompah
created: 2026-08-08 09:54
---
Consolidated systemic workflow head d9f9eff68 now includes OOMPAH-775/778, OOMPAH-792, OOMPAH-798, all prior implementation branches, and the previous full-gate repair. All superseded task worktrees/branches have been pruned; only the live checkout and consolidated review worktree remain. Static gates are green (20/20 authorized task-status writers, secret scan, compile/diff). The one exact full branch gate is running now; publication/deployment and terminal task updates follow a green gate.
---
author: oompah
created: 2026-08-08 11:03
---
Systemic workflow repair composition is committed at 900295e723bd5fc61e3aff23e979d6fee882ee79. Focused validation is green, including 334 repaired epic/delivery cases, 85 rollup/transition authority cases, and the final Git/tracker self-heal race. Static terminal-mutation and secret gates pass. Starting the exact full branch gate now; publish/deploy/terminalization follows only after that head is green.
---
author: oompah
created: 2026-08-08 12:56
---
Systemic composition advanced to b80e632fcb55658d37aa267bc7fa71ef0f044991 with OOMPAH-909 resource-leak/deadlock repair. All 27 non-terminal tasks remain directly owned through 2026-08-10 with no dependency cycle or expired claim. Exact full gate OOMPAH-763-full-b80e632 is now running; publish/deploy and dependency-safe closeout follow on green.
---
author: oompah
created: 2026-08-09 05:17
---
Systemic workflow program completed by direct project owner on rollout head dec2c35bb9e61bd286e271bcd03fcb0700f69a6e. Every child is terminal; all 14 parent-null systemic companion tasks were explicitly completed; focused and race suites passed; exact full gate passed (18,874 passed, 7 skipped, 2 xfailed); exact build is live with all implementation/review/integration/epic domains in enforce mode; terminal-audit backlog is zero; global actionable alerts are zero; raw exhausted history is retained while current exhausted=0; expired leases=0. Final liveness/canary convergence will be recorded after this terminal rollup publication.
---
author: oompah
created: 2026-08-09 05:17
---
Override by oompah-cli: terminal transition to Done applied by project owner.

Reason: Direct project-owner completion after all children/companions completed, exact-head full gate passed, and live all-enforce verification.
---
<!-- COMMENTS:END -->
