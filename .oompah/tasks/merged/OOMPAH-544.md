---
id: OOMPAH-544
type: task
status: Merged
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
updated_at: '2026-08-02T18:36:08.821128Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-3d2398de29f9
    project_id: proj-14849f1b
    task_id: OOMPAH-544
    target_state: Merged
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 9a0f975899bcad1796fc5af499e82c3573bf67615735409e8c101f7396b4c9d9
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: 'Owner reconciliation: commit 3d72d2e69 implementing the timeout fix was
      merged in PR #577 at 7b7341201 after the recorded full local gate and green
      replacement CI. OOMPAH-699 tracks automatic convergence.'
    created_at: '2026-08-02T18:36:05.268397+00:00'
    applied: false
  version: 1
  pending_chain: []
  attempt_history: []
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
author: oompah
created: 2026-07-29 15:30
---
Added pytest-timeout and a global five-second per-test timeout, corrected three tests that leaked intentionally delayed background work, added configuration regression coverage, and verified make test locally (13,138 passed, 7 skipped) plus GitHub CI on Python 3.11, 3.12, and 3.13 (run 30465625633). Changes are committed and pushed as 3d72d2e69 on PR #577.
---
author: oompah
created: 2026-08-02 18:36
---
Override by oompah-cli: terminal transition to Merged applied by project owner.

Reason: Owner reconciliation: commit 3d72d2e69 implementing the timeout fix was merged in PR #577 at 7b7341201 after the recorded full local gate and green replacement CI. OOMPAH-699 tracks automatic convergence.
---
<!-- COMMENTS:END -->
