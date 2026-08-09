---
id: OOMPAH-971
type: task
status: In Progress
priority: null
title: Make terminal-audit full gates portable to task-private virtualenvs
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-09T19:50:52.737789Z'
updated_at: '2026-08-09T20:11:31.847675Z'
work_branch: OOMPAH-971
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: standalone
  task_branch: OOMPAH-971
  head_sha: 125d19edd8b6c4e3bb001b675cf77da084ea25a2
  submitted_at: '2026-08-09T20:11:22.877849+00:00'
  updated_at: '2026-08-09T20:11:22.877849+00:00'
oompah.work_branch: OOMPAH-971
---
## Summary

Live OOMPAH-967 completion audit at exact merged head 5adb50e55 ran make test in a detached auditor worktree with OOMPAH_TASK_VENV=.oompah/task-venv and no repo .venv. The gate reported 19,144 passes but 10 infrastructure failures: seven scripts/run-tests.sh contract tests reached the fallback repo .venv Python-path error before their intended invalid-worker/HOME assertions, plus environment-sensitive failures in managed native lifecycle, the cold thousand-task Markdown page, and validation command lifecycle. Hosted exact-head Python 3.11/3.12/3.13 all passed. This is not OOMPAH-967 behavior, but it falsely routed a merged task to Needs CI Fix. OOMPAH-906 hardened isolated quality-gate HOME and OOMPAH-862 reuses existing local gates; neither covers an auditor-required full gate when only a valid task-private venv exists.\n\nImplementation scope: reproduce the detached terminal-audit Makefile environment (valid absolute OOMPAH_TASK_VENV/OOMPAH_TEST_PYTHON, no repo .venv, xdist worker isolation, trusted auditor HOME); make nested runner contract tests and the affected infrastructure modules exercise their intended assertions without assuming .venv or losing the configured interpreter/capabilities; order runner preflight diagnostics deterministically; preserve fail-closed interpreter, trusted-HOME, symlink, writable-root, and validation-resource safety. Do not merely widen timeouts or weaken path checks.\n\nRequired tests: run test_pytest_parallel.py, the exact managed-native lifecycle node, cold thousand-task page node, and validation-command lifecycle node from a detached-worktree/task-private-venv harness; prove invalid/missing interpreter still fails closed when it is the relevant precondition; prove ordinary repo .venv and hosted CI remain compatible; add a regression that an auditor make test cannot fail solely because .venv is absent when OOMPAH_TASK_VENV is valid. Acceptance: the exact OOMPAH-967 harness-only failure set is eliminated deterministically, focused modules and protected matrix pass, and future terminal audits do not route good merged code to Needs CI Fix for this environment mismatch.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-09 19:51
---
Accepted for direct-owner repair from OOMPAH-967 audit attempt audit-e269ff899599. Hosted exact-head CI was green; this task fixes the detached-auditor task-private-venv gate mismatch that produced the false Needs CI Fix state.
---
author: oompah
created: 2026-08-09 20:11
---
Implementation complete at rebased exact head 125d19edd8b6c4e3bb001b675cf77da084ea25a2; stable patch identity 34cd50a038dcbd0a0a0c02cb1621d091990a6206 is unchanged from independently reviewed head 5ec355f21. The test-only repair supplies the active absolute task-private interpreter to nested runner preflight tests and removes unrelated fsync/atomic-write setup cost from the cold pagination fixture without changing production checks or timeouts. Evidence: detached runner 35/35, accurate loaded affected suite 726/726, lifecycle stress 48/48, independent detached review no blockers with explicit fail-closed checks green, post-rebase focused 36/36, terminal-audit mutation scan passed, and diff check clean.
---
author: oompah
created: 2026-08-09 20:11
---
Fixed detached terminal-audit harness portability without weakening production safety; exact rebased head is independently reviewed and focused/loaded/stress coverage is green.
---
<!-- COMMENTS:END -->
