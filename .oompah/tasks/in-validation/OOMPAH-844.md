---
id: OOMPAH-844
type: task
status: In Validation
priority: null
title: Isolate orchestrator maintenance unit tests from full-corpus recovery scans
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-06T03:00:58.832102Z'
updated_at: '2026-08-06T05:02:08.765578Z'
work_branch: OOMPAH-844
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/730
review_number: '730'
review_head: d58976219e939c349498f69ce2fdbcb6ff650e96
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 200b1ea64865a868d8ee4246a376cf8f29dd7986d9268d55b7922c05417d48f5
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-06T03:54:09.275440+00:00'
  matched_identifiers: []
  evidence: 'Focus handoff: duplicate_detector

    Duplicate preflight verdict: no_duplicate

    Matches: none

    Evidence: The task corpus was comprehensively searched across 34 similarity candidates
    and all 508 projects tasks. All tasks in the provided corpus are in terminal states
    (Archived, Done, or Merged). OOMPAH-844 addresses a specific test isolation and
    timeout issue: stubbing `_recover_release_addendum_leases()` in the repo-heal
    unit test to prevent accidental full-corpus scanning, adding bounded timeouts
    for storage-backed orchestrator construction tests, and auditing adjacent `_tick`
    tests for similar coupling. The closest reviewed tasks (OOMPAH-217, OOMPAH-218,
    OOMPAH-219) address orchestrator behavior and safety limits but do not cover test
    isolation from corpus recovery scans or timeout management. No open or in-progress
    task covers this implementation scope.

    Focus handoff: duplicate_detector


    Duplicate preflight verdict: no_duplicate


    Matches: none


    Evidence: The task corpus was comprehensively searched across 34 similarity candidates
    and all 508 projects tasks. All tasks in the provided corpus are in terminal states
    (Archived, Done, or Merged). OOMPAH-844 addresses a specific test isolation and
    timeout issue: stubbing `_recover_release_addendum_leases()` in the repo-heal
    unit test to prevent accidental full-corpus scanning, adding bounded timeouts
    for storage-backed orchestrator construction tests, and auditing adjacent `_tick`
    tests for similar coupling. The closest reviewed tasks (OOMPAH-217, OOMPAH-218,
    OOMPAH-219) address orchestrator behavior and safety limits but do not cover test
    isolation from corpus recovery scans or timeout management. No open or in-progress
    task covers this implementation scope.'
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: null
oompah.task_costs:
  total_input_tokens: 16
  total_output_tokens: 2156
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 10
      output_tokens: 1971
      cost_usd: 0.0
    unknown:
      input_tokens: 6
      output_tokens: 185
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 1971
    cost_usd: 0.0
    recorded_at: '2026-08-06T03:54:04.186843+00:00'
  - profile: auditor
    model: unknown
    input_tokens: 6
    output_tokens: 185
    cost_usd: 0.0
    recorded_at: '2026-08-06T05:02:06.182535+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-844__20260806T035057Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-844
    source_sha: fe6257b596f79296b11dd4870a62bdbc79159d27
    completed_at: '2026-08-06T03:54:06.870136+00:00'
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  task_branch: OOMPAH-844
  head_sha: d58976219e939c349498f69ce2fdbcb6ff650e96
  submitted_at: '2026-08-06T04:14:10.074408+00:00'
  updated_at: '2026-08-06T04:14:10.074408+00:00'
