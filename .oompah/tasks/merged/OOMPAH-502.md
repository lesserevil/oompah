---
id: OOMPAH-502
type: epic
status: Merged
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
updated_at: '2026-08-04T23:33:37.230356Z'
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
    infrastructure-exhausted-audit-930e23082310-3: '2026-08-04T23:13:05.036936+00:00'
    attempt-d400bbba9978: '2026-08-04T23:33:33.691747+00:00'
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
  - project_id: proj-14849f1b
    task_id: OOMPAH-502
    target_state: Done
    evidence_fingerprint: 368991f4b860d3150eec99c06ecc85cbe862b8f17388d2e10f0b3b668478f9c3
    audit_ids:
    - audit-930e23082310
    kind: result
    applied: true
    retired_at: '2026-08-04T23:13:05.036951+00:00'
  - project_id: proj-14849f1b
    task_id: OOMPAH-502
    target_state: Merged
    evidence_fingerprint: 368991f4b860d3150eec99c06ecc85cbe862b8f17388d2e10f0b3b668478f9c3
    audit_ids:
    - audit-3d99b9c238bc
    kind: result
    applied: true
    retired_at: '2026-08-04T23:33:33.691766+00:00'
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
  - project_id: proj-14849f1b
    task_id: OOMPAH-502
    audit_id: audit-930e23082310
    attempt_id: infrastructure-exhausted-audit-930e23082310-3
    target_state: Done
    evidence_fingerprint: 368991f4b860d3150eec99c06ecc85cbe862b8f17388d2e10f0b3b668478f9c3
    status: Needs Human
    audit_ids:
    - audit-930e23082310
    applied: true
    created_at: '2026-08-04T23:13:05.036971+00:00'
    applied_at: '2026-08-04T23:13:11.478492+00:00'
  - project_id: proj-14849f1b
    task_id: OOMPAH-502
    audit_id: audit-3d99b9c238bc
    attempt_id: attempt-d400bbba9978
    target_state: Merged
    evidence_fingerprint: 368991f4b860d3150eec99c06ecc85cbe862b8f17388d2e10f0b3b668478f9c3
    status: Merged
    audit_ids:
    - audit-3d99b9c238bc
    applied: false
    created_at: '2026-08-04T23:33:33.691791+00:00'
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
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 368991f4b860d3150eec99c06ecc85cbe862b8f17388d2e10f0b3b668478f9c3
    attempts:
    - version: 1
      attempt_id: attempt-d00cb31c0e1c
      target_state: Done
      request_state: pending
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 368991f4b860d3150eec99c06ecc85cbe862b8f17388d2e10f0b3b668478f9c3
      created_at: '2026-08-04T22:13:11.820939+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-04T22:13:11.820939+00:00'
      branch_key: epic-OOMPAH-502
      failure_classification: infrastructure_error
      ended_at: '2026-08-04T22:13:33.766342+00:00'
      failure_reason: 'terminal audit evidence has no safely resolvable revision for
        OOMPAH-502 (tried: origin/epic-OOMPAH-502, origin/OOMPAH-502)'
      next_retry_at: '2026-08-04T22:13:43.766308+00:00'
    - version: 1
      attempt_id: attempt-07688b36768e
      target_state: Done
      request_state: pending
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 368991f4b860d3150eec99c06ecc85cbe862b8f17388d2e10f0b3b668478f9c3
      created_at: '2026-08-04T22:43:08.829012+00:00'
      provider_id: prov-651d553c
      model: sonnet
      started_at: '2026-08-04T22:43:08.829012+00:00'
      branch_key: epic-OOMPAH-502
      candidate_rotation_count: 1
      failure_classification: infrastructure_error
      ended_at: '2026-08-04T22:43:25.604787+00:00'
      failure_reason: 'terminal audit evidence has no safely resolvable revision for
        OOMPAH-502 (tried: origin/epic-OOMPAH-502, origin/OOMPAH-502)'
      next_retry_at: '2026-08-04T22:43:45.604759+00:00'
    - version: 1
      attempt_id: attempt-b221b94d00a4
      target_state: Done
      request_state: pending
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 368991f4b860d3150eec99c06ecc85cbe862b8f17388d2e10f0b3b668478f9c3
      created_at: '2026-08-04T22:55:43.680250+00:00'
      provider_id: prov-651d553c
      model: haiku
      started_at: '2026-08-04T22:55:43.680250+00:00'
      branch_key: epic-OOMPAH-502
      candidate_rotation_count: 2
      failure_classification: infrastructure_error
      ended_at: '2026-08-04T22:55:59.362372+00:00'
      failure_reason: 'terminal audit evidence has no safely resolvable revision for
        OOMPAH-502 (tried: origin/epic-OOMPAH-502, origin/OOMPAH-502)'
      next_retry_at: '2026-08-04T22:56:39.362345+00:00'
    - version: 1
      attempt_id: infrastructure-exhausted-audit-930e23082310-3
      target_state: Done
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 368991f4b860d3150eec99c06ecc85cbe862b8f17388d2e10f0b3b668478f9c3
      verdict: needs_human
      failure_classification: infrastructure_error
      created_at: '2026-08-04T23:13:05.036841+00:00'
      completed_at: '2026-08-04T23:13:05.036841+00:00'
    requested_by:
      version: 1
      identity: epic-rollup-reconciliation
      source: oompah
    previous_state: In Validation
    created_at: '2026-08-04T18:30:13.803900+00:00'
    updated_at: '2026-08-04T23:13:05.036841+00:00'
  - version: 1
    audit_id: audit-3d99b9c238bc
    project_id: proj-14849f1b
    task_id: OOMPAH-502
    target_state: Merged
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 368991f4b860d3150eec99c06ecc85cbe862b8f17388d2e10f0b3b668478f9c3
    attempts:
    - version: 1
      attempt_id: attempt-d400bbba9978
      target_state: Merged
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 368991f4b860d3150eec99c06ecc85cbe862b8f17388d2e10f0b3b668478f9c3
      created_at: '2026-08-04T23:24:10.470037+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-04T23:24:10.470037+00:00'
      branch_key: epic-OOMPAH-502
      verdict: pass
      completed_at: '2026-08-04T23:33:33.691567+00:00'
      ended_at: '2026-08-04T23:33:33.691567+00:00'
    requested_by:
      version: 1
      identity: epic-rollup-reconciliation
      source: oompah
    previous_state: In Validation
    created_at: '2026-08-04T18:30:13.803900+00:00'
    updated_at: '2026-08-04T23:33:33.691567+00:00'
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
  - version: 1
    attempt_id: attempt-d00cb31c0e1c
    target_state: Done
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 368991f4b860d3150eec99c06ecc85cbe862b8f17388d2e10f0b3b668478f9c3
    created_at: '2026-08-04T22:13:11.820939+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-04T22:13:11.820939+00:00'
    branch_key: epic-OOMPAH-502
    failure_classification: infrastructure_error
    ended_at: '2026-08-04T22:13:33.766342+00:00'
    failure_reason: 'terminal audit evidence has no safely resolvable revision for
      OOMPAH-502 (tried: origin/epic-OOMPAH-502, origin/OOMPAH-502)'
    next_retry_at: '2026-08-04T22:13:43.766308+00:00'
  - version: 1
    attempt_id: attempt-07688b36768e
    target_state: Done
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 368991f4b860d3150eec99c06ecc85cbe862b8f17388d2e10f0b3b668478f9c3
    created_at: '2026-08-04T22:43:08.829012+00:00'
    provider_id: prov-651d553c
    model: sonnet
    started_at: '2026-08-04T22:43:08.829012+00:00'
    branch_key: epic-OOMPAH-502
    candidate_rotation_count: 1
    failure_classification: infrastructure_error
    ended_at: '2026-08-04T22:43:25.604787+00:00'
    failure_reason: 'terminal audit evidence has no safely resolvable revision for
      OOMPAH-502 (tried: origin/epic-OOMPAH-502, origin/OOMPAH-502)'
    next_retry_at: '2026-08-04T22:43:45.604759+00:00'
  - version: 1
    attempt_id: attempt-b221b94d00a4
    target_state: Done
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 368991f4b860d3150eec99c06ecc85cbe862b8f17388d2e10f0b3b668478f9c3
    created_at: '2026-08-04T22:55:43.680250+00:00'
    provider_id: prov-651d553c
    model: haiku
    started_at: '2026-08-04T22:55:43.680250+00:00'
    branch_key: epic-OOMPAH-502
    candidate_rotation_count: 2
    failure_classification: infrastructure_error
    ended_at: '2026-08-04T22:55:59.362372+00:00'
    failure_reason: 'terminal audit evidence has no safely resolvable revision for
      OOMPAH-502 (tried: origin/epic-OOMPAH-502, origin/OOMPAH-502)'
    next_retry_at: '2026-08-04T22:56:39.362345+00:00'
  - version: 1
    attempt_id: attempt-d400bbba9978
    target_state: Merged
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 368991f4b860d3150eec99c06ecc85cbe862b8f17388d2e10f0b3b668478f9c3
    created_at: '2026-08-04T23:24:10.470037+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-04T23:24:10.470037+00:00'
    branch_key: epic-OOMPAH-502
