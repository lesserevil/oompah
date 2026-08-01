---
id: OOMPAH-673
type: bug
status: Backlog
priority: 2
title: Make canonical CLI mismatch recovery unambiguous across upgrades
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-01T02:34:24.348580Z'
updated_at: '2026-08-01T02:34:24.348580Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Triggered by: OOMPAH-672

Reproduce the safe-restart recovery trap when the running service is revision A, the canonical CLI does not match A, and the clean pushed checkout is advanced to candidate revision B. scripts/canonical_cli_cutover.py tells the operator to run make install-cli, but installing from B makes the launcher B while service A remains live, so make graceful rejects the same mismatch and cannot stage the normal A-to-B cutover. Today recovery required temporarily publishing a tracked A checkout, installing its CLI, restoring the operator venv to B, deleting the temporary branch/worktree, then running make graceful. Implement a supported, bounded recovery that can pair the canonical launcher with the verified running revision without temporary remote refs, or make the normal cutover safely accept and repair this exact pre-cutover state. Update Makefile targets and docs/cli-install.md recovery instructions. Preserve exact build/instance checks, lifecycle ownership, atomic launcher activation, drain semantics, and fail-closed behavior for unknown revisions. Add deterministic tests covering A service + mismatched launcher + B checkout, the documented operator sequence, install/stage failure rollback, concurrent cutover locking, and proof that no live CLI/server mismatch is left. Acceptance: the documented Makefile-backed recovery reaches a healthy B/B pair from this state without force-restart, temporary remote branches, or manual tool-root surgery; focused tests and the complete Makefile gate pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

