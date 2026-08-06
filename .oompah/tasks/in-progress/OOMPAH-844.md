---
id: OOMPAH-844
type: task
status: In Progress
priority: null
title: Isolate orchestrator maintenance unit tests from full-corpus recovery scans
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-06T03:00:58.832102Z'
updated_at: '2026-08-06T04:02:17.974107Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
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
oompah.agent_run_id: 3bd713d1-6cf9-44ba-8b1a-9e448cbeb62c
oompah.task_costs:
  total_input_tokens: 10
  total_output_tokens: 1971
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 10
      output_tokens: 1971
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 1971
    cost_usd: 0.0
    recorded_at: '2026-08-06T03:54:04.186843+00:00'
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
<!-- COMMENTS:END -->
