---
id: OOMPAH-1001
type: bug
status: In Validation
priority: 1
title: Import trusted protected recovery-PR exact-head gates before terminal-audit
  dispatch
parent: null
children: []
blocked_by: []
start_blocked_by: &id001 []
labels: []
assignee: null
created_at: '2026-08-10T17:36:35.101810Z'
updated_at: '2026-08-10T19:51:49.943861Z'
work_branch: OOMPAH-1001
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.create_once:
  version: 1
  project_id: proj-14849f1b
  operation_kind: api_task_create
  creation_marker: o999-protected-recovery-pr-gate-import-v1
  request_fingerprint: ea272e3261553b0afbf6159e7cf5993e453800bc18863cb9a23339b827c4abb9
oompah.start_blocked_by: *id001
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: standalone
  task_branch: OOMPAH-1001
  head_sha: 1e8edb7bc7f8579e17d02610fd751ff9b5f812c2
  submitted_at: '2026-08-10T19:22:54.922877+00:00'
  updated_at: '2026-08-10T19:22:54.922877+00:00'
oompah.work_branch: OOMPAH-1001
oompah.terminal_audit:
  queued_comment_posted: true
  oompah.terminal_audit_tracker_projections:
  - version: 1
    audit_id: audit-d765f0c89989
    project_id: proj-14849f1b
    task_id: OOMPAH-1001
    digest: b11b65e16b38d16d503cfa549a9010ea24103e06e70a9b87f7e31d37491c6bfa
  - version: 1
    audit_id: audit-32e7c981afdc
    project_id: proj-14849f1b
    task_id: OOMPAH-1001
    digest: b11b65e16b38d16d503cfa549a9010ea24103e06e70a9b87f7e31d37491c6bfa
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-d765f0c89989
    project_id: proj-14849f1b
    task_id: OOMPAH-1001
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: b11b65e16b38d16d503cfa549a9010ea24103e06e70a9b87f7e31d37491c6bfa
    attempts:
    - version: 1
      attempt_id: attempt-b2f7a603c2ac
      target_state: Done
      request_state: in_progress
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: b11b65e16b38d16d503cfa549a9010ea24103e06e70a9b87f7e31d37491c6bfa
      created_at: '2026-08-10T19:51:41.662172+00:00'
      provider_id: prov-651d553c
      model: haiku
      started_at: '2026-08-10T19:51:41.662172+00:00'
      branch_key: OOMPAH-1001
      selected_ref: 1e8edb7bc7f8579e17d02610fd751ff9b5f812c2
      selected_sha: 1e8edb7bc7f8579e17d02610fd751ff9b5f812c2
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: Ready to Integrate
    created_at: '2026-08-10T19:51:00.663431+00:00'
    selected_ref: 1e8edb7bc7f8579e17d02610fd751ff9b5f812c2
    selected_sha: 1e8edb7bc7f8579e17d02610fd751ff9b5f812c2
    updated_at: '2026-08-10T19:51:41.662172+00:00'
  - version: 1
    audit_id: audit-32e7c981afdc
    project_id: proj-14849f1b
    task_id: OOMPAH-1001
    target_state: Merged
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: b11b65e16b38d16d503cfa549a9010ea24103e06e70a9b87f7e31d37491c6bfa
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: Ready to Integrate
    created_at: '2026-08-10T19:51:00.663431+00:00'
    selected_ref: 1e8edb7bc7f8579e17d02610fd751ff9b5f812c2
    selected_sha: 1e8edb7bc7f8579e17d02610fd751ff9b5f812c2
  attempt_history:
  - version: 1
    attempt_id: attempt-b2f7a603c2ac
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: b11b65e16b38d16d503cfa549a9010ea24103e06e70a9b87f7e31d37491c6bfa
    created_at: '2026-08-10T19:51:41.662172+00:00'
    provider_id: prov-651d553c
    model: haiku
    started_at: '2026-08-10T19:51:41.662172+00:00'
    branch_key: OOMPAH-1001
    selected_ref: 1e8edb7bc7f8579e17d02610fd751ff9b5f812c2
    selected_sha: 1e8edb7bc7f8579e17d02610fd751ff9b5f812c2
---
## Summary

Triggered by: OOMPAH-999

