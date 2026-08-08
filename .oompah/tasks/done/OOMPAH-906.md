---
id: OOMPAH-906
type: task
status: Done
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
updated_at: '2026-08-08T03:56:38.192524Z'
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
  head_sha: aca098a94f75330939e7fe392bca31b33cc87ced
  submitted_at: '2026-08-07T23:36:59.852789+00:00'
  updated_at: '2026-08-07T23:36:59.852789+00:00'
oompah.work_branch: OOMPAH-906
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-00878f94b610
    project_id: proj-14849f1b
    task_id: OOMPAH-906
    target_state: Done
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 4d0eeeabd35153e84764bde758a72a3f492073b92e955be574bba8df43b6cab1
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: 'Project-owner reconciliation: the task implementation and subsequent
      cleanup hardening are published on epic-OOMPAH-763 at e74449e4f9303f35c2cc2c1c5fc78ee979f4d268.
      Independent reviews accepted the exact composition after blockers were fixed;
      affected tests passed 392/392 and the exact full make test passed 17,860 with
      zero failures.'
    created_at: '2026-08-08T03:56:21.782606+00:00'
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-906
    target_state: Done
    evidence_fingerprint: 4d0eeeabd35153e84764bde758a72a3f492073b92e955be574bba8df43b6cab1
    audit_ids: []
    kind: override
    applied: true
    retired_at: '2026-08-08T03:56:32.641230+00:00'
  oompah.terminal_audit_result_intents: []
  version: 1
  pending_chain: []
  attempt_history: []
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
author: oompah
created: 2026-08-07 22:03
---
Preserved trusted exact-gate HOME for xdist native-validation guard state with fail-closed writable-root checks, bounded teardown cleanup, and regression coverage. Exact head: 273c3ddb683abe295f2c878b022d899896ebd618.
---
author: oompah
created: 2026-08-07 22:37
---
Independent-review findings are fixed and pushed at replacement exact head 510988c96e982ff170fbb78bda8c39963f11b113. The resolved candidate worker HOME and runner-owned session root are now checked against every writable gate root, relative temp/run roots resolve against the worker cwd, HOME/pytest-workers and session symlink escapes fail closed, and recursive cleanup never follows a resolved symlink target. Each gate gets a unique runner/controller-owned HOME namespace; controller teardown and the shell runner EXIT trap remove partial state after killed/crashed xdist workers and configuration failures. Regression coverage includes OOMPAH_TEMP_ROOT=/home/oompah/pytest-workers, all six relative temp/run variables, parent symlinks, controller crash/config leftovers, killed pytest, and config-failure cleanup. Canonical broker evidence: focused worker-isolation plus the exact three OOMPAH-869 managed-native reproductions passed 36/36 under simulated gate + real xdist; broader parallel/Codex/quality-gate modules passed 187/187 under the same boundary; both runs verified no worker-HOME leak. Final Ruff, py_compile, bash syntax, diff check, and make check-secrets passed. Branch is clean and matches origin/OOMPAH-906 exactly.
---
author: oompah
created: 2026-08-07 22:38
---
Addressed blocked independent-review findings with fully resolved candidate/root validation, relative-root and symlink defenses, and runner/controller-owned crash-safe cleanup. Replacement exact head: 510988c96e982ff170fbb78bda8c39963f11b113.
---
author: oompah
created: 2026-08-07 23:36
---
Final independent-review replacement is pushed at exact head aca098a94f75330939e7fe392bca31b33cc87ced. The quality gate now mounts a distinct server-owned trusted HOME capability outside the candidate-writable run root; legacy three-argument injected launchers receive host-materialized paths; every allocation, completion, cancellation, and failure path releases the validation lease/generation and removes both run roots and sidecars. Restart cleanup is inode/PID-start-tick fenced, preserves active or unknown owners, age-bounds missing/corrupt metadata, safely reclaims abandoned .<root>.scavenge-* quarantines after hard crashes, and keeps owner sidecars until quarantine recovery completes. The runner validates preallocated worker HOME before any disposable allocation and cleans controller/configuration-failure state. Evidence on the exact content: canonical-broker affected suite 134/134 passed and returned to idle with zero owners/waiters; real built-in bubblewrap execution of the three OOMPAH-869 managed-native regressions passed 3/3 at the exact committed head; git diff --check, bash syntax, focused Ruff, make terminal-audit-scan, and make check-secrets all passed. Two independent adversarial reviews ACCEPT exact aca098a94f75330939e7fe392bca31b33cc87ced, including a manual hard-crash quarantine replay. Branch is clean and exactly matches origin/OOMPAH-906.
---
author: oompah
created: 2026-08-07 23:37
---
Isolated validation guards in a server-owned HOME, hardened allocation and xdist cleanup, and added restart-safe stale-root/quarantine recovery; exact head aca098a94f75330939e7fe392bca31b33cc87ced passed 134 affected tests, 3 real-bwrap regressions, static/security gates, and two independent reviews.
---
author: oompah
created: 2026-08-08 03:56
---
Override by oompah-cli: terminal transition to Done applied by project owner.

Reason: Project-owner reconciliation: the task implementation and subsequent cleanup hardening are published on epic-OOMPAH-763 at e74449e4f9303f35c2cc2c1c5fc78ee979f4d268. Independent reviews accepted the exact composition after blockers were fixed; affected tests passed 392/392 and the exact full make test passed 17,860 with zero failures.
---
author: oompah
created: 2026-08-08 03:56
---
Integrated and validated on epic-OOMPAH-763 at e74449e4f9303f35c2cc2c1c5fc78ee979f4d268.
---
<!-- COMMENTS:END -->
