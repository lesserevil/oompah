---
id: OOMPAH-457
type: epic
status: In Validation
priority: 0
title: Build the terminal-audit state model and transition coordinator
parent: null
children:
- OOMPAH-461
- OOMPAH-462
- OOMPAH-463
- OOMPAH-464
- OOMPAH-465
- OOMPAH-466
- OOMPAH-467
blocked_by: []
labels:
- ci-fix
assignee: null
created_at: '2026-07-28T13:03:45.243838Z'
updated_at: '2026-08-04T22:20:25.829455Z'
work_branch: epic-OOMPAH-457
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/565
review_number: '565'
merged_at: null
oompah.review_url: https://github.com/lesserevil/oompah/pull/565
oompah.review_number: '565'
oompah.work_branch: epic-OOMPAH-457
oompah.target_branch: main
oompah.agent_run_id: d58c06c0-a435-492e-aa36-13e0fccab150
oompah.terminal_audit:
  queued_comment_posted: true
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-e210194f8664
    project_id: proj-14849f1b
    task_id: OOMPAH-457
    target_state: Archived
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 14b6de4be4102cebf7887c3fd29606f7e26cb0e48a2766af964ff91d7bb88078
    attempts:
    - version: 1
      attempt_id: attempt-66403b6f73b4
      target_state: Archived
      request_state: pending
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 14b6de4be4102cebf7887c3fd29606f7e26cb0e48a2766af964ff91d7bb88078
      created_at: '2026-08-04T21:42:29.461331+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-04T21:42:29.461331+00:00'
      branch_key: epic-OOMPAH-457
      ended_at: '2026-08-04T21:51:25.377377+00:00'
      failure_reason: auditor session abandoned; no live worker owns the attempt
    - version: 1
      attempt_id: attempt-047bed843267
      target_state: Archived
      request_state: in_progress
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 14b6de4be4102cebf7887c3fd29606f7e26cb0e48a2766af964ff91d7bb88078
      created_at: '2026-08-04T22:19:55.657378+00:00'
      provider_id: prov-651d553c
      model: sonnet
      started_at: '2026-08-04T22:19:55.657378+00:00'
      branch_key: epic-OOMPAH-457
      candidate_rotation_count: 1
    requested_by:
      version: 1
      identity: oompah
      source: auto_archive
    previous_state: Merged
    created_at: '2026-08-04T21:33:09.639801+00:00'
    updated_at: '2026-08-04T22:19:55.657378+00:00'
  - version: 1
    audit_id: audit-70ee8bf012fa
    project_id: proj-14849f1b
    task_id: OOMPAH-457
    target_state: Done
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 200a2b6ad737cbd463d050509ef27124c7a977a63f51277dc16974b404699b9c
    attempts: []
    requested_by:
      version: 1
      identity: epic-rollup-reconciliation
      source: oompah
    previous_state: In Validation
    created_at: '2026-08-04T21:35:36.253495+00:00'
  - version: 1
    audit_id: audit-04b103e6d430
    project_id: proj-14849f1b
    task_id: OOMPAH-457
    target_state: Merged
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 200a2b6ad737cbd463d050509ef27124c7a977a63f51277dc16974b404699b9c
    attempts: []
    requested_by:
      version: 1
      identity: epic-rollup-reconciliation
      source: oompah
    previous_state: In Validation
    created_at: '2026-08-04T21:35:36.253495+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-66403b6f73b4
    target_state: Archived
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 14b6de4be4102cebf7887c3fd29606f7e26cb0e48a2766af964ff91d7bb88078
    created_at: '2026-08-04T21:42:29.461331+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-04T21:42:29.461331+00:00'
    branch_key: epic-OOMPAH-457
    ended_at: '2026-08-04T21:51:25.377377+00:00'
    failure_reason: auditor session abandoned; no live worker owns the attempt
  - version: 1
    attempt_id: attempt-047bed843267
    target_state: Archived
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 14b6de4be4102cebf7887c3fd29606f7e26cb0e48a2766af964ff91d7bb88078
    created_at: '2026-08-04T22:19:55.657378+00:00'
    provider_id: prov-651d553c
    model: sonnet
    started_at: '2026-08-04T22:19:55.657378+00:00'
    branch_key: epic-OOMPAH-457
    candidate_rotation_count: 1
---
## Summary

Goal

Create the durable state-machine foundation that places an independent validation step between active work and every terminal status. This epic does not dispatch auditor agents or migrate every caller; it defines the canonical In Validation status, audit records, evidence identity, persistence, transition chaining, failure routing, restart behavior, and explicit owner override contract that later epics consume.

Required behavior

- Existing terminal records at upgrade are grandfathered, but every new Done, Merged, or Archived request is represented by a durable audit request.
- A direct Merged request without a current Done audit for the same evidence revision creates an ordered Done-then-Merged chain.
- Duplicate requests are idempotent and stale verdicts cannot change state.
- Failures route to Open, Needs CI Fix, Needs Rebase, In Review, Needs Human, or the pre-archive state using a centralized classification table.
- Owner bypasses require explicit authority and a non-empty reason.
- No verifier error or retry ceiling may fail open into a terminal state.

