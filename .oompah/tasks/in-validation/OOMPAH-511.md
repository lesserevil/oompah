---
id: OOMPAH-511
type: epic
status: In Validation
priority: 1
title: Prevent managed task writes from bypassing state branches
parent: null
children:
- OOMPAH-512
- OOMPAH-513
- OOMPAH-514
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-28T15:16:09.831740Z'
updated_at: '2026-08-04T16:24:41.126726Z'
work_branch: epic-OOMPAH-511
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/562
review_number: '562'
merged_at: null
oompah.review_url: https://github.com/lesserevil/oompah/pull/562
oompah.review_number: '562'
oompah.work_branch: epic-OOMPAH-511
oompah.target_branch: main
oompah.terminal_audit:
  queued_comment_posted: true
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-dc2b7e9fa81f
    project_id: proj-14849f1b
    task_id: OOMPAH-511
    target_state: Archived
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: d46f59de6b7e98be6b90abb05ad71e10fedea7b02363822c30dd5c37750f1529
    attempts: []
    requested_by:
      version: 1
      identity: oompah
      source: auto_archive
    previous_state: Merged
    created_at: '2026-08-04T16:24:35.836414+00:00'
  attempt_history: []
---
## Summary

Problem

A managed Oompah project can be configured to keep native Markdown task state on a dedicated Git state branch, yet legacy/global tracker consumers still construct a writable OompahMarkdownTracker from the server process working directory. When background maintenance or another unscoped consumer uses that tracker, task and epic updates are committed directly to the code checkout and can be pushed to the default branch, bypassing the project's designated state branch.

Scope

Make project-scoped tracker resolution mandatory for managed-project writes, prevent an unscoped legacy tracker from mutating a registered state-branch project, and add end-to-end protection proving maintenance and server-side consumers cannot change the code branch. Preserve standalone/single-repository compatibility where no managed project store is configured. Coordinate with, but do not duplicate, OOMPAH-492's targeted worker-exit and epic-rebase test isolation.

Relevant code includes oompah/orchestrator.py, oompah/server.py, oompah/oompah_md_tracker.py, background maintenance consumers, and tracker-oriented tests. All configuration remains in .env; no WORKFLOW.md tuning.

Acceptance criteria

All native task writes for a state-branch-enabled managed project resolve through that project's configured tracker; an unscoped/default-branch write attempt fails before modifying Git; background maintenance and server helper paths cannot fall back to the process checkout; standalone compatibility is retained; focused tests and make test pass; and ordinary main/release histories receive no task metadata commits.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-28 15:17
---
Claimed for this manual implementation session. Work will be completed sequentially in an isolated epic-OOMPAH-511 worktree; OOMPAH-492 remains with its existing worker because its targeted test isolation is complementary, not duplicated.
---
author: oompah
created: 2026-07-28 15:42
---
Implementation complete and pushed at 6533e235e. All three child tasks are Done and the complete epic branch is ready for review in https://github.com/lesserevil/oompah/pull/562. Validation: 12,402 tests passed, 39 skipped; secret scan passed; worktree is clean and synchronized with origin.
---
author: oompah
created: 2026-07-28 15:47
---
GitHub CI is green on Python 3.11, 3.12, and 3.13 for PR #562. The epic has no remaining implementation or test blocker; it is awaiting review/merge.
---
author: oompah
created: 2026-07-28 16:23
---
YOLO: merged PR #562.
---
author: oompah
created: 2026-08-04 16:24
---
Queued Archived audit: Aged Merged auto-archive (closed 7 days ago). An auditor will review before the task is retired.
---
<!-- COMMENTS:END -->