Triggered by OOMPAH-999. Problem: recovery head 6418a935de7b4aab93a24af4756a54b344463513 passed the complete local Makefile gate and protected PR #799 Python 3.11/3.12/3.13 checks, but no exact evidence entered quality_gates.json, so terminal audit redundantly launched make test until a supported owner override. Scope: in oompah/scm.py expose rich exact-SHA check/workflow evidence including check/run IDs, head SHA, workflow identity, run attempt, status, and conclusion; in oompah/quality_gate.py add a fail-closed imported/attested PASS API with durable provenance while retaining the repo/target/source/exact-head/configured-command key; in oompah/orchestrator.py import evidence during merged recovery-review reconciliation before auditor dispatch only when current audit binding, PR source/head/base, target containment, and configured command all agree. Document operator trust configuration in docs/operator-runbook.md if needed. Never translate aggregate CIStatus passed directly: require exact PR head, merged target, every configured required context/matrix job successful, and trusted workflow/command attestation proving the protected workflow ran test_command_full. Reject empty, neutral, skipped, cancelled, altered, wrong-SHA/base/source, stale attempt/fingerprint, degraded API, replayed, or advanced-head evidence. Tests: PR #799-shaped evidence imports one durable PASS and the first auditor reuses it without launching a full command, including after restart; every trust mismatch runs the ordinary full gate; concurrent import/dispatch is idempotent; serialized provenance cannot be reused across repo, branch, head, or command. Acceptance: authoritative protected recovery-PR gates are reused exactly once without weakening fail-closed terminal audit behavior, and focused plus complete protected gates pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-10 18:09
---
Trust-boundary refinement from live PR #799 evidence: do not treat GitHub run.head_sha as proof that test_command_full executed at the PR head because current pull_request CI uses bare actions/checkout@v4 and normally checks out a synthetic merge revision. The importer must require an operator-pinned workflow identity/blob plus exact required jobs/app/attempt and either (a) an explicit workflow checkout of github.event.pull_request.head.sha whose pinned definition attests the command, or (b) for historical recovery PRs, verified merge parents and exact PR-head/merge tree equality. PR #799 satisfies the historical tree-equality rule: head 6418a935..., merge 0ce6c313..., workflow blob 492e9289..., and all three attempt-2 jobs completed successfully. Add the explicit PR-head checkout to .github/workflows/ci.yml for future evidence, pin its new trusted blob through .env-only configuration, keep default import disabled, never use aggregate CIStatus.PASSED, and fail closed on any API/pagination/config/tree/workflow/job mismatch.
---
author: oompah
created: 2026-08-10 19:22
---
Implementation is complete and pushed at exact head 1e8edb7bc. The launch-only bridge imports strict protected-workflow evidence under the live audit attempt, current environment trust fingerprint, exact PR/source/head/target identity, canonical project URL, fresh target containment, and a post-I/O task/project/config recheck; command-time reuse is local-only and config revocation is immediate. The actual PR #799 probe returned COMPLETE and passed the independent binder for run 31411330877 attempt 2. Validation: 81 focused terminal/protected tests and 771 affected config/SCM/quality/workflow tests passed; terminal mutation scan and paranoid secret scan passed. Independent adversarial review reports no remaining blocker.
---
author: oompah
created: 2026-08-10 19:23
---
Implemented and pushed exact protected recovery-PR gate import at 1e8edb7bc. Real PR #799 evidence binds successfully; 771 affected tests, terminal mutation scan, secret scan, and independent adversarial review are green.
---
author: oompah
created: 2026-08-10 19:36
---
Live diagnosis: OOMPAH-1000 is authoritatively Merged on the current state branch, but universal workflow facts projected its state-less native Markdown BlockerRef as Backlog. Filed OOMPAH-1004 for generation-consistent dependency status resolution. Removing this now-obsolete hard-start edge as the scoped in-flight workaround; implementation ancestry and protected integration gates remain mandatory.
---
author: oompah
created: 2026-08-10 19:41
---
Protected PR #801 is open from exact submitted head 1e8edb7bc7f8579e17d02610fd751ff9b5f812c2: https://github.com/lesserevil/oompah/pull/801. CI is now running in parallel with OOMPAH-1003/OOMPAH-1004 implementation; Oompah may reconcile this existing review.
---
author: oompah
created: 2026-08-10 19:50
---
Branch quality gate passed for `1e8edb7bc7f8579e17d02610fd751ff9b5f812c2` using `make test` in 181.4s. Review creation may proceed.
---
author: oompah
created: 2026-08-10 19:51
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-10 19:51
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/haiku)
---
author: oompah
created: 2026-08-10 19:51
---
Focus: Completion Auditor
---
<!-- COMMENTS:END -->
