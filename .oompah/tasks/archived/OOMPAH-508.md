---
id: OOMPAH-508
type: feature
status: Archived
priority: 1
title: Run focused checks at handoff and one full quality gate per ready branch
parent: OOMPAH-502
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-28T15:06:08.389229Z'
updated_at: '2026-08-05T00:52:30.012064Z'
work_branch: epic-OOMPAH-502
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 8ff14fbc-cb6e-4168-b77e-4f4e6eb88f8b
oompah.work_branch: epic-OOMPAH-502
oompah.task_costs:
  total_input_tokens: 18
  total_output_tokens: 273
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 18
      output_tokens: 273
      cost_usd: 0.0
  runs:
  - profile: standard
    model: unknown
    input_tokens: 18
    output_tokens: 273
    cost_usd: 0.0
    recorded_at: '2026-07-28T15:49:12.360160+00:00'
oompah.terminal_audit:
  queued_comment_posted: true
  applied_result_attempts:
    attempt-f4551bd2ba77: '2026-08-05T00:52:26.583577+00:00'
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-508
    target_state: Archived
    evidence_fingerprint: a999058c901f8de3c4b34c4b91426bb8593fd78fe0ca8d90a3f2bcf37cde75f1
    audit_ids:
    - audit-922ddb8e6bc3
    kind: result
    applied: true
    retired_at: '2026-08-05T00:52:26.583590+00:00'
  oompah.terminal_audit_result_intents:
  - project_id: proj-14849f1b
    task_id: OOMPAH-508
    audit_id: audit-922ddb8e6bc3
    attempt_id: attempt-f4551bd2ba77
    target_state: Archived
    evidence_fingerprint: a999058c901f8de3c4b34c4b91426bb8593fd78fe0ca8d90a3f2bcf37cde75f1
    status: Archived
    audit_ids:
    - audit-922ddb8e6bc3
    applied: false
    created_at: '2026-08-05T00:52:26.583605+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-922ddb8e6bc3
    project_id: proj-14849f1b
    task_id: OOMPAH-508
    target_state: Archived
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: a999058c901f8de3c4b34c4b91426bb8593fd78fe0ca8d90a3f2bcf37cde75f1
    attempts:
    - version: 1
      attempt_id: attempt-8d0aa00c32ca
      target_state: Archived
      request_state: pending
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: a999058c901f8de3c4b34c4b91426bb8593fd78fe0ca8d90a3f2bcf37cde75f1
      created_at: '2026-08-04T21:41:47.998086+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-04T21:41:47.998086+00:00'
      branch_key: epic-OOMPAH-502
      ended_at: '2026-08-04T21:49:15.465164+00:00'
      failure_reason: auditor session abandoned; no live worker owns the attempt
    - version: 1
      attempt_id: attempt-88f3174fd0c5
      target_state: Archived
      request_state: pending
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: a999058c901f8de3c4b34c4b91426bb8593fd78fe0ca8d90a3f2bcf37cde75f1
      created_at: '2026-08-04T22:44:33.849163+00:00'
      provider_id: prov-651d553c
      model: sonnet
      started_at: '2026-08-04T22:44:33.849163+00:00'
      branch_key: epic-OOMPAH-502
      candidate_rotation_count: 1
      ended_at: '2026-08-04T22:56:45.387988+00:00'
      failure_reason: auditor session abandoned; no live worker owns the attempt
    - version: 1
      attempt_id: attempt-f4551bd2ba77
      target_state: Archived
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: a999058c901f8de3c4b34c4b91426bb8593fd78fe0ca8d90a3f2bcf37cde75f1
      created_at: '2026-08-05T00:20:53.029391+00:00'
      provider_id: prov-651d553c
      model: haiku
      started_at: '2026-08-05T00:20:53.029391+00:00'
      branch_key: epic-OOMPAH-502
      candidate_rotation_count: 2
      verdict: pass
      completed_at: '2026-08-05T00:52:26.583424+00:00'
      ended_at: '2026-08-05T00:52:26.583424+00:00'
    requested_by:
      version: 1
      identity: oompah
      source: auto_archive
    previous_state: Merged
    created_at: '2026-08-04T18:28:42.830532+00:00'
    updated_at: '2026-08-05T00:52:26.583424+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-8d0aa00c32ca
    target_state: Archived
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: a999058c901f8de3c4b34c4b91426bb8593fd78fe0ca8d90a3f2bcf37cde75f1
    created_at: '2026-08-04T21:41:47.998086+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-04T21:41:47.998086+00:00'
    branch_key: epic-OOMPAH-502
    ended_at: '2026-08-04T21:49:15.465164+00:00'
    failure_reason: auditor session abandoned; no live worker owns the attempt
  - version: 1
    attempt_id: attempt-88f3174fd0c5
    target_state: Archived
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: a999058c901f8de3c4b34c4b91426bb8593fd78fe0ca8d90a3f2bcf37cde75f1
    created_at: '2026-08-04T22:44:33.849163+00:00'
    provider_id: prov-651d553c
    model: sonnet
    started_at: '2026-08-04T22:44:33.849163+00:00'
    branch_key: epic-OOMPAH-502
    candidate_rotation_count: 1
    ended_at: '2026-08-04T22:56:45.387988+00:00'
    failure_reason: auditor session abandoned; no live worker owns the attempt
  - version: 1
    attempt_id: attempt-f4551bd2ba77
    target_state: Archived
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: a999058c901f8de3c4b34c4b91426bb8593fd78fe0ca8d90a3f2bcf37cde75f1
    created_at: '2026-08-05T00:20:53.029391+00:00'
    provider_id: prov-651d553c
    model: haiku
    started_at: '2026-08-05T00:20:53.029391+00:00'
    branch_key: epic-OOMPAH-502
    candidate_rotation_count: 2
