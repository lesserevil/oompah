---
id: OOMPAH-502
type: epic
status: In Validation
priority: 1
title: Reduce agent wall-clock latency without weakening delivery gates
parent: null
children:
- OOMPAH-503
- OOMPAH-504
- OOMPAH-505
- OOMPAH-506
- OOMPAH-507
- OOMPAH-508
- OOMPAH-509
- OOMPAH-510
- OOMPAH-517
- OOMPAH-518
- OOMPAH-519
- OOMPAH-520
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-28T15:03:45.331314Z'
updated_at: '2026-08-04T22:08:38.014291Z'
work_branch: epic-OOMPAH-502
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/564
review_number: '564'
merged_at: null
oompah.review_url: https://github.com/lesserevil/oompah/pull/564
oompah.review_number: '564'
oompah.work_branch: epic-OOMPAH-502
oompah.target_branch: main
oompah.terminal_audit:
  queued_comment_posted: true
  applied_result_attempts:
    attempt-69402e9e4957: '2026-08-04T22:08:31.729868+00:00'
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-502
    target_state: Archived
    evidence_fingerprint: 2afbf9fb2274a9812f0087a197c5ffea8d69ccf6f70b2c6cc7b20cf37b6f072d
    audit_ids:
    - audit-c0f003ce43f5
    kind: result
    applied: true
    retired_at: '2026-08-04T22:08:31.729880+00:00'
  oompah.terminal_audit_result_intents:
  - project_id: proj-14849f1b
    task_id: OOMPAH-502
    audit_id: audit-c0f003ce43f5
    attempt_id: attempt-69402e9e4957
    target_state: Archived
    evidence_fingerprint: 2afbf9fb2274a9812f0087a197c5ffea8d69ccf6f70b2c6cc7b20cf37b6f072d
    status: In Validation
    audit_ids:
    - audit-c0f003ce43f5
    applied: true
    created_at: '2026-08-04T22:08:31.729895+00:00'
    applied_at: '2026-08-04T22:08:36.791434+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-c0f003ce43f5
    project_id: proj-14849f1b
    task_id: OOMPAH-502
    target_state: Archived
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 2afbf9fb2274a9812f0087a197c5ffea8d69ccf6f70b2c6cc7b20cf37b6f072d
    attempts:
    - version: 1
      attempt_id: attempt-623e2bd6d3e7
      target_state: Archived
      request_state: pending
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 2afbf9fb2274a9812f0087a197c5ffea8d69ccf6f70b2c6cc7b20cf37b6f072d
      created_at: '2026-08-04T21:41:08.721917+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-04T21:41:08.721917+00:00'
      branch_key: epic-OOMPAH-502
      ended_at: '2026-08-04T21:48:19.323835+00:00'
      failure_reason: auditor session abandoned; no live worker owns the attempt
    - version: 1
      attempt_id: attempt-69402e9e4957
      target_state: Archived
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 2afbf9fb2274a9812f0087a197c5ffea8d69ccf6f70b2c6cc7b20cf37b6f072d
      created_at: '2026-08-04T21:48:21.618731+00:00'
      provider_id: prov-651d553c
      model: sonnet
      started_at: '2026-08-04T21:48:21.618731+00:00'
      branch_key: epic-OOMPAH-502
      candidate_rotation_count: 1
      verdict: pass
      completed_at: '2026-08-04T22:08:31.729679+00:00'
      ended_at: '2026-08-04T22:08:31.729679+00:00'
    requested_by:
      version: 1
      identity: oompah
      source: auto_archive
    previous_state: Merged
    created_at: '2026-08-04T18:27:48.153699+00:00'
    updated_at: '2026-08-04T22:08:31.729679+00:00'
  - version: 1
    audit_id: audit-930e23082310
    project_id: proj-14849f1b
    task_id: OOMPAH-502
    target_state: Done
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 368991f4b860d3150eec99c06ecc85cbe862b8f17388d2e10f0b3b668478f9c3
    attempts: []
    requested_by:
      version: 1
      identity: epic-rollup-reconciliation
      source: oompah
    previous_state: In Validation
    created_at: '2026-08-04T18:30:13.803900+00:00'
  - version: 1
    audit_id: audit-3d99b9c238bc
    project_id: proj-14849f1b
    task_id: OOMPAH-502
    target_state: Merged
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 368991f4b860d3150eec99c06ecc85cbe862b8f17388d2e10f0b3b668478f9c3
    attempts: []
    requested_by:
      version: 1
      identity: epic-rollup-reconciliation
      source: oompah
    previous_state: In Validation
    created_at: '2026-08-04T18:30:13.803900+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-623e2bd6d3e7
    target_state: Archived
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 2afbf9fb2274a9812f0087a197c5ffea8d69ccf6f70b2c6cc7b20cf37b6f072d
    created_at: '2026-08-04T21:41:08.721917+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-04T21:41:08.721917+00:00'
    branch_key: epic-OOMPAH-502
    ended_at: '2026-08-04T21:48:19.323835+00:00'
    failure_reason: auditor session abandoned; no live worker owns the attempt
  - version: 1
    attempt_id: attempt-69402e9e4957
    target_state: Archived
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 2afbf9fb2274a9812f0087a197c5ffea8d69ccf6f70b2c6cc7b20cf37b6f072d
    created_at: '2026-08-04T21:48:21.618731+00:00'
    provider_id: prov-651d553c
    model: sonnet
    started_at: '2026-08-04T21:48:21.618731+00:00'
    branch_key: epic-OOMPAH-502
    candidate_rotation_count: 1
