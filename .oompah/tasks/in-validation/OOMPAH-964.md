---
id: OOMPAH-964
type: bug
status: In Validation
priority: 1
title: Ignore PR-backed issue comments in GitHub issue intake
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels:
- github-intake
- needs:backend
assignee: null
created_at: '2026-08-09T16:09:40.311061Z'
updated_at: '2026-08-09T17:16:40.395608Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.terminal_audit:
  queued_comment_posted: true
  oompah.terminal_audit_tracker_projections:
  - version: 1
    audit_id: audit-3b82473e5c6a
    project_id: proj-14849f1b
    task_id: OOMPAH-964
    digest: 5f317aea7f8bfeec2d33d305f88480668d0a5d1039eaa7e29d86ced8e185da6a
  - version: 1
    audit_id: audit-2ed0e89f0435
    project_id: proj-14849f1b
    task_id: OOMPAH-964
    digest: 5f317aea7f8bfeec2d33d305f88480668d0a5d1039eaa7e29d86ced8e185da6a
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-3b82473e5c6a
    project_id: proj-14849f1b
    task_id: OOMPAH-964
    target_state: Done
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 5f317aea7f8bfeec2d33d305f88480668d0a5d1039eaa7e29d86ced8e185da6a
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: Open
    created_at: '2026-08-09T17:16:34.821342+00:00'
    selected_ref: origin/OOMPAH-964
    selected_sha: 21861cac88967f1b7b1fb171c8bb78ded3fd346c
  - version: 1
    audit_id: audit-2ed0e89f0435
    project_id: proj-14849f1b
    task_id: OOMPAH-964
    target_state: Merged
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 5f317aea7f8bfeec2d33d305f88480668d0a5d1039eaa7e29d86ced8e185da6a
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: Open
    created_at: '2026-08-09T17:16:34.821342+00:00'
    selected_ref: origin/OOMPAH-964
    selected_sha: 21861cac88967f1b7b1fb171c8bb78ded3fd346c
  attempt_history: []
---
## Summary

Triggered by: OOMPAH-963

GitHub sends issue_comment webhooks for both issues and pull requests. The 2026-08-09 issue_comment.created deliveries for merged PR #768 were routed through native GitHub issue intake and created erroneous Proposed task OOMPAH-963, even though pull_request events, issues events with an issue.pull_request marker, and GitHub issues-list polling already exclude PRs. Implement defense-in-depth so PR-backed issue_comment payloads can never be normalized or imported as native work. Scope: update oompah/webhooks.py and/or oompah/github_intake_bridge.py at the issue-comment parsing/intake boundary; preserve pull-request review lifecycle handling and ordinary GitHub issue comment synchronization. Add regression coverage in tests/test_webhooks.py and tests/test_github_intake_bridge.py for an issue_comment.created payload whose issue object includes pull_request, proving it creates no native Proposed task and imports no comment, including when a lower-level intake helper is invoked defensively. Keep ordinary issue_comment.created/edited behavior unchanged. Acceptance criteria: (1) PR-backed issue_comment webhooks are ignored by native issue intake without creating or mutating native tasks; (2) PR webhook review handling remains unchanged; (3) genuine issue comments continue to import; (4) regression tests reproduce the PR #768/OOMPAH-963 failure shape and pass; (5) focused webhook and GitHub-intake test modules pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-09 16:20
---
Project owner promotes the confirmed PR-backed issue_comment intake regression for direct implementation.
---
author: oompah
created: 2026-08-09 16:26
---
Branch quality gate blocked review creation.

Branch: `OOMPAH-964`
Target: `main`
Head: `unknown`
Command: `make test`
Result: `infrastructure_error`
Process: ended without subprocess exit evidence

Infrastructure action required: repair or replace the operator-owned quality-gate runtime. No candidate CI-fix status was applied because the candidate command did not run.

Output tail:
```text
Candidate CI was not run because the submitted review branch tip is unavailable in the managed repository.
```
---
author: oompah
created: 2026-08-09 16:27
---
Implemented defense-in-depth rejection of PR-backed GitHub issue_comment events at both webhook parsing and native-intake boundaries. Genuine issue comments remain covered and the full focused modules pass (265 tests), along with terminal-audit, secret, and diff checks. Pushed exact head fe2cb2d612c82d71e2637254fd79c30db5124377 and opened PR #773; hosted CI run 31323802373 is in progress.
---
author: oompah
created: 2026-08-09 16:35
---
Addressed independent-review blocker: both PR-comment guards now require a truthy pull_request marker, preserving genuine issue_comment payloads with pull_request: null. Added explicit parser and direct-intake nullable-marker regressions. Exact head 5693a9786509d31446ae8f5232caa8fef7be7d1d is pushed to PR #773; hosted run 31324161414 queued. Validation: 416 tests across webhook/intake/server/promotion modules passed; nullable regressions passed 20 repeated process runs; terminal-audit, secret, undefined-name, and diff checks passed.
---
author: oompah
created: 2026-08-09 16:46
---
Second independent review found the final falsey non-null edge: an empty pull_request object must still be PR-backed. Corrected exact head 21861cac8 now rejects every non-null marker at both parser and native-intake boundaries while missing/null markers remain genuine issue comments. Added empty-object regressions; 418 webhook/intake/approval/server tests plus terminal mutation, secret, critical lint, and diff checks pass. Final hosted matrix and independent re-review are running.
---
author: oompah
created: 2026-08-09 17:16
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
<!-- COMMENTS:END -->
