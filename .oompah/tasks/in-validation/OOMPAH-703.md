---
id: OOMPAH-703
type: bug
status: In Validation
priority: 1
title: Make backlog refresh invalidation tests wait for completion deterministically
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-02T20:59:10.197769Z'
updated_at: '2026-08-02T22:36:16.459515Z'
work_branch: OOMPAH-703
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/663
review_number: '663'
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 7379f73edf0db9cd454f28a67b73307d7d36633b8a5f53b98c3407ab3f9291cf
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-02T21:53:57.558386+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector  \nDuplicate preflight verdict: no_duplicate\
    \  \nMatches: none  \n\nEvidence: No active peer task covers deterministic synchronization\
    \ for `BacklogRefreshManager` invalidation tests. Closest reviewed tasks, OOMPAH-158\
    \ and OOMPAH-175, are terminal and address unrelated cache behavior."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 1
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: null
oompah.task_costs:
  total_input_tokens: 50575
  total_output_tokens: 11057
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 50524
      output_tokens: 1662
      cost_usd: 0.0
    unknown:
      input_tokens: 51
      output_tokens: 9395
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 1336
    cost_usd: 0.0
    recorded_at: '2026-08-02T21:52:08.225263+00:00'
  - profile: default
    model: haiku
    input_tokens: 50514
    output_tokens: 326
    cost_usd: 0.0
    recorded_at: '2026-08-02T21:53:57.556844+00:00'
  - profile: auditor
    model: unknown
    input_tokens: 51
    output_tokens: 9395
    cost_usd: 0.0
    recorded_at: '2026-08-02T22:36:00.887406+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-703__20260802T215147Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-703
    source_sha: 366129d0a5046c5ed7caed4acf26cd8cd2a3fbdd
    completed_at: '2026-08-02T21:52:11.278492+00:00'
  - run_id: OOMPAH-703__20260802T215345Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-703
    source_sha: 366129d0a5046c5ed7caed4acf26cd8cd2a3fbdd
    completed_at: '2026-08-02T21:53:57.596053+00:00'
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  task_branch: OOMPAH-703
  head_sha: 26b3f2ea9a99038870bc1f5d46a29157ee9be512
  submitted_at: '2026-08-02T22:12:54.173205+00:00'
  updated_at: '2026-08-02T22:12:54.173205+00:00'