---
## Summary

Triggered by: OOMPAH-501

Objective: reduce time spent in duplicate screening, prompt replay, repeated branch-wide tests, provider ambiguity, restart recovery, and stale storage while preserving one-writer-per-shared-epic and the rule that a PR/MR is created only when the entire branch is ready.

Scope: auto duplicate detection compares only nonterminal tasks; agent prompts retain the latest actionable human context and focus handoff without replaying unbounded history; Claude and Codex role candidates use explicit fast/standard/deep models; managed stale caches and worktrees receive a daily scan plus earlier pressure-triggered cleanup; deployment restarts drain active agents before replacing the process; intermediate focus handoffs use focused tests while one branch-ready gate runs the full suite; and pytest parallelism is enabled only after isolation is proven.

Constraints: keep all tunables in .env/.env.example, preserve provider round-robin and one-agent-per-epic safety, never delete active/unowned paths, never weaken terminal audit or merge readiness, and create no rollup PR/MR until every child is Done with landing evidence.

Acceptance criteria: each child has regression tests and operator documentation; the final clean branch passes make test and the secret scan; measured dispatch/task timing shows removed redundant work; cleanup is observable and fail-safe; role telemetry records the explicit provider/model; a single epic-owned review is created only after the full branch is ready.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-28 17:42
---
Branch quality gate passed for `aa93fa639e4def9e787740917ecff2fb3fe11ca1` using `make test` in 66.2s. Review creation may proceed.
---
author: oompah
created: 2026-07-28 17:55
---
Branch quality gate passed for `3a34d9a3f49df65d66bc6503d8bd3c5442132ac9` using `make test` in 65.1s. Review creation may proceed.
---
author: oompah
created: 2026-07-28 17:58
---
YOLO: merged PR #564.
---
author: oompah
created: 2026-08-04 18:27
---
Queued Archived audit: Aged Merged auto-archive (closed 7 days ago). An auditor will review before the task is retired.
---
author: oompah
created: 2026-08-04 21:48
---
Auditor dispatched (attempt #2, candidate: prov-651d553c/sonnet)
---
author: oompah
created: 2026-08-04 21:48
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-04 22:08
---
Audit PASS — Archived

[REDACTED]

Safe evidence:
- merge_commit: 0237f77305c83617bdca6d83f339fac65033a5a9
- merge_pr: #564
- merge_date: 2026-07-28
- quality_gate_commit_1: aa93fa639e4def9e787740917ecff2fb3fe11ca1
- quality_gate_result_1: make test passed in 66.2s
- quality_gate_commit_2: 3a34d9a3f49df65d66bc6503d8bd3c5442132ac9
- quality_gate_result_2: make test passed in 65.1s
- commits_in_main: confirmed via git branch --contains 3a34d9a3f49
- files_changed: 44
- insertions: 3810
- children_archived: OOMPAH-509, OOMPAH-517, OOMPAH-518, OOMPAH-519, OOMPAH-520
- children_in_validation: OOMPAH-503, OOMPAH-504, OOMPAH-505, OOMPAH-506, OOMPAH-507, OOMPAH-508, OOMPAH-510
- auto_archive_trigger: 7 days since merge (2026-07-28 to 2026-08-04)
---
<!-- COMMENTS:END -->
