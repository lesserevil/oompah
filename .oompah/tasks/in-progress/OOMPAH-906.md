---
id: OOMPAH-906
type: task
status: In Progress
priority: null
title: Keep isolated quality-gate HOME from invalidating the trusted native validation
  guard
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-07T21:47:20.306703Z'
updated_at: '2026-08-07T22:03:11.685888Z'
work_branch: OOMPAH-906
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  task_branch: OOMPAH-906
  head_sha: 273c3ddb683abe295f2c878b022d899896ebd618
  submitted_at: '2026-08-07T22:03:00.915026+00:00'
  updated_at: '2026-08-07T22:03:00.915026+00:00'
oompah.work_branch: OOMPAH-906
---
## Summary

Exact isolated branch gates for OOMPAH-646 and OOMPAH-869 produced the same three false failures in tests/test_acp_codex_backend.py: test_managed_native_cli_guard_uses_auditor_owner_identity, test_managed_native_cli_does_not_lease_an_entire_light_turn, and test_managed_native_cli_rejects_task_writable_direct_codex. The gate places HOME beneath /tmp/oompah-gate; _create_native_validation_runtime_root derives HOME/.oompah/native-validation-guards and correctly rejects it because /tmp is an untrusted task-writable root. OOMPAH-869 otherwise passed 15,948 tests, and hosted CI/worktree gates use a trusted HOME and pass. Implementation scope: make the isolated quality-gate runner provide an operator-trusted native-validation guard runtime outside every workspace/temp writable root without weakening executable or runtime-root safety checks; ensure subprocess HOME isolation and cleanup remain bounded. Relevant context: branch quality-gate workspace/environment construction, oompah/acp_backends/codex.py native guard bootstrap, and tests/test_acp_codex_backend.py. Required tests: deterministically reproduce an isolated gate whose HOME is under /tmp, prove the three managed-native tests execute their intended paths, retain rejection of task-writable Codex binaries/runtime roots, and exercise cleanup/cancellation. Acceptance: an exact isolated make test no longer reports these harness-only failures, native guard state remains inaccessible to the task sandbox, and focused quality-gate/Codex suites plus the full gate pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-07 21:57
---
Direct fix implemented in isolated branch OOMPAH-906. Xdist workers now preserve the quality gate's trusted pre-worker HOME outside task-writable high-churn tmp roots, fail closed when a configured gate HOME overlaps /tmp, /var/tmp, or configured gate temp/run roots, and remove the external per-worker HOME during teardown. Evidence so far: worker-isolation unit suite 20 passed; the exact three OOMPAH-869 managed-native failures passed 3/3 under simulated gate + xdist and the canonical broker; broader parallel/Codex/quality-gate suite passed 174/174; Ruff, py_compile, diff check, and secret scan pass. Final xdist module rerun and commit/push remain.
---
author: oompah
created: 2026-08-07 22:02
---
Implementation is committed and pushed on origin/OOMPAH-906 at exact SHA 273c3ddb683abe295f2c878b022d899896ebd618. The change preserves the trusted exact-gate HOME for per-worker native-validation guard state, continues to isolate temp/XDG state beneath each worker run root, fails closed for HOME under /tmp, /var/tmp, or configured writable gate roots, and cleans external worker HOME state during teardown. Validation: 20 focused worker-isolation tests passed; the exact three OOMPAH-869 false-failure nodes passed 3/3 under simulated gate + real xdist using the canonical broker; 174 affected parallel/Codex/quality-gate tests passed; final Ruff, py_compile, git diff --check, and secret scan passed. uv.lock setup-only drift from local environment creation was reverted and excluded. Branch is clean and exactly matches origin. Handoff: cherry-pick 273c3ddb683abe295f2c878b022d899896ebd618 into the systemic composition; do not mutate OOMPAH-869's review head.
---
<!-- COMMENTS:END -->