oompah.review_url: https://github.com/lesserevil/oompah/pull/730
oompah.review_number: '730'
oompah.work_branch: OOMPAH-844
oompah.target_branch: main
oompah.review_head: d58976219e939c349498f69ce2fdbcb6ff650e96
oompah.terminal_audit:
  queued_comment_posted: true
  applied_result_attempts:
    attempt-5ae16c12cc7d: '2026-08-06T05:01:18.699605+00:00'
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-844
    target_state: Done
    evidence_fingerprint: 092291c29764bf5800f8f18879a35fe4249c6f25281c5539668536984fcf9f4f
    audit_ids:
    - audit-c9dff9bc3978
    kind: result
    applied: true
    retired_at: '2026-08-06T05:01:18.699617+00:00'
  oompah.terminal_audit_result_intents:
  - project_id: proj-14849f1b
    task_id: OOMPAH-844
    audit_id: audit-c9dff9bc3978
    attempt_id: attempt-5ae16c12cc7d
    target_state: Done
    evidence_fingerprint: 092291c29764bf5800f8f18879a35fe4249c6f25281c5539668536984fcf9f4f
    status: In Validation
    audit_ids:
    - audit-c9dff9bc3978
    applied: true
    created_at: '2026-08-06T05:01:18.699633+00:00'
    applied_at: '2026-08-06T05:01:26.406791+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-c9dff9bc3978
    project_id: proj-14849f1b
    task_id: OOMPAH-844
    target_state: Done
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 092291c29764bf5800f8f18879a35fe4249c6f25281c5539668536984fcf9f4f
    attempts:
    - version: 1
      attempt_id: attempt-5ae16c12cc7d
      target_state: Done
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 092291c29764bf5800f8f18879a35fe4249c6f25281c5539668536984fcf9f4f
      created_at: '2026-08-06T04:56:25.746278+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-06T04:56:25.746278+00:00'
      branch_key: OOMPAH-844
      verdict: pass
      completed_at: '2026-08-06T05:01:18.699434+00:00'
      ended_at: '2026-08-06T05:01:18.699434+00:00'
    requested_by:
      version: 1
      identity: yolo-merge
      source: oompah
    previous_state: In Review
    created_at: '2026-08-06T04:53:16.902678+00:00'
    updated_at: '2026-08-06T05:01:18.699434+00:00'
  - version: 1
    audit_id: audit-4d23077d474f
    project_id: proj-14849f1b
    task_id: OOMPAH-844
    target_state: Merged
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 092291c29764bf5800f8f18879a35fe4249c6f25281c5539668536984fcf9f4f
    attempts: []
    requested_by:
      version: 1
      identity: yolo-merge
      source: oompah
    previous_state: In Review
    created_at: '2026-08-06T04:53:16.902678+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-5ae16c12cc7d
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 092291c29764bf5800f8f18879a35fe4249c6f25281c5539668536984fcf9f4f
    created_at: '2026-08-06T04:56:25.746278+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-06T04:56:25.746278+00:00'
    branch_key: OOMPAH-844
---
## Summary