oompah.review_url: https://github.com/lesserevil/oompah/pull/663
oompah.review_number: '663'
oompah.work_branch: OOMPAH-703
oompah.target_branch: main
oompah.terminal_audit:
  queued_comment_posted: true
  applied_result_attempts:
    attempt-9ad9b59746a7: '2026-08-02T22:35:46.448566+00:00'
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-703
    target_state: Done
    evidence_fingerprint: f55c8ab7eae1ae9acff2b0164f275f9aebe7fafb215c1480a6604e9e4237964c
    audit_ids:
    - audit-b074ba92b861
    kind: result
    applied: true
    retired_at: '2026-08-02T22:35:46.448575+00:00'
  oompah.terminal_audit_result_intents:
  - project_id: proj-14849f1b
    task_id: OOMPAH-703
    audit_id: audit-b074ba92b861
    attempt_id: attempt-9ad9b59746a7
    target_state: Done
    evidence_fingerprint: f55c8ab7eae1ae9acff2b0164f275f9aebe7fafb215c1480a6604e9e4237964c
    status: In Validation
    audit_ids:
    - audit-b074ba92b861
    applied: true
    created_at: '2026-08-02T22:35:46.448589+00:00'
    applied_at: '2026-08-02T22:35:50.396009+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-b074ba92b861
    project_id: proj-14849f1b
    task_id: OOMPAH-703
    target_state: Done
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: f55c8ab7eae1ae9acff2b0164f275f9aebe7fafb215c1480a6604e9e4237964c
    attempts:
    - version: 1
      attempt_id: attempt-9ad9b59746a7
      target_state: Done
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: f55c8ab7eae1ae9acff2b0164f275f9aebe7fafb215c1480a6604e9e4237964c
      created_at: '2026-08-02T22:31:11.810654+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-02T22:31:11.810654+00:00'
      branch_key: OOMPAH-703
      verdict: pass
      completed_at: '2026-08-02T22:35:46.448436+00:00'
      ended_at: '2026-08-02T22:35:46.448436+00:00'
    requested_by:
      version: 1
      identity: lesserevil
      source: forge
    previous_state: In Review
    created_at: '2026-08-02T22:28:44.531536+00:00'
    updated_at: '2026-08-02T22:35:46.448436+00:00'
  - version: 1
    audit_id: audit-3990a0e653f5
    project_id: proj-14849f1b
    task_id: OOMPAH-703
    target_state: Merged
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: f55c8ab7eae1ae9acff2b0164f275f9aebe7fafb215c1480a6604e9e4237964c
    attempts:
    - version: 1
      attempt_id: attempt-9f942b3ce3c7
      target_state: Merged
      request_state: in_progress
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: f55c8ab7eae1ae9acff2b0164f275f9aebe7fafb215c1480a6604e9e4237964c
      created_at: '2026-08-02T22:36:10.967063+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-02T22:36:10.967063+00:00'
      branch_key: OOMPAH-703
    requested_by:
      version: 1
      identity: lesserevil
      source: forge
    previous_state: In Review
    created_at: '2026-08-02T22:28:44.531536+00:00'
    updated_at: '2026-08-02T22:36:10.967063+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-9ad9b59746a7
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: f55c8ab7eae1ae9acff2b0164f275f9aebe7fafb215c1480a6604e9e4237964c
    created_at: '2026-08-02T22:31:11.810654+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-02T22:31:11.810654+00:00'
    branch_key: OOMPAH-703
  - version: 1
    attempt_id: attempt-9f942b3ce3c7
    target_state: Merged
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: f55c8ab7eae1ae9acff2b0164f275f9aebe7fafb215c1480a6604e9e4237964c
    created_at: '2026-08-02T22:36:10.967063+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-02T22:36:10.967063+00:00'
    branch_key: OOMPAH-703
---
## Summary

Triggered by: OOMPAH-700

