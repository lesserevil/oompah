---
id: OOMPAH-902
type: task
status: In Progress
priority: null
title: Make exact-gate sandboxes provide a hermetic operator identity
parent: OOMPAH-763
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-07T18:27:23.281558Z'
updated_at: '2026-08-07T18:27:41.961729Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Live deterministic regression: the exact BranchQualityGate for OOMPAH-863 at dab5702e5 failed after the same a85 composition passed a brokered local full make test. A fail-fast sandbox reproduction collected 280 affected tests and failed at tests/test_acp_codex_backend.py::test_native_validation_deep_root_uses_random_protected_socket because pwd.getpwuid(os.geteuid()) raised KeyError for uid 1000: the bubblewrap empty root mounts /usr but provides no trusted passwd/NSS identity. The complete gate then cascaded into 120 failures and 5 errors. Kernel evidence also shows nested bubblewrap AppArmor CAP_SYS_ADMIN denials in credential-isolation success paths, and all four workers spent long intervals in jbd2_log_wait_commit because gate temp/home/pycache are bound to ext4-backed /oompah-gate/tmp. Implementation scope: give the immutable candidate sandbox a server-owned, read-only minimal effective-user identity mapping without exposing credentials or allowing candidate rewriting; preserve production native-validation fail-closed behavior; make nested sandbox capability probing distinguish an unavailable host policy from a command/credential failure while keeping route-blocking assertions meaningful; and place disposable pytest scratch/worker homes/pycache on private sandbox tmpfs (coordinate with OOMPAH-868 rather than duplicating dedicated-CI logging work). Relevant files: oompah/quality_gate.py, rebase sandbox capability handling only if required, tests/test_quality_gate.py, tests/test_acp_codex_backend.py, tests/test_native_validation_guard.py, tests/test_epic_rebase_credential_isolation.py. Required tests: exact fail-fast pwd.getpwuid reproduction inside the real bubblewrap command; synthetic identity cannot be modified by candidate code; no host passwd secrets/remote credentials are exposed; nested-bwrap denial is classified fail-closed and success-path tests skip only on a proven host-policy denial; sandbox temp paths resolve to tmpfs; the affected process-global/credential modules pass in the actual BranchQualityGate; full make test passes at the exact candidate head. Acceptance: OOMPAH-863 and OOMPAH-866 exact gates no longer fail from missing UID identity, nested host-policy denial, or ext4 scratch amplification, while candidate isolation and exact-head/lease fencing remain intact.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

