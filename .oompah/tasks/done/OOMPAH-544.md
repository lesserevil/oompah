---
id: OOMPAH-544
type: task
status: Done
priority: 1
title: Bound individual pytest tests to five seconds in CI
parent: null
children: []
blocked_by: []
labels:
- human-only
- needs:test
- needs:ci
assignee: null
created_at: '2026-07-29T15:11:56.176459Z'
updated_at: '2026-07-29T15:30:01.607334Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Add pytest-timeout to the development/test dependencies and configure pytest so every individual test is limited to 5 seconds, with timeout diagnostics that identify the stalled test and its stack. Apply the same configuration to local Makefile-driven test runs and GitHub Actions because both consume pyproject.toml. Add a regression test that verifies the dependency and exact five-second pytest configuration. Run the previously flaky subprocess lifecycle test and the complete make test suite. Acceptance criteria: (1) pytest-timeout is installed by the dev extra used in CI; (2) pytest applies a 5-second per-test timeout by default; (3) timeout output identifies the affected test/stack; (4) the configuration regression test, tests/test_agent.py::test_stop_kills_spawned_descendant, and make test pass; (5) the stalled PR #577 CI run is superseded and all Python matrix checks are rerun.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-29 15:12
---
Claimed by the interactive Codex session. Implementing on the existing PR #577 branch so the new commit supersedes the stalled workflow run and reruns the full Python matrix.
---
author: oompah
created: 2026-07-29 15:24
---
Implemented and pushed commit 3d72d2e69 to PR #577. Added pytest-timeout with a global per-test timeout of 5 seconds using the thread method, plus a regression test for the configuration. The timeout exposed two tests that left executor threads sleeping for 10 seconds and one test that awaited a deliberately non-completing task; those tests now clean up promptly. Full local make test passes: 13,138 passed, 7 skipped in 75.43s. Replacement CI run 30465625633 is in progress; superseded hung run 30462624713 was canceled.
---
<!-- COMMENTS:END -->