CI for OOMPAH-700 exposed a pre-existing timing race in tests/test_release_delivery_refresh.py::TestBacklogRefreshManagerInvalidate::test_invalidate_causes_next_get_or_start_to_refresh on Python 3.11: the test sleeps for 50 ms after scheduling BacklogRefreshManager background work and sometimes observes one service call instead of two. Replace fixed-duration sleeps in this invalidate test and adjacent BacklogRefreshManager tests with deterministic synchronization on refresh completion. Prefer an existing status/result completion signal; if production code needs a narrowly scoped awaitable completion primitive, add it in oompah/release_delivery_refresh.py with unit coverage and without changing non-test refresh semantics. Add regression coverage that invalidation starts exactly one subsequent refresh, preserves stale-while-revalidate behavior, and is reliable under repeated Python 3.11 execution. Acceptance criteria: the formerly failing test no longer relies on wall-clock sleeps to infer completion; adjacent invalidation tests use deterministic synchronization where applicable; a repeated focused run passes; make test and make check-secrets pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-02 21:51
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-02 21:51
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-02 21:52
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 1.3K out [1.3K total]
- Cost: $0.0000
- Exit: normal, Duration: 33s
- Log: OOMPAH-703__20260802T215147Z.jsonl
---
author: oompah
created: 2026-08-02 21:53
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-02 21:53
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-02 21:53
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 50.5K in / 326 out [50.8K total]
- Cost: $0.0000
- Exit: normal, Duration: 18s
- Log: OOMPAH-703__20260802T215345Z.jsonl
---
author: oompah
created: 2026-08-02 21:54
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-02 21:54
---
Focus: Test Engineer
---
author: oompah
created: 2026-08-02 21:54
---
Understanding: I will inspect BacklogRefreshManager and its invalidation tests, replace wall-clock completion assumptions with deterministic synchronization, add regression coverage for one subsequent refresh and stale-while-revalidate behavior, then run focused checks and the required Makefile validation.
---
author: oompah
created: 2026-08-02 21:55
---
Discovery: refresh jobs already own an asyncio.Task, and _run records terminal complete/failed state before the task finishes; however, tests cannot await that task through the public API. I will add a narrowly scoped wait_for_completion(project_id, branch) method that shields the refresh task from caller cancellation and returns the terminal RefreshStatus, then use it in the invalidate tests. This preserves stale-while-revalidate and normal refresh behavior while making completion synchronization explicit.
---
author: oompah
created: 2026-08-02 21:57
---
Implementation: added BacklogRefreshManager.wait_for_completion(), which awaits the existing job task without cancelling refresh work and returns terminal complete/failed status (or None for an unknown key). Added success, failure, and no-job unit coverage. Reworked all applicable invalidate tests to await completion, strengthened stale-while-revalidate assertions to verify the old result is served then replaced, and kept the exact one-subsequent-call assertion.
---
author: oompah
created: 2026-08-02 22:11
---
Verification: make test passed with 15,013 passed, 7 skipped, and 1 xfailed; make check-secrets passed. After the final synchronization assertion cleanup, the full release-delivery-refresh suite passed 55/55 under Python 3.12, and the completion/thread-safety/invalidation subset passed 9/9 in five consecutive Python 3.11 runs.
---
author: oompah
created: 2026-08-02 22:12
---
Completion: pushed commit 26b3f2ea9a99038870bc1f5d46a29157ee9be512. BacklogRefreshManager now exposes deterministic wait_for_completion() status synchronization; invalidate, stale-while-revalidate, regression, thread-safety, and completion tests no longer infer background completion from fixed sleeps. Required make test and make check-secrets gates passed, and the branch is clean/up to date.
---
author: oompah
created: 2026-08-02 22:13
---
Added deterministic refresh completion synchronization and updated backlog invalidation regression tests.
---
author: oompah
created: 2026-08-02 22:13
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 0, Tool calls: 69
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 18m 50s
- Log: OOMPAH-703__20260802T215421Z.jsonl
---
author: oompah
created: 2026-08-02 22:20
---
Branch quality gate passed for `26b3f2ea9a99038870bc1f5d46a29157ee9be512` using `make test` in 395.2s. Review creation may proceed.
---
author: oompah
created: 2026-08-02 22:28
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-02 22:28
---
YOLO: merged PR #663.
---
author: oompah
created: 2026-08-02 22:31
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-08-02 22:31
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-02 22:35
---
Audit PASS — Done

[REDACTED]

Safe evidence:
- branch_head: 26b3f2ea9a99038870bc1f5d46a29157ee9be512
- merge_commit: 53b14479d Merge pull request #663 from lesserevil/OOMPAH-703
- contains_main: true
- focused_tests_passed: TestBacklogRefreshManagerInvalidate + TestRefreshManagerCompletion = 8/8; +TestRefreshManagerThreadSafety = 9/9; full test_release_delivery_refresh.py module = 55/55
- [REDACTED-credential-key]: pass
- make_test_gate: pass (395.2s, per branch quality gate on 26b3f2ea9)
- primitive: BacklogRefreshManager.wait_for_completion in oompah/release_delivery_refresh.py:228
- sleep_replacements: 5 invalidate tests + thread-safety cleanup switched from asyncio.sleep(0.05|0.2) to wait_for_completion
- new_test_class: TestRefreshManagerCompletion (no-job, success, failure)
---
author: oompah
created: 2026-08-02 22:36
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/opus]
- Turns: 56, Tool calls: 45
- Tokens: 51 in / 9.4K out [9.4K total]
- Cost: $0.0000
- Exit: normal, Duration: 4m 48s
- Log: OOMPAH-703__20260802T223118Z.jsonl
---
author: oompah
created: 2026-08-02 22:36
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-08-02 22:36
---
Focus: Completion Auditor
---
<!-- COMMENTS:END -->
