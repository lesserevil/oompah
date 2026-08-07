---
id: OOMPAH-906
type: task
status: Backlog
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
updated_at: '2026-08-07T21:47:20.306703Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Exact isolated branch gates for OOMPAH-646 and OOMPAH-869 produced the same three false failures in tests/test_acp_codex_backend.py: test_managed_native_cli_guard_uses_auditor_owner_identity, test_managed_native_cli_does_not_lease_an_entire_light_turn, and test_managed_native_cli_rejects_task_writable_direct_codex. The gate places HOME beneath /tmp/oompah-gate; _create_native_validation_runtime_root derives HOME/.oompah/native-validation-guards and correctly rejects it because /tmp is an untrusted task-writable root. OOMPAH-869 otherwise passed 15,948 tests, and hosted CI/worktree gates use a trusted HOME and pass. Implementation scope: make the isolated quality-gate runner provide an operator-trusted native-validation guard runtime outside every workspace/temp writable root without weakening executable or runtime-root safety checks; ensure subprocess HOME isolation and cleanup remain bounded. Relevant context: branch quality-gate workspace/environment construction, oompah/acp_backends/codex.py native guard bootstrap, and tests/test_acp_codex_backend.py. Required tests: deterministically reproduce an isolated gate whose HOME is under /tmp, prove the three managed-native tests execute their intended paths, retain rejection of task-writable Codex binaries/runtime roots, and exercise cleanup/cancellation. Acceptance: an exact isolated make test no longer reports these harness-only failures, native guard state remains inaccessible to the task sandbox, and focused quality-gate/Codex suites plus the full gate pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

