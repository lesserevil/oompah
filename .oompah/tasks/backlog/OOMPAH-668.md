---
id: OOMPAH-668
type: bug
status: Backlog
priority: 1
title: Use the trusted test virtualenv without reinstalling inside quality-gate sandbox
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-31T21:35:20.853943Z'
updated_at: '2026-07-31T21:35:20.853943Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Triggered by: OOMPAH-664

Production reproduction on 2026-07-31 after OOMPAH-664 rebased onto deployed main: the OS-enforced branch gate mounts the service-owned complete test virtualenv read-only at candidate .venv, but git-archive timestamps make candidate pyproject.toml newer than .venv/.uv-setup. make test therefore runs uv pip install -e server before tests; the fail-closed sandbox intentionally exposes only /usr and cannot see the operator uv launcher, producing make: uv: No such file or directory. Even projecting uv would then attempt to mutate the protected read-only trusted runtime. Fix the Makefile quality-gate path so OOMPAH_PYTEST_GATE uses and validates the server-provided test virtualenv without invoking setup or dependency installation, while normal operator and developer make test behavior still installs declared dev dependencies. Preserve sandbox isolation and fail closed if the trusted Python or required test modules are absent. Add regressions for stale pyproject and marker mtimes, no uv visibility, read-only mounted runtime, missing trusted runtime, and unchanged non-gate test-setup behavior; extend the real bubblewrap make-target test to exercise the project Makefile dependency path. Acceptance: OOMPAH-664 exact-head gate reaches pytest instead of failing setup, candidate code cannot mutate the host runtime, focused quality-gate and Makefile tests pass, and the full project gate passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

