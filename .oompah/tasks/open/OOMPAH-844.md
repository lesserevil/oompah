---
id: OOMPAH-844
type: task
status: Open
priority: null
title: Isolate orchestrator maintenance unit tests from full-corpus recovery scans
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-06T03:00:58.832102Z'
updated_at: '2026-08-06T03:50:35.290774Z'
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
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 9d6633c9-e1e0-440e-bb20-0c87df8cc20d
  claim_owner: 11468835-7c49-48df-a46d-b143af3a940a
  claimed_at: '2026-08-06T03:47:31.188749+00:00'
  claim_expires_at: '2026-08-06T04:17:31.188749+00:00'
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 40447f4b-c911-472a-bb22-6d9b498b3b3f
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
<!-- COMMENTS:END -->
