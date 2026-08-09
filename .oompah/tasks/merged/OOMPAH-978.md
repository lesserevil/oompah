---
id: OOMPAH-978
type: bug
status: Merged
priority: 1
title: Stop project config updates from dirtying managed checkouts
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels:
- reliability
assignee: null
created_at: '2026-08-09T23:14:00.520291Z'
updated_at: '2026-08-09T23:54:41.245173Z'
work_branch: OOMPAH-978
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/787
review_number: '787'
review_head: a1f6ef58e7da26ba2cd5be8a1c470eab1bed7acd
merged_at: null
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: standalone
  task_branch: OOMPAH-978
  head_sha: a1f6ef58e7da26ba2cd5be8a1c470eab1bed7acd
  submitted_at: '2026-08-09T23:20:56.655835+00:00'
  updated_at: '2026-08-09T23:20:56.655835+00:00'
oompah.work_branch: OOMPAH-978
oompah.review_url: https://github.com/lesserevil/oompah/pull/787
oompah.review_number: '787'
oompah.target_branch: main
oompah.review_head: a1f6ef58e7da26ba2cd5be8a1c470eab1bed7acd
oompah.terminal_audit:
  queued_comment_posted: true
  oompah.terminal_audit_tracker_projections:
  - version: 1
    audit_id: audit-6b258e38a578
    project_id: proj-14849f1b
    task_id: OOMPAH-978
    digest: 88a039ed4ac5abd74531c6b00318396dd21ce35fa374f154c028516ce7d40c99
  - version: 1
    audit_id: audit-0425441df257
    project_id: proj-14849f1b
    task_id: OOMPAH-978
    digest: 88a039ed4ac5abd74531c6b00318396dd21ce35fa374f154c028516ce7d40c99
  oompah.terminal_override_records:
  - version: 1
    override_id: override-ce1ebaefb5a9
    project_id: proj-14849f1b
    task_id: OOMPAH-978
    target_state: Merged
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 88a039ed4ac5abd74531c6b00318396dd21ce35fa374f154c028516ce7d40c99
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: 'Protected combined PR #787 merged exact OOMPAH-978 head 409132582cb1c527ffa53efc174d3464289971a7
      into main as eb3ca86e56dbe87a078d81f97cfa6054b94a5ee6. Protected Python 3.11/3.12/3.13
      gates passed; implementation and independent final-review suites passed. The
      exact final build is deployed, the managed clone is clean, and webhook self-heal
      reports a sound fast-forward pull.'
    created_at: '2026-08-09T23:54:37.272718+00:00'
    selected_ref: a1f6ef58e7da26ba2cd5be8a1c470eab1bed7acd
    selected_sha: a1f6ef58e7da26ba2cd5be8a1c470eab1bed7acd
    applied: false
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-6b258e38a578
    project_id: proj-14849f1b
    task_id: OOMPAH-978
    target_state: Done
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 88a039ed4ac5abd74531c6b00318396dd21ce35fa374f154c028516ce7d40c99
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: In Review
    created_at: '2026-08-09T23:45:33.568120+00:00'
    selected_ref: a1f6ef58e7da26ba2cd5be8a1c470eab1bed7acd
    selected_sha: a1f6ef58e7da26ba2cd5be8a1c470eab1bed7acd
  - version: 1
    audit_id: audit-0425441df257
    project_id: proj-14849f1b
    task_id: OOMPAH-978
    target_state: Merged
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 88a039ed4ac5abd74531c6b00318396dd21ce35fa374f154c028516ce7d40c99
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: In Review
    created_at: '2026-08-09T23:45:33.568120+00:00'
    selected_ref: a1f6ef58e7da26ba2cd5be8a1c470eab1bed7acd
    selected_sha: a1f6ef58e7da26ba2cd5be8a1c470eab1bed7acd
  attempt_history: []
---
## Summary

Triggered by: OOMPAH-940

Bug: project create/update paths call tracker AGENTS.md installation directly against Project.repo_path. When the generated integration block changes, routine project configuration updates rewrite tracked AGENTS.md in the canonical managed clone. Later startup sync uses git pull --autostash, reapplies that implicit edit, leaves the checkout dirty, and blocks webhook fast-forward synchronization. Implementation scope: remove implicit AGENTS.md writes from project registration/configuration paths in oompah/server.py; keep bootstrap status/preview/apply as the explicit mutation workflow and preserve tracker configuration cache/lifecycle behavior. Update affected project CRUD tests and add regressions proving project create and project PATCH/config reload leave AGENTS.md byte-for-byte unchanged even when its managed block is stale, while POST /api/v1/projects/{id}/bootstrap/apply remains the only path that can apply and commit bootstrap changes. Required focused tests: project CRUD, agent instructions, and project bootstrap suites. Acceptance criteria: routine service/project configuration operations never dirty a clean managed checkout; explicit bootstrap apply behavior remains covered; all focused checks pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-09 23:20
---
Implemented systemic fix on exact pushed head a1f6ef58e7da26ba2cd5be8a1c470eab1bed7acd. Root cause: project create/PATCH implicitly rewrote tracked AGENTS.md in the canonical managed clone; later startup pull --autostash reapplied the edit, giving it a startup-time mtime and leaving webhook sync unsound. The lifecycle calls are removed; explicit bootstrap status/preview/apply remains intact and its invocation contract is asserted. Regression coverage initializes clean Git repos with stale managed blocks and proves create plus both tracker-kind PATCH directions preserve bytes and git cleanliness. Focused result: 196 passed (project CRUD, agent instructions, project bootstrap); make terminal-audit-scan passed 20/20.
---
author: oompah
created: 2026-08-09 23:21
---
Removed implicit AGENTS.md writes from project lifecycle APIs; clean-checkout and explicit-bootstrap regressions pass on a1f6ef58e.
---
author: oompah
created: 2026-08-09 23:22
---
Opened PR #787 for exact head a1f6ef58e7da26ba2cd5be8a1c470eab1bed7acd so protected checks can run while the queued workflow submission catches up.
---
author: oompah
created: 2026-08-09 23:24
---
Branch quality gate passed for `a1f6ef58e7da26ba2cd5be8a1c470eab1bed7acd` using `make test` in 162.2s. Review creation may proceed.
---
author: oompah
created: 2026-08-09 23:27
---
Addressed independent review blocker and superseded a1f6ef58e with exact pushed head 409132582cb1c527ffa53efc174d3464289971a7, stacked directly on OOMPAH-974 exact 0006c430f566da7138f2958ed948e15d371cdf6d. Explicit bootstrap status/preview/apply is now tracker-aware while defaulting to native for CLI compatibility; real GitHub tracker regressions prove status/preview report drift without mutation and apply renders the GitHub integration block. Combined-head focused result: 198 passed; terminal scan 20/20.
---
author: oompah
created: 2026-08-09 23:33
---
Independent exact-head review APPROVED 409132582cb1c527ffa53efc174d3464289971a7 with parent exactly OOMPAH-974 0006c430f. Reviewer verified no runtime AGENTS.md writer remains on project create/PATCH, explicit bootstrap status/preview/apply is tracker-aware for native and GitHub aliases, all public helper defaults preserve standalone CLI compatibility, and AST call-site scan found no incompatible callers. Independent combined review ran 353 focused tests; implementation run passed 198; terminal scan 20/20 and diff/trailer/origin cleanliness pass. PR #787 protected matrix is running; auto-merge remains off until parent PR #784 lands.
---
author: oompah
created: 2026-08-09 23:45
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
<!-- COMMENTS:END -->
