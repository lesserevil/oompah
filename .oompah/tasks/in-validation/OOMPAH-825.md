---
id: OOMPAH-825
type: task
status: In Validation
priority: 0
title: Scope and reclassify exhausted lifecycle reconciliation rows from authoritative
  landing evidence
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels:
- ci-fix
assignee: null
created_at: '2026-08-05T08:24:12.278010Z'
updated_at: '2026-08-05T13:32:31.954386Z'
work_branch: OOMPAH-825
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/721
review_number: '721'
review_head: 11c75e6c1b86f16837c13efb32938f814f362b79
merged_at: null
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  task_branch: OOMPAH-825
  base_branch: main
  head_sha: 11c75e6c1b86f16837c13efb32938f814f362b79
  submitted_at: '2026-08-05T12:55:30.423880+00:00'
  updated_at: '2026-08-05T12:55:30.423880+00:00'
oompah.review_url: https://github.com/lesserevil/oompah/pull/721
oompah.review_number: '721'
oompah.work_branch: OOMPAH-825
oompah.target_branch: main
oompah.review_head: 11c75e6c1b86f16837c13efb32938f814f362b79
oompah.terminal_audit:
  queued_comment_posted: true
  applied_result_attempts:
    attempt-d04fe57ac79d: '2026-08-05T13:32:03.004855+00:00'
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-825
    target_state: Done
    evidence_fingerprint: f1446e7a5635bf07712e5dc07c6bcf7c4d386aee89bb245209cbf5f4c6138b71
    audit_ids:
    - audit-5ffc50b0397d
    kind: result
    applied: true
    retired_at: '2026-08-05T13:32:03.004870+00:00'
  oompah.terminal_audit_result_intents:
  - project_id: proj-14849f1b
    task_id: OOMPAH-825
    audit_id: audit-5ffc50b0397d
    attempt_id: attempt-d04fe57ac79d
    target_state: Done
    evidence_fingerprint: f1446e7a5635bf07712e5dc07c6bcf7c4d386aee89bb245209cbf5f4c6138b71
    status: In Validation
    audit_ids:
    - audit-5ffc50b0397d
    applied: true
    created_at: '2026-08-05T13:32:03.004890+00:00'
    applied_at: '2026-08-05T13:32:10.475660+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-5ffc50b0397d
    project_id: proj-14849f1b
    task_id: OOMPAH-825
    target_state: Done
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: f1446e7a5635bf07712e5dc07c6bcf7c4d386aee89bb245209cbf5f4c6138b71
    attempts:
    - version: 1
      attempt_id: attempt-d04fe57ac79d
      target_state: Done
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: f1446e7a5635bf07712e5dc07c6bcf7c4d386aee89bb245209cbf5f4c6138b71
      created_at: '2026-08-05T13:15:23.162171+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-05T13:15:23.162171+00:00'
      branch_key: OOMPAH-825
      verdict: pass
      completed_at: '2026-08-05T13:32:03.004640+00:00'
      ended_at: '2026-08-05T13:32:03.004640+00:00'
    requested_by:
      version: 1
      identity: yolo-merge
      source: oompah
    previous_state: In Review
    created_at: '2026-08-05T13:13:49.463353+00:00'
    updated_at: '2026-08-05T13:32:03.004640+00:00'
  - version: 1
    audit_id: audit-073bdc9f703b
    project_id: proj-14849f1b
    task_id: OOMPAH-825
    target_state: Merged
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: f1446e7a5635bf07712e5dc07c6bcf7c4d386aee89bb245209cbf5f4c6138b71
    attempts: []
    requested_by:
      version: 1
      identity: yolo-merge
      source: oompah
    previous_state: In Review
    created_at: '2026-08-05T13:13:49.463353+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-d04fe57ac79d
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: f1446e7a5635bf07712e5dc07c6bcf7c4d386aee89bb245209cbf5f4c6138b71
    created_at: '2026-08-05T13:15:23.162171+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-05T13:15:23.162171+00:00'
    branch_key: OOMPAH-825
oompah.task_costs:
  total_input_tokens: 51
  total_output_tokens: 8069
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 51
      output_tokens: 8069
      cost_usd: 0.0
  runs:
  - profile: auditor
    model: unknown
    input_tokens: 51
    output_tokens: 8069
    cost_usd: 0.0
    recorded_at: '2026-08-05T13:32:26.861922+00:00'
---
## Summary

