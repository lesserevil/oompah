---
id: OOMPAH-933
type: task
status: Done
priority: null
title: Make protected-main CI reproduce the supported quality gate
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-09T06:09:37.822614Z'
updated_at: '2026-08-09T20:16:47.474317Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-c3d08001f353
    project_id: proj-14849f1b
    task_id: OOMPAH-933
    target_state: Done
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 94ecad58d4b6319c05822dd305eb6602a11c510c10d319c08ae3b4f000919ed0
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: 'Protected PR #749 squash-integrated the OOMPAH-933 hosted-CI contract
      into main at d6b3018016bfa2036a010cce7ecec9ac13924a5a. All required hosted Python
      3.11/3.12/3.13 checks and the exact complete Makefile gate passed. Owner terminalization
      is required because delivery used the shared epic branch.'
    created_at: '2026-08-09T06:59:26.021950+00:00'
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-933
    target_state: Done
    evidence_fingerprint: 94ecad58d4b6319c05822dd305eb6602a11c510c10d319c08ae3b4f000919ed0
    audit_ids: []
    kind: override
    applied: true
    retired_at: '2026-08-09T06:59:34.266699+00:00'
  oompah.terminal_audit_result_intents: []
  oompah.terminal_provenance_suppression:
    version: 1
    suppressed: true
    authority_generation: 0
    reason: Project owner confirms OOMPAH-933 is a completed historical/provenance-only
      legacy record; this is not a landing claim.
    marked_at: '2026-08-09T20:16:45.614307+00:00'
    updated_at: '2026-08-09T20:16:45.614307+00:00'
    history:
    - kind: mark
      actor:
        version: 1
        identity: oompah-cli
        source: api
      reason: Project owner confirms OOMPAH-933 is a completed historical/provenance-only
        legacy record; this is not a landing claim.
      recorded_at: '2026-08-09T20:16:45.614307+00:00'
      authority_generation: 0
    actor:
      version: 1
      identity: oompah-cli
      source: api
  version: 1
  pending_chain: []
  attempt_history: []
---
## Summary

Problem: required GitHub-hosted CI runs pytest directly without provisioning bubblewrap, a real project .venv, or Git commit identity. PR #749 therefore fails on all supported Python versions even though the exact Makefile gate passes locally: sandbox tests fail closed because bwrap is absent, nested run-tests rejects the missing .venv interpreter, and temporary Git commits lack identity. This makes protected main impossible to update. Scope: update .github/workflows/ci.yml to provision and smoke-test the OS sandbox, create the project test environment through Makefile targets, configure the canonical bot Git identity, and run the supported make test gate. Add static regression coverage for the hosted CI contract. Acceptance: focused workflow-contract tests pass; the exact local full gate passes; PR #749's required Python 3.11/3.12/3.13 checks pass without bypassing branch protection.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-09 06:14
---
Root cause confirmed from PR #749: hosted CI ran raw pytest without bubblewrap namespace support, a project .venv, or Git commit identity. Implemented the protected-CI contract fix on epic-OOMPAH-763: provision and smoke-test both required bwrap namespace shapes, configure canonical bot identity, create the matrix-specific .venv through make test-setup, and run make test. Added static workflow regression coverage. Focused sandbox/quality/workflow tests: 248 passed. Preparing the exact gate and protected PR checks now.
---
author: oompah
created: 2026-08-09 06:59
---
Delivered through protected PR #749 and squash-merged to main at d6b3018016bfa2036a010cce7ecec9ac13924a5a. Required GitHub-hosted Python 3.11/3.12/3.13 checks all passed. The exact merged tree also passed the complete Makefile gate: 18,880 passed, 7 skipped, 2 xfailed.
---
author: oompah
created: 2026-08-09 06:59
---
Override by oompah-cli: terminal transition to Done applied by project owner.

Reason: Protected PR #749 squash-integrated the OOMPAH-933 hosted-CI contract into main at d6b3018016bfa2036a010cce7ecec9ac13924a5a. All required hosted Python 3.11/3.12/3.13 checks and the exact complete Makefile gate passed. Owner terminalization is required because delivery used the shared epic branch.
---
<!-- COMMENTS:END -->
