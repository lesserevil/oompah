---
id: OOMPAH-668
type: bug
status: Open
priority: 1
title: Use the trusted test virtualenv without reinstalling inside quality-gate sandbox
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-31T21:35:20.853943Z'
updated_at: '2026-07-31T21:36:32.865803Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 8e4e3574b1f58ffe3b7c489be06bd9da31962659f65aef9ed6a6ca88664ecc25
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: f3d331f2-52a9-4fc3-b11f-8c0e6a4e1ce6
  claim_owner: 25dc1d1d-9292-4ddb-9dce-007ca37e5395
  claimed_at: '2026-07-31T21:36:26.684052+00:00'
  claim_expires_at: '2026-07-31T22:06:26.684052+00:00'
  retry_count: 0
  retry_after: null
oompah.agent_run_id: 4964095e-a27e-4656-9333-a6d3745467c2
---
## Summary

Triggered by: OOMPAH-664

Production reproduction on 2026-07-31 after OOMPAH-664 rebased onto deployed main: the OS-enforced branch gate mounts the service-owned complete test virtualenv read-only at candidate .venv, but git-archive timestamps make candidate pyproject.toml newer than .venv/.uv-setup. make test therefore runs uv pip install -e server before tests; the fail-closed sandbox intentionally exposes only /usr and cannot see the operator uv launcher, producing make: uv: No such file or directory. Even projecting uv would then attempt to mutate the protected read-only trusted runtime. Fix the Makefile quality-gate path so OOMPAH_PYTEST_GATE uses and validates the server-provided test virtualenv without invoking setup or dependency installation, while normal operator and developer make test behavior still installs declared dev dependencies. Preserve sandbox isolation and fail closed if the trusted Python or required test modules are absent. Add regressions for stale pyproject and marker mtimes, no uv visibility, read-only mounted runtime, missing trusted runtime, and unchanged non-gate test-setup behavior; extend the real bubblewrap make-target test to exercise the project Makefile dependency path. Acceptance: OOMPAH-664 exact-head gate reaches pytest instead of failing setup, candidate code cannot mutate the host runtime, focused quality-gate and Makefile tests pass, and the full project gate passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-31 21:35
---
Claimed directly for operator recovery because OOMPAH-664 is otherwise deadlocked in Ready delivery. Reproduction is the production gate on head 9b0696866: make test enters .venv/.uv-setup and fails before pytest because uv is deliberately absent from the sandbox. I will separate gate-mode trusted-runtime validation from normal dependency installation, add regression coverage, run focused and full gates, and deploy before requeueing OOMPAH-664.
---
author: oompah
created: 2026-07-31 21:36
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-31 21:36
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
