---
id: OOMPAH-673
type: bug
status: Open
priority: 2
title: Make canonical CLI mismatch recovery unambiguous across upgrades
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-01T02:34:24.348580Z'
updated_at: '2026-08-01T02:34:40.134127Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 6c063c0ee4af6e852f42b593bd42f90fa12c1aac379cb9da31e2685cd7dca129
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 4a8430de-54d5-4d51-8855-a7772bb44942
  claim_owner: c9040198-12fd-44df-a501-638d565273c9
  claimed_at: '2026-08-01T02:34:33.510149+00:00'
  claim_expires_at: '2026-08-01T03:04:33.510149+00:00'
  retry_count: 0
  retry_after: null
oompah.agent_run_id: c07d8fba-3989-414e-8dc4-8c25fd3deb7a
---
## Summary

Triggered by: OOMPAH-672

Reproduce the safe-restart recovery trap when the running service is revision A, the canonical CLI does not match A, and the clean pushed checkout is advanced to candidate revision B. scripts/canonical_cli_cutover.py tells the operator to run make install-cli, but installing from B makes the launcher B while service A remains live, so make graceful rejects the same mismatch and cannot stage the normal A-to-B cutover. Today recovery required temporarily publishing a tracked A checkout, installing its CLI, restoring the operator venv to B, deleting the temporary branch/worktree, then running make graceful. Implement a supported, bounded recovery that can pair the canonical launcher with the verified running revision without temporary remote refs, or make the normal cutover safely accept and repair this exact pre-cutover state. Update Makefile targets and docs/cli-install.md recovery instructions. Preserve exact build/instance checks, lifecycle ownership, atomic launcher activation, drain semantics, and fail-closed behavior for unknown revisions. Add deterministic tests covering A service + mismatched launcher + B checkout, the documented operator sequence, install/stage failure rollback, concurrent cutover locking, and proof that no live CLI/server mismatch is left. Acceptance: the documented Makefile-backed recovery reaches a healthy B/B pair from this state without force-restart, temporary remote branches, or manual tool-root surgery; focused tests and the complete Makefile gate pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-01 02:34
---
Accepted follow-up from the OOMPAH-672 production cutover; ready for normal bug dispatch.
---
author: oompah
created: 2026-08-01 02:34
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-01 02:34
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
