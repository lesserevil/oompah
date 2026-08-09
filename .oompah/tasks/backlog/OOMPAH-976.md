---
id: OOMPAH-976
type: task
status: Backlog
priority: null
title: Serialize native validation authority withdrawal with supervisor terminal claims
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-09T22:15:32.098347Z'
updated_at: '2026-08-09T22:15:32.098347Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Triggered by the exact OOMPAH-975 protected Python 3.12 gate at d173e88eec2552ee639ef235a772fceeed8b66e6 (GitHub Actions run 31338540722, job 93308256998). tests/test_acp_codex_backend.py::TestCodexCliPath::test_managed_native_supervisor_cause_precedes_codex_item_completion[authority_withdrawn-10-True] intermittently failed because the process did not remain alive until the supervisor claimed the exact terminal cause. The test had already observed descriptor transfer and then wrote the cancellation marker; the validation shim nevertheless raised 'native validation authority was withdrawn before exec' and exited before the expected atomic supervisor terminal claim. Python 3.11/3.13 passed, the prior Python 3.12 head passed, and 19,235 other 3.12 tests passed, proving a scheduling race rather than an OOMPAH-975 semantic failure. Implementation scope: identify and serialize the descriptor-transfer, cancellation observation, exec admission, supervisor terminal claim, and generic item-completion boundaries so authority withdrawal after transfer deterministically preserves the exact cause and process ownership until the supervisor commits it. Do not relax fail-closed cancellation, permit execution after withdrawn authority, or weaken the assertion to accept both outcomes. Relevant code: oompah/native_validation_guard.py, oompah/acp_backends/codex.py, and tests/test_acp_codex_backend.py around test_managed_native_supervisor_cause_precedes_codex_item_completion. Required tests: deterministic barriers for withdrawal immediately before/after transfer and before/after exec admission; exact terminal cause wins generic completion; no descriptor/process/lease leak; repeated serial and xdist stress including Python 3.12. Acceptance: the failing interleaving is reproducible before the fix, deterministic after it, focused native-validation/Codex suites and protected matrix pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

