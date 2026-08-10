---
id: OOMPAH-1000
type: bug
status: Merged
priority: 1
title: Bind direct-recovery terminal gate identity to the immutable audit revision
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-10T17:36:32.614914Z'
updated_at: '2026-08-10T18:39:32.447851Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.create_once:
  version: 1
  project_id: proj-14849f1b
  operation_kind: api_task_create
  creation_marker: o999-terminal-gate-audit-selected-sha-v1
  request_fingerprint: 277a198f28adbc26f867ebadc4659c02b081c3e20661b5b3f8d5bf088cd7fd2e
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-419e36e0f73d
    project_id: proj-14849f1b
    task_id: OOMPAH-1000
    target_state: Merged
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: dd9586d47ac8ece8e7c927ae055c2ed28127b1bd18cb4d87d5dfb284eebd1038
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: 'Exact implementation d8232d4f250fade0da5603f0ed31dfa043b0d258 is contained
      in protected merge 8eac2ae5097e84840d6b07fe965b37224c0f7960 via PR #800; combined
      exact head 017956bd637bfd3dd9124396fef394b439f47d6a passed the complete local
      Makefile gate and protected Python 3.11/3.12/3.13 CI, with independent adversarial
      approval.'
    created_at: '2026-08-10T18:39:24.808065+00:00'
    selected_ref: origin/OOMPAH-1000
    selected_sha: d8232d4f250fade0da5603f0ed31dfa043b0d258
    applied: false
  version: 1
  pending_chain: []
  attempt_history: []
---
## Summary

Triggered by: OOMPAH-999

Triggered by OOMPAH-999. Problem: a durable terminal-audit attempt was exactly bound to selected_ref and selected_sha 6418a935de7b4aab93a24af4756a54b344463513, but terminal quality-gate evidence recorded an empty head because identity resolution only consumed ordinary issue review/source metadata, which direct recovery tasks may not have. Scope: centralize terminal-gate identity resolution in oompah/orchestrator.py; preserve normal accepted-head authority and, only when it is absent, admit AuditorTargetContract.selected_sha from a freshly reloaded matching pending attempt whose project, task, audit attempt, fingerprint, and state all agree. Resolve branch identity from the same durable staging contract. Change oompah/auditor.py or oompah/terminal_audit.py only if the immutable target contract needs an explicit branch key. selected_sha is identity only and must never imply a passing gate. Tests: add regressions in tests/test_quality_gate.py and tests/test_terminal_audit_observability.py for an OOMPAH-999-shaped audit with no ordinary head; stale fingerprint/attempt, wrong task/project, conflicting head, invalid binding, and changed state must fail closed; OOMPAH-980/OOMPAH-988 review and deleted-branch behavior must remain unchanged; exact SHA without passing evidence must remain full_gate_required. Acceptance: terminal metrics, prompts, and gate lookup use the truthful immutable audit head, all mismatches fail closed, and focused plus complete protected gates pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-10 18:02
---
Implementation handoff: branch OOMPAH-1000 is pushed at b17cfe56e3782bd02d01204ab9377eefd2ea871b. The patch binds terminal quality-gate identity to a freshly reloaded exact live audit attempt only when ordinary accepted-head metadata is absent; all scope, state, fingerprint, binding, and attempt mismatches fail closed, and selected_sha alone never implies PASS. Verification: 332 focused quality-gate/terminal-observability tests passed; 28/28 direct-recovery and retained review/deleted-branch regression slice passed after final test fixture adjustment; terminal task-status mutation scan passed (20/20 allowlisted); paranoid secret scan and commit hooks passed. Awaiting independent parent review; task intentionally not submitted or terminalized.
---
author: oompah
created: 2026-08-10 18:13
---
Review correction pushed as d8232d4f250fade0da5603f0ed31dfa043b0d258. Terminal quality-gate fallback now verifies both the supplied Project.id and the freshly reloaded task project_id match the audit target project before deriving or looking up gate identity; both mismatch paths fail closed without a gate or branch-head lookup. Verification: 334 focused tests passed across tests/test_quality_gate.py and tests/test_terminal_audit_observability.py; targeted authority regressions 30 passed; terminal-audit mutation scan 20/20; git diff --check and secret scan passed. Branch OOMPAH-1000 is clean and exactly synchronized with origin. Task intentionally remains In Progress pending integration review.
---
author: oompah
created: 2026-08-10 18:20
---
Protected recovery candidate: PR #800 carries exact OOMPAH-1000 commit d8232d4f250fade0da5603f0ed31dfa043b0d258 in combined head 017956bd637bfd3dd9124396fef394b439f47d6a. Clean combined focused result: 426 passed; full Makefile gate, protected Python 3.11/3.12/3.13 CI, and independent adversarial review are running on that exact head.
---
<!-- COMMENTS:END -->