oompah.task_costs:
  total_input_tokens: 13
  total_output_tokens: 7374
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 13
      output_tokens: 7374
      cost_usd: 0.0
  runs:
  - profile: auditor
    model: unknown
    input_tokens: 13
    output_tokens: 7374
    cost_usd: 0.0
    recorded_at: '2026-08-04T22:09:42.990132+00:00'
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
author: oompah
created: 2026-08-04 22:09
---
Run #2 [attempt=2, profile=auditor, role=auditor -> Claude/sonnet]
- Turns: 33, Tool calls: 19
- Tokens: 13 in / 7.4K out [7.4K total]
- Cost: $0.0000
- Exit: normal, Duration: 21m 15s
- Log: OOMPAH-502__20260804T214848Z.jsonl
---
author: oompah
created: 2026-08-04 22:13
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-08-04 22:13
---
Run #1 [attempt=1, profile=auditor, role=— -> unknown/unknown]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 8s
---
author: oompah
created: 2026-08-04 22:13
---
Auditor attempt ended: terminal audit evidence has no safely resolvable revision for OOMPAH-502 (tried: origin/epic-OOMPAH-502, origin/OOMPAH-502). A different independent auditor will be tried on the next scheduler tick.
---
author: oompah
created: 2026-08-04 22:43
---
Auditor dispatched (attempt #2, candidate: prov-651d553c/sonnet)
---
author: oompah
created: 2026-08-04 22:43
---
Run #2 [attempt=2, profile=auditor, role=— -> unknown/unknown]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 5s
---
author: oompah
created: 2026-08-04 22:44
---
Auditor attempt ended: terminal audit evidence has no safely resolvable revision for OOMPAH-502 (tried: origin/epic-OOMPAH-502, origin/OOMPAH-502). A different independent auditor will be tried on the next scheduler tick.
---
author: oompah
created: 2026-08-04 22:55
---
Auditor dispatched (attempt #3, candidate: prov-651d553c/haiku)
---
author: oompah
created: 2026-08-04 22:56
---
Run #3 [attempt=3, profile=auditor, role=— -> unknown/unknown]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 10s
---
author: oompah
created: 2026-08-04 22:56
---
Auditor attempt ended: terminal audit evidence has no safely resolvable revision for OOMPAH-502 (tried: origin/epic-OOMPAH-502, origin/OOMPAH-502). A different independent auditor will be tried on the next scheduler tick.
---
author: oompah
created: 2026-08-04 23:13
---
Needs Human — Done audit requires operator input.

Independent auditor launches exhausted their retry budget because the audit workspace or transport failed before review began. Restore the audit infrastructure, then have a project owner rearm this terminal audit; do not reopen implementation work.
---
author: oompah
created: 2026-08-04 23:24
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-08-04 23:24
---
Focus: Completion Auditor
---
<!-- COMMENTS:END -->