Constraints

Use tracker-owned oompah metadata for durable audit authority and normal comments for human-readable evidence. Preserve native Markdown state-branch behavior and GitHub/GitLab adapter compatibility. Configuration belongs in .env, not WORKFLOW.md. All code changes require tests.

Acceptance criteria

The coordinator can stage, persist, recover, pass, fail, supersede, and override target-specific terminal audits without starting a model. Its public types and methods are documented and stable enough for the auditor and integration epics. Focused tests and make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-28 18:10
---
Started from origin/main at 0237f77305c83617bdca6d83f339fac65033a5a9. All child tasks are Open; OOMPAH-461 is the first dispatched child on shared branch epic-OOMPAH-457.
---
author: oompah
created: 2026-07-28 20:36
---
Branch quality gate passed for `a5699d6fce9e358c556763e304f47deeca17d958` using `make test` in 72.3s. Review creation may proceed.
---
author: oompah
created: 2026-07-28 20:45
---
YOLO: CI tests failed on MR #565. Fix the failing tests so this MR can merge. Do NOT rewrite the feature — only fix test failures. IMPORTANT: Paths in CI logs are not trustworthy. Run tests locally to get accurate paths and errors.
---
author: oompah
created: 2026-07-28 21:04
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-07-28 21:05
---
Focus: CI Failure Fixer
---
author: oompah
created: 2026-07-28 21:05
---
Understanding: I will inspect the failed GitHub Actions jobs for MR #565 on epic-OOMPAH-457, reproduce the reported errors locally, apply only the minimal covered CI fix, run focused tests, push the same branch, and verify checks restart.
---
author: oompah
created: 2026-07-28 21:06
---
Discovery: GitHub Actions run 30397110118 failed only on Python 3.11 in tests/test_state_branch_e2e.py::TestCheckpointCoalescingE2E::test_multiple_mutations_coalesced_into_single_commit: the manual flush saw 1 mutation instead of 5. The test configures a real 100 ms debounce timer while performing five git-backed creates, so on the slower CI worker the timer flushed the first four before the explicit assertion. The focused test passes locally on Python 3.12, confirming timing sensitivity; Python 3.13 CI passed and 3.12 was canceled. The production queue behavior is correct; the test needs to prevent auto-flush while testing explicit coalesced flush.
---
author: oompah
created: 2026-07-28 21:07
---
Implementation: Changed only the failing E2E test configuration. Its checkpoint debounce/max-delay are now 30s/60s, matching the existing pending-counter test pattern, so the explicit flush deterministically owns all five mutations even on a slow CI runner. No production code or workflow files were changed.
---
author: oompah
created: 2026-07-28 21:07
---
Verification: Focused checkpoint coverage passes locally on Python 3.12.12: TestCheckpointCoalescingE2E alone 3/3, then tests/test_checkpoint_coalescing.py plus tests/test_state_branch_e2e.py 105/105 in 11.08s. git diff --check also passes. Per CI-fixer instructions I did not rerun the already-passed full make test gate.
---
author: oompah
created: 2026-07-28 21:08
---
Completion: Pushed minimal CI repair commit 63c36e380aaee3ccf1bc09b72e5bf17bc71e8b16 to the existing epic-OOMPAH-457 branch for PR #565. The branch is clean and up to date with origin. GitHub Actions rerun 30399368777 is confirmed on the new head, with Python 3.11/3.12/3.13 jobs pending. Focused local suites passed 105/105.
---
author: oompah
created: 2026-07-28 21:08
---
Run #YOLO-reopen [attempt=YOLO-reopen, profile=deep, role=deep -> Codex/gpt-5.6-sol]
- Turns: 0, Tool calls: 37
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 3m 38s
- Log: OOMPAH-457__20260728T210500Z.jsonl
---
author: oompah
created: 2026-07-28 21:08
---
Stabilized the checkpoint coalescing E2E test by preventing its real debounce timer from racing the explicit flush on slow CI runners. Pushed commit 63c36e380 to PR #565; focused checkpoint/state-branch suites pass 105/105 and replacement CI run 30399368777 is queued for all supported Python versions.
---
author: oompah
created: 2026-07-28 21:11
---
Branch quality gate passed for `63c36e380aaee3ccf1bc09b72e5bf17bc71e8b16` using `make test` in 67.2s. Review creation may proceed.
---
author: oompah
created: 2026-07-28 21:15
---
YOLO: merged PR #565.
---
author: oompah
created: 2026-08-04 21:33
---
Queued Archived audit: Aged Merged auto-archive (closed 7 days ago). An auditor will review before the task is retired.
---
author: oompah
created: 2026-08-04 22:20
---
Auditor dispatched (attempt #2, candidate: prov-651d553c/sonnet)
---
author: oompah
created: 2026-08-04 22:20
---
Focus: Completion Auditor
---
<!-- COMMENTS:END -->
