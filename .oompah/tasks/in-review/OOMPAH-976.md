---
id: OOMPAH-976
type: task
status: In Review
priority: null
title: Serialize native validation authority withdrawal with supervisor terminal claims
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-09T22:15:32.098347Z'
updated_at: '2026-08-09T23:04:15.780702Z'
work_branch: OOMPAH-976
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/785
review_number: '785'
review_head: 6af2014f97244e153ba3ea1ea70a4342d63ebc8b
merged_at: null
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: standalone
  task_branch: OOMPAH-976
  head_sha: 6af2014f97244e153ba3ea1ea70a4342d63ebc8b
  submitted_at: '2026-08-09T22:39:52.268716+00:00'
  updated_at: '2026-08-09T22:39:52.268716+00:00'
oompah.work_branch: OOMPAH-976
oompah.review_url: https://github.com/lesserevil/oompah/pull/785
oompah.review_number: '785'
oompah.target_branch: main
oompah.review_head: 6af2014f97244e153ba3ea1ea70a4342d63ebc8b
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-c8562f45ed03
    project_id: proj-14849f1b
    task_id: OOMPAH-976
    target_state: Merged
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: a2abaedcf05df4a1e17157fc81594ef9a394d669c0186d2970c9d7eaa0c111eb
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: 'Exact implementation head 6af2014f97244e153ba3ea1ea70a4342d63ebc8b passed
      independent security/liveness review, 234 serial plus 234 xdist tests, 10/10
      stress on both race edges, protected Python 3.11/3.12/3.13, merged via PR #785
      as 25154c8b709f5916d5a9744d2b2fe9979d64799f, and is the exact deployed running
      build.'
    created_at: '2026-08-09T23:04:14.257692+00:00'
    selected_ref: 6af2014f97244e153ba3ea1ea70a4342d63ebc8b
    selected_sha: 6af2014f97244e153ba3ea1ea70a4342d63ebc8b
    applied: false
  version: 1
  pending_chain: []
  attempt_history: []
---
## Summary

Triggered by the exact OOMPAH-975 protected Python 3.12 gate at d173e88eec2552ee639ef235a772fceeed8b66e6 (GitHub Actions run 31338540722, job 93308256998). tests/test_acp_codex_backend.py::TestCodexCliPath::test_managed_native_supervisor_cause_precedes_codex_item_completion[authority_withdrawn-10-True] intermittently failed because the process did not remain alive until the supervisor claimed the exact terminal cause. The test had already observed descriptor transfer and then wrote the cancellation marker; the validation shim nevertheless raised 'native validation authority was withdrawn before exec' and exited before the expected atomic supervisor terminal claim. Python 3.11/3.13 passed, the prior Python 3.12 head passed, and 19,235 other 3.12 tests passed, proving a scheduling race rather than an OOMPAH-975 semantic failure. Implementation scope: identify and serialize the descriptor-transfer, cancellation observation, exec admission, supervisor terminal claim, and generic item-completion boundaries so authority withdrawal after transfer deterministically preserves the exact cause and process ownership until the supervisor commits it. Do not relax fail-closed cancellation, permit execution after withdrawn authority, or weaken the assertion to accept both outcomes. Relevant code: oompah/native_validation_guard.py, oompah/acp_backends/codex.py, and tests/test_acp_codex_backend.py around test_managed_native_supervisor_cause_precedes_codex_item_completion. Required tests: deterministic barriers for withdrawal immediately before/after transfer and before/after exec admission; exact terminal cause wins generic completion; no descriptor/process/lease leak; repeated serial and xdist stress including Python 3.12. Acceptance: the failing interleaving is reproducible before the fix, deterministic after it, focused native-validation/Codex suites and protected matrix pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-09 22:25
---
Implementation started on branch OOMPAH-976. Reproduced the Python 3.12 authority-withdrawal timing lane locally and traced the unsafe interleaving to the shim receiving the lease descriptor before a final broker-mediated exec-admission decision; the shim could observe cancellation and exit while the supervisor's exact terminal claim was still pending. Implementing a fail-closed post-transfer admission handshake with deterministic race barriers and descriptor/lease cleanup coverage. The shared service will not be restarted from this lane.
---
author: oompah
created: 2026-08-09 22:38
---
Implemented the race fix on OOMPAH-976 after rebasing onto merged main e8be4d38. The heavyweight shim now requires a broker-mediated ADMIT/ADMITTED handshake after SCM_RIGHTS descriptor transfer. Exec admission and exact terminal claims linearize on the same run lock; cancellation before admission is claimed exactly before the shim is denied, while later withdrawal terminates an already-admitted generation without allowing post-withdrawal workload effects. The admission handler joins the atomic terminal claim directly, so a delayed supervisor observer cannot strand it. Coverage includes deterministic pre-admission, post-admission, timeout, blocked observer, exact-cause precedence, no-workload-after-withdrawal, lease cleanup, FD cleanup, and bounded retirement. Checks: 234 affected tests passed; both withdrawal edge nodes passed 10/10 stress repetitions each; diff and compile checks clean.
---
author: oompah
created: 2026-08-09 22:40
---
Implemented and pushed exact head 6af2014f97244e153ba3ea1ea70a4342d63ebc8b. Added authenticated post-transfer exec admission serialized with exact terminal claims; deterministic before/after-admission withdrawal coverage proves exact cause precedence, bounded termination, and no post-withdrawal workload, lease, or FD leak. Python 3.12 affected suites: 234 passed serial and 234 passed with xdist; withdrawal edge nodes passed 10/10 each under repeated serial stress. Ready for independent exact-head review.
---
author: oompah
created: 2026-08-09 22:41
---
Implementation pushed at exact head 6af2014f97244e153ba3ea1ea70a4342d63ebc8b. Authenticated ADMIT/ADMITTED handshake now linearizes native exec admission with the supervisor terminal claim; deterministic withdrawal before/after admission and cleanup tests pass. Affected suite: 234 serial and 234 xdist; both race edges 10/10 stress. Protected PR #785 is running while independent exact-head review completes.
---
author: oompah
created: 2026-08-09 22:49
---
Branch quality gate passed for `6af2014f97244e153ba3ea1ea70a4342d63ebc8b` using `make test` in 164.6s. Review creation may proceed.
---
<!-- COMMENTS:END -->
