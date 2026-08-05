---
id: OOMPAH-842
type: task
status: In Validation
priority: null
title: Bootstrap native validation guard provider fix onto main
parent: null
children: []
blocked_by: []
start_blocked_by: &id001
- OOMPAH-841
labels: []
assignee: null
created_at: '2026-08-05T18:52:26.995790Z'
updated_at: '2026-08-05T22:23:19.087825Z'
work_branch: OOMPAH-842
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/725
review_number: '725'
review_head: c5c0f4029096f43c669840e3138e1317a1aa3361
merged_at: null
oompah.start_blocked_by: *id001
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  task_branch: OOMPAH-842
  head_sha: c5c0f4029096f43c669840e3138e1317a1aa3361
  submitted_at: '2026-08-05T21:56:02.250758+00:00'
  updated_at: '2026-08-05T21:56:02.250758+00:00'
oompah.review_url: https://github.com/lesserevil/oompah/pull/725
oompah.review_number: '725'
oompah.work_branch: OOMPAH-842
oompah.target_branch: main
oompah.review_head: c5c0f4029096f43c669840e3138e1317a1aa3361
oompah.terminal_audit:
  queued_comment_posted: true
  applied_result_attempts:
    attempt-7e11ef429641: '2026-08-05T22:23:10.359201+00:00'
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-842
    target_state: Done
    evidence_fingerprint: a469e9b6423f8f24f8ff1429f5e606a9d512db781918a8bf5a9f33c8a17c26f0
    audit_ids:
    - audit-9ae8619f760e
    kind: result
    applied: true
    retired_at: '2026-08-05T22:23:10.359210+00:00'
  oompah.terminal_audit_result_intents:
  - project_id: proj-14849f1b
    task_id: OOMPAH-842
    audit_id: audit-9ae8619f760e
    attempt_id: attempt-7e11ef429641
    target_state: Done
    evidence_fingerprint: a469e9b6423f8f24f8ff1429f5e606a9d512db781918a8bf5a9f33c8a17c26f0
    status: In Validation
    audit_ids:
    - audit-9ae8619f760e
    applied: true
    created_at: '2026-08-05T22:23:10.359221+00:00'
    applied_at: '2026-08-05T22:23:16.457318+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-9ae8619f760e
    project_id: proj-14849f1b
    task_id: OOMPAH-842
    target_state: Done
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: a469e9b6423f8f24f8ff1429f5e606a9d512db781918a8bf5a9f33c8a17c26f0
    attempts:
    - version: 1
      attempt_id: attempt-7e11ef429641
      target_state: Done
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: a469e9b6423f8f24f8ff1429f5e606a9d512db781918a8bf5a9f33c8a17c26f0
      created_at: '2026-08-05T22:18:56.622928+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-05T22:18:56.622928+00:00'
      branch_key: OOMPAH-842
      verdict: pass
      completed_at: '2026-08-05T22:23:10.359077+00:00'
      ended_at: '2026-08-05T22:23:10.359077+00:00'
    requested_by:
      version: 1
      identity: lesserevil
      source: forge
    previous_state: In Review
    created_at: '2026-08-05T22:17:23.501614+00:00'
    updated_at: '2026-08-05T22:23:10.359077+00:00'
  - version: 1
    audit_id: audit-2fb4256b75cb
    project_id: proj-14849f1b
    task_id: OOMPAH-842
    target_state: Merged
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: a469e9b6423f8f24f8ff1429f5e606a9d512db781918a8bf5a9f33c8a17c26f0
    attempts: []
    requested_by:
      version: 1
      identity: lesserevil
      source: forge
    previous_state: In Review
    created_at: '2026-08-05T22:17:23.501614+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-7e11ef429641
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: a469e9b6423f8f24f8ff1429f5e606a9d512db781918a8bf5a9f33c8a17c26f0
    created_at: '2026-08-05T22:18:56.622928+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-05T22:18:56.622928+00:00'
    branch_key: OOMPAH-842
---
## Summary