Bug: the exact combined-tree gate for OOMPAH-821 failed after 16,116 passing tests because tests/test_orchestrator_handlers.py::TestRepoHealErrorReporting::test_heal_failure_does_not_raise_from_tick invokes the real _recover_release_addendum_leases() path. That path scans the full task corpus, can exceed the global per-test timeout under xdist saturation, and leaves the intentionally failing maintenance future visible during teardown. The same systemic coupling has affected other exact-head gates. Implementation scope: isolate the repo-heal unit test from unrelated release-addendum recovery work by stubbing _recover_release_addendum_leases; give storage-backed orchestrator construction tests an explicit bounded timeout where cold-corpus startup can legitimately exceed the global 5-second default; audit adjacent _tick unit tests for the same accidental corpus dependency without weakening production timeouts or assertions. Relevant files: tests/test_orchestrator_handlers.py and tests/test_orchestrator_github_lifecycle.py; production code should change only if investigation finds a real unbounded scan. Required tests: reproduce both named tests under repeated concurrent execution, run the affected modules, and run make test at the exact review head. Acceptance: the tests remain semantically scoped, fail on their intended assertions, pass repeatedly under load, do not leak background futures at teardown, and the canonical full gate passes without raising the per-test timeout globally.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-06 03:50
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-06 03:50
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-06 03:54
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 2.0K out [2.0K total]
- Cost: $0.0000
- Exit: normal, Duration: 3m 50s
- Log: OOMPAH-844__20260806T035057Z.jsonl
---
author: oompah
created: 2026-08-06 03:55
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-06 03:55
---
Focus: Oompah Tests Auth Specialist
---
author: oompah
created: 2026-08-06 03:55
---
Understanding: I will inspect the named repo-heal and storage-backed orchestrator tests plus adjacent _tick tests, isolate only unrelated release-addendum recovery, add explicit bounded startup timeouts where justified, and verify focused suites under concurrency without changing production timeout policy.
---
author: oompah
created: 2026-08-06 04:01
---
Discovery: HEAD predates the existing OOMPAH-821 stabilization patch. The exact outlier is TestRepoHealErrorReporting::test_heal_failure_does_not_raise_from_tick, which lacks the recovery stub while sibling tick tests already stub it. The storage-backed lifecycle construction outlier is TestCandidateFetchGitHub::test_github_issues_have_correct_tracker_kind; prior gate evidence uses a 20-second pytest marker for its cold startup. I will apply those scoped changes and preserve the global five-second timeout.
---
author: oompah
created: 2026-08-06 04:02
---
Implementation: Added a scoped @pytest.mark.timeout(20) to the storage-backed GitHub lifecycle construction test. Stubbed _recover_release_addendum_leases in the repo-heal failure test and three adjacent epic-maintenance _tick tests, preserving their existing assertions and teardown handling. No production code or global timeout changed.
---
author: oompah
created: 2026-08-06 04:04
---
Verification: Focused xdist checks passed: 15 affected handler tests in 7.33s, lifecycle construction target in 3.48s, full GitHub lifecycle module (41 tests) in 13.37s, and eight concurrent repo-heal regression processes. The combined affected modules passed 320 tests in 86.54s. Next is make test at the review head.
---
author: oompah
created: 2026-08-06 04:11
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 0, Tool calls: 104
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 16m 41s
- Log: OOMPAH-844__20260806T035521Z.jsonl
---
author: oompah
created: 2026-08-06 04:12
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-08-06 04:12
---
Focus: Oompah Tests Auth Specialist
---
author: oompah
created: 2026-08-06 04:14
---
Completion: Delivered and pushed d58976219 (OOMPAH-844). Focused xdist and concurrent regression checks passed (320 affected-module tests in 86.54s). The required make test was invoked at this exact head but could not start pytest because the managed validation guard attempted chmod on its shared lock directory under /home/shedwards/src/oompah, which is read-only in this worktree (OSError 30). No source or timeout-policy failure was observed; integration should run the canonical gate in its writable validation environment.
---
author: oompah
created: 2026-08-06 04:14
---
Isolated maintenance unit tests from full-corpus scans; focused concurrency checks passed
---
author: oompah
created: 2026-08-06 04:14
---
Run #2 [attempt=2, profile=standard, role=standard -> Codex/gpt-5.6-terra]
- Turns: 0, Tool calls: 16
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 1m 56s
- Log: OOMPAH-844__20260806T041250Z.jsonl
---
author: oompah
created: 2026-08-06 04:40
---
Branch quality gate passed for `d58976219e939c349498f69ce2fdbcb6ff650e96` using `make test` in 662.7s. Review creation may proceed.
---
author: oompah
created: 2026-08-06 04:53
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-06 04:53
---
YOLO: merged PR #730.
---
author: oompah
created: 2026-08-06 04:56
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-08-06 04:56
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-06 05:01
---
Audit PASS — Done

[REDACTED]

Safe evidence:
- head_sha: d58976219e939c349498f69ce2fdbcb6ff650e96
- files_changed: tests/test_orchestrator_github_lifecycle.py, tests/test_orchestrator_handlers.py
- insertions: 14
- merged_pr: 730
- merge_commit: f2b319c11
- branch_quality_gate: make test passed in 662.7s at d58976219
- timeout_marker_lifecycle: line 293 (@pytest.mark.timeout(20))
- timeout_marker_handlers: line 3161 (@pytest.mark.timeout(20))
- recover_leases_stub_repo_heal: line 3177
- recover_leases_stubs_tick: handlers lines 1299, 1339, 1391
- production_code_changed: none
---
author: oompah
created: 2026-08-06 05:02
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/opus]
- Turns: 41, Tool calls: 23
- Tokens: 6 in / 185 out [191 total]
- Cost: $0.0000
- Exit: normal, Duration: 5m 38s
- Log: OOMPAH-844__20260806T045638Z.jsonl
---
<!-- COMMENTS:END -->