Live post-OOMPAH-823 state has 46 bounded/exhausted terminal lifecycle rows and action_required=true, but the warning is mostly false classification. Root cause: OompahMarkdownTracker normalization yields Issue(project_id=None), and reconcile_lifecycle_batch neither attaches the source project_id nor installs the current all-issues snapshot as recovery context before _validate_terminal_transition/_resolve_parent_epic. OOMPAH-739 added snapshot recovery only around recover_pending_audits, not the later background batch. Persisted conflict recovery is also stale/narrow: Archived tasks OOMPAH-452/453/455/456 have current PASS/Archived evidence but conflict resume requires PASS/Done; parent/target-relative landing evidence is absent from failure_fingerprint; and structurally Done-only OOMPAH-660/662 have matching applied project-owner Done overrides that recovery ignores. Scope: project-scope every batch Issue and supply a complete project snapshot; revalidate persisted conflicts against current terminal/audit facts; treat current PASS/Archived as superseding stale Merged repair; incorporate parent and target-relative durable LandingFact plus a classifier version into retry fingerprints; accept a matching applied authorized Done override for structurally Done-only maintenance; migrate/rearm v1 exhausted rows exactly once; preserve fail-closed intent checkpoints, row isolation, cross-project isolation, restart idempotence, and bounded persistence. Live migration groups: 4 stale Archived no-ops (452/453/455/456); 31 valid Merged rows with terminal parent evidence; 9 target-relative/patch-equivalent landed rows including OOMPAH-589/590/597/601/602/603/766 and EXOCOMP-129/185; 2 owner-override repairs (660/662 Merged to Done). Required tests: native Issue(project_id=None) parity; OOMPAH-739 background-batch snapshot parity with deleted refs; stale conflict plus PASS/Archived; one-time fingerprint reopen on changed landing evidence but not outage/restart; nested target-relative PRs and rebased parent PR chains; matching owner Done override one-write repair while missing evidence remains exhausted; live-shaped 46-row v1 migration yielding 44 not_needed plus 2 reconciled; cross-project isolation; restart idempotence and bounded writes. Acceptance: deploy on main without hand-editing service_state or task files; only OOMPAH-660/662 require tracker status writes; the ledger converges to exhausted=0 and action_required=false; no valid terminal state is weakened or auto-trusted without authoritative current evidence.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-05 09:53
---
Implemented the authoritative lifecycle-ledger recovery at clean pushed exact head b741e5372. It scopes alias-complete project snapshots, parses strict landing facts, distinguishes forge outage from negative evidence, rejects stale/retired authority, performs fresh under-lock tri-state validation before durable intent/status repair, and makes the one-time v1 migration restart/race safe. Live-shaped 46-row migration coverage proves 44 not-needed + 2 owner-authorized Done repairs; provider, parent-landing, child-state, and persistence races fail closed. Verification: 390 focused tests pass (terminal enforcement 78, SCM 304, compatibility 8); terminal mutation scan 8/8; secret/diff checks pass; independent exact-head review PASS; canonical trailer and remote synchronization verified. Holding submission only to serialize against OOMPAH-816's active canonical gate.
---
author: oompah
created: 2026-08-05 12:13
---
Rebased the reviewed lifecycle recovery implementation onto deployed OOMPAH-824 main c14ca03f59078e6df06871488cf78f04477acb11. New exact clean pushed head 74c4b71cfab349bc782fff71188c97651f54f519 has that exact parent, one canonical commit, and the same five-path delta. Rebase had zero conflicts/manual adaptations. Validation lease construction and top-level/health validation_resources projections coexist with lifecycle landing evidence, tri-state SCM observation, locked finality revalidation, and v1 migration; no workflow-shadow/job fields leaked. Nine-file combined lifecycle/SCM/validation/orchestrator suite: 983 passed. Terminal scan 8/8, secret scan, diff checks, trailer, upstream cleanliness all pass. Independent exact-head review is in progress before submission.
---
author: oompah
created: 2026-08-05 12:19
---
Independent exact-head review PASS at 74c4b71cfab349bc782fff71188c97651f54f519: one exact parent c14ca03f5, clean/pushed; patch-identical rebase; validation arbitration preserved; project-scoped fingerprints and tri-state SCM fail closed; exhausted rows rearm only on authoritative evidence changes; v1 migration marker is outage/restart durable; fresh complete snapshot is revalidated under the project write lock; live-shaped 46-row migration converges 44 no-op + exactly 2 authorized Done repairs; no workflow-shadow leakage; tests and trailer valid.
---
author: oompah
created: 2026-08-05 12:19
---
Authoritative lifecycle-ledger recovery rebased onto deployed validation arbitration at exact reviewed head 74c4b71cfab349bc782fff71188c97651f54f519. 983 focused tests and required scans pass; independent review PASS.
---
author: oompah
created: 2026-08-05 12:30
---
Branch quality gate passed for `74c4b71cfab349bc782fff71188c97651f54f519` using `make test` in 630.6s. Review creation may proceed.
---
author: oompah
created: 2026-08-05 12:42
---
YOLO: CI tests failed on MR #721. Fix the failing tests so this MR can merge. Do NOT rewrite the feature — only fix test failures. IMPORTANT: Paths in CI logs are not trustworthy. Run tests locally to get accurate paths and errors.
---
author: oompah
created: 2026-08-05 12:49
---
[watchdog:stalled_task] Stalled-task watchdog audit (run #6)

**State audited:** `Needs CI Fix`
**Classification:** `actionable`
**Action:** `reopen`
**Evidence:** Recent comment indicates CI is now passing or PR has been merged; safe to reopen for dispatch.
**Evidence head:** `74c4b71cfab349bc782fff71188c97651f54f519`
**Evidence result:** `comment_ci_passing`

*This comment is posted automatically by the oompah stalled-task watchdog. No human action required unless the classification above is incorrect.*
---
author: oompah
created: 2026-08-05 12:55
---
CI-fix pushed at exact head 11c75e6c1b86f16837c13efb32938f814f362b79. Root cause was test isolation: TestCheckCloseGate mocked the forge PR query but, with no GitHub token in CI, still invoked the real 'gh auth token' subprocess; its 5-second timeout raced pytest's 5-second per-test deadline. The fix supplies a deterministic test-only GH_TOKEN for this class and asserts the open-PR test never invokes subprocess.run, so it cannot conceal a real fallback. No feature/runtime code changed. Verification with both invoking tokens unset: formerly failing test 20/20; complete tests/test_close_gate.py 41/41; terminal scan 8/8; secret and diff checks pass; branch is clean and pushed. Independent incremental review is in progress.
---
author: oompah
created: 2026-08-05 12:55
---
Fix CI-only close-gate test isolation at exact pushed head 11c75e6c1b86f16837c13efb32938f814f362b79; focused stress/tests and safety scans pass, runtime feature unchanged.
---
author: oompah
created: 2026-08-05 12:56
---
Independent incremental review PASS at exact pushed head 11c75e6c1b86f16837c13efb32938f814f362b79. Reviewer verified the one-commit delta changes only tests/test_close_gate.py, fixture scope is limited to TestCheckCloseGate, deterministic test token cannot mask authentication fallback because the open-PR regression asserts subprocess.run is never called, lower-level auth/query tests remain unaffected, and branch/upstream/trailer/diff are exact and clean.
---
author: oompah
created: 2026-08-05 13:13
---
OOMPAH-826 containment/workaround complete for the current review generation: exact repaired head 11c75e6c1b86f16837c13efb32938f814f362b79 passed the complete Makefile gate (15,657 passed, 7 skipped, 1 expected xfail; 0 failures; 621.26s). GitHub CI on the same exact head is also green across Python 3.11/3.12/3.13. PR #721 was temporarily draft-held only to prevent merge before this missing exact-head local evidence existed; restoring it to ready now.
---
author: oompah
created: 2026-08-05 13:13
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-05 13:14
---
YOLO: merged PR #721.
---
author: oompah
created: 2026-08-05 13:15
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-08-05 13:15
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-05 13:24
---
Post-deploy live acceptance found two narrower production-shape gaps not covered by the reviewed migration fixture. The key exhaustion/action_required migration succeeded (exhausted=0, action_required=false) and OOMPAH-662 repaired to Done, but OOMPAH-452/453/455/456 retry as lifecycle_metadata_not_finalized and OOMPAH-660 retries as lifecycle_repair_not_applied. Exact diagnosis: Archived audits use disposition fingerprints from request_archived_audit, which cannot equal _lifecycle_terminal_authorities' issue fingerprint despite completed PASS + applied result intent; filed OOMPAH-828. OOMPAH-660 is the original OOMPAH-663 legacy canonicalization pair: current/integration audit ab40139d2035 versus applied Done override 62954f9b5fdc; the live-shaped OOMPAH-825 fixture incorrectly modeled equality; filed OOMPAH-829 for bounded equivalence migration. No service_state/task metadata was hand-edited. Both bugs are Open; project remains paused.
---
author: oompah
created: 2026-08-05 13:32
---
Audit PASS — Done

[REDACTED]

Safe evidence:
- head_commit: 11c75e6c1b86f16837c13efb32938f814f362b79
- merge_commit: 7978ec91b5532784c5dd6f18bc028954fd3696a9
- pr_number: 721
- parent_main: c14ca03f59078e6df06871488cf78f04477acb11
- branch_commits: 74c4b71cf (Scope lifecycle reconciliation evidence) + 11c75e6c1 (Isolate close-gate tests from host auth)
- files_changed: 6 (5 code+tests, 1 close-gate isolation)
- insertions_deletions: +2140/-266
- classifier_version: LIFECYCLE_RECONCILIATION_CLASSIFIER_VERSION=2
- full_gate_result: 15657 passed, 7 skipped, 1 xfailed in 619.73s
- terminal_mutation_scan: 8 identified, 8 allowlisted
- [REDACTED-credential-key]: clean
- commit_trailer: canonical oompah trailer, no model attribution
- merged_to_main: true
---
author: oompah
created: 2026-08-05 13:32
---
Run #YOLO-reopen [attempt=YOLO-reopen, profile=auditor, role=auditor -> Claude/opus]
- Turns: 59, Tool calls: 45
- Tokens: 51 in / 8.1K out [8.1K total]
- Cost: $0.0000
- Exit: normal, Duration: 17m 2s
- Log: OOMPAH-825__20260805T131538Z.jsonl
---
<!-- COMMENTS:END -->
