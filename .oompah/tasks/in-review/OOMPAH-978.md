---
id: OOMPAH-978
type: bug
status: In Review
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
updated_at: '2026-08-09T23:27:45.144518Z'
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
<!-- COMMENTS:END -->