OOMPAH-841 fixes a live service-capacity deadlock on the OOMPAH-763 program branch: the native Codex npm shebang resolves node through the command validation shim and can lease the sole validation slot for the full provider session. This standalone deployment task must land the exact reviewed OOMPAH-841 production and regression changes directly on main before the larger epic closes.\n\nImplementation scope: after OOMPAH-841 is committed, independently reviewed, tested, and pushed, cherry-pick or faithfully apply only its native validation guard/Codex bootstrap changes and tests onto current origin/main. Resolve conflicts without bringing unrelated OOMPAH-763 work. Run the focused native guard and Codex backend tests plus the canonical full branch gate, integrate through the normal review path, gracefully restart with make restart, and verify the live validation_resources owner is an actual heavyweight command rather than a provider root. Confirm waiting auditors/workers advance and no provider bootstrap consumes capacity.\n\nRelevant files: oompah/native_validation_guard.py, oompah/acp_backends/codex.py, tests/test_native_validation_guard.py, tests/test_acp_codex_backend.py.\n\nAcceptance criteria: the exact OOMPAH-841 fix is deployed on main with no unrelated program commits; focused/full gates pass; a live Codex agent starts with owner_count unchanged until it launches a real heavyweight command; current waiters drain naturally; server remains healthy after graceful restart.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-05 20:46
---
Direct implementation claimed after OOMPAH-841 passed independent review and its 254-test focused gate. Cherry-picked the exact reviewed OOMPAH-841 commit onto current origin/main da53569a; the only conflict was the owner-claim test import block, resolved by preserving main's imports plus the new regression dependencies. Resulting OOMPAH-842 head is d0286b5b. git diff --check and production py_compile pass. Runtime gates are waiting behind the scheduler-owned OOMPAH-828/OOMPAH-841 validation lane.
---
author: oompah
created: 2026-08-05 21:56
---
Final reviewed head c5c0f4029096f43c669840e3138e1317a1aa3361 is pushed on OOMPAH-842, exactly one commit over current origin/main 2c7f609e. Focused native guard/Codex/owner/audit-health gate passed (252 tests); canonical full gate passed (15,721 passed, 7 skipped, 1 xfailed, exit 0); diff check, py_compile, and secret scan passed. Independent review found no blockers.
---
author: oompah
created: 2026-08-05 21:56
---
Deploy native provider bootstrap validation lease fix onto main
---
author: oompah
created: 2026-08-05 22:07
---
Branch quality gate passed for `c5c0f4029096f43c669840e3138e1317a1aa3361` using `make test` in 649.5s. Review creation may proceed.
---
author: oompah
created: 2026-08-05 22:17
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-05 22:17
---
YOLO: merged PR #725.
---
author: oompah
created: 2026-08-05 22:19
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-08-05 22:19
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-05 22:23
---
Audit PASS — Done

[REDACTED]

Safe evidence:
- branch_head: c5c0f4029096f43c669840e3138e1317a1aa3361
- origin_main_head: b98ebb40d269ebeb7a134dc43add36bf782d9402
- prior_main_head: 2c7f609e0
- merge_pr: PR #725
- commit_title: Prevent native provider bootstrap validation leases
- diff_scope_files: oompah/acp_backends/codex.py, oompah/native_validation_guard.py, oompah/orchestrator.py, oompah/server.py, oompah/validation_resource_lease.py, tests/test_acp_codex_backend.py, tests/test_native_validation_guard.py, tests/test_owner_claim.py, tests/test_terminal_audit_health_api.py, tests/test_validation_resource_lease.py
- [REDACTED-credential-key]: pass (exit 0)
- focused_tests_present: test_trusted_provider_node_bootstrap_does_not_lease_entire_session, test_managed_native_cli_fences_exact_provider_bootstrap, and 14 additional native guard regression tests
- prior_full_gate: 15721 passed 7 skipped 1 xfailed exit 0 in 649.5s (per prior audit comment 2026-08-05 22:07)
---
<!-- COMMENTS:END -->