---
## Summary

Problem: every specialist focus currently runs the entire 12k-test suite because project instructions require make test before each commit. A multi-focus shared branch repeats the same four-minute gate several times, but Oompah can open the epic review without a single branch-head quality record after all children finish.

Implementation: introduce branch-head quality-gate evidence keyed by repository identity, target branch, work branch, head SHA, and configured command. Intermediate focus instructions require tests covering changed behavior plus relevant neighboring suites, not the full suite. When a standalone branch or complete epic branch becomes review-ready, run the configured full Makefile quality gate exactly once outside the scheduler event loop; cache PASS only for the exact head SHA and invalidate it on new commits/rebase/command changes. On failure, do not create a PR/MR; post concise failure evidence and route the task/epic to the existing CI-fix workflow. Keep the terminal auditor plan independent and preserve final review-readiness rechecks. Configuration belongs in .env/.env.example.

Tests: multiple focus handoffs on one unchanged branch cause zero full gates; readiness causes one; repeated ticks are idempotent; head changes invalidate; concurrent ticks claim once; nested epics and standalone tasks; pass/fail/timeout/restart recovery; scheduler HTTP responsiveness while tests run; GitHub/GitLab provider neutrality. Update AGENTS.md, generated integration instructions, WORKFLOW.md, and operator docs consistently.

Acceptance criteria: intermediate agents run focused checks; every review has one passing full gate for its exact head; failures cannot create reviews; no unchanged branch reruns the full suite.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-28 15:06
---
Claimed for manual implementation by the current Codex session. Held in Backlog while the shared epic branch is built so Oompah does not dispatch another agent; status will move to In Progress and Done as this session completes the slice.
---
author: oompah
created: 2026-07-28 15:36
---
Implementation started on epic-OOMPAH-502. Adding persistent branch-head quality-gate evidence at the review-creation boundary, changing worker guidance to focused checks, and covering idempotence, invalidation, failure, timeout, recovery, concurrency, and provider-neutral review flows.
---
author: oompah
created: 2026-07-28 15:46
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-28 15:46
---
Focus: CI Failure Fixer
---
author: oompah
created: 2026-07-28 15:47
---
Understanding: Dispatched as CI Failure Fixer on branch epic-OOMPAH-502. The branch has 6 commits ahead of main implementing the quality-gate feature (OOMPAH-505, drain/restart, stale storage, ACP model tiers, startup prompt compaction, duplicate detection fix). Will run make test to identify CI failures, then apply minimal fixes.
---
author: oompah
created: 2026-07-28 15:49
---
Run #1 [attempt=1, profile=standard, role=standard -> Claude/default]
- Turns: 0, Tool calls: 8
- Tokens: 18 in / 273 out [291 total]
- Cost: $0.0000
- Exit: terminated, Duration: 2m 37s
- Log: OOMPAH-508__20260728T154638Z.jsonl
---
author: oompah
created: 2026-07-28 15:49
---
Holding in Backlog only to prevent orphan recovery from assigning a duplicate agent while the claimed implementation is active in this session. Focused coverage currently passes (824 tests); full branch gate and final status follow after the complete epic head is ready.
---
author: oompah
created: 2026-07-28 15:56
---
Implemented and pushed as 79f023202. Review creation for standalone tasks and complete epic branches now requires a persistent, single-flight full quality outcome keyed by repo/target/work branch/head SHA/command. Passing or failing unchanged heads are reused across concurrent ticks and restarts; new commits/rebases/config invalidate naturally. Failures route to Needs CI Fix with actionable output, and configured standalone gates run in the off-loop deferred-review lane. Worker/bootstrap guidance now requests focused behavior and neighbor tests. Coverage: 824 focused tests, then full make test (12,673 passed, 7 skipped), plus secret scan.
---
author: oompah
created: 2026-07-28 15:56
---
Exact-head full branch gate shipped with persistent single-flight evidence and focused worker checks.
---
author: oompah
created: 2026-08-04 18:28
---
Queued Archived audit: Aged Merged auto-archive (closed 7 days ago). An auditor will review before the task is retired.
---
author: oompah
created: 2026-08-05 00:21
---
Auditor dispatched (attempt #3, candidate: prov-651d553c/haiku)
---
author: oompah
created: 2026-08-05 00:21
---
Focus: Completion Auditor
---
<!-- COMMENTS:END -->
