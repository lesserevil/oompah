---
id: OOMPAH-995
type: bug
status: In Progress
priority: 1
title: Move gate and workflow publication I/O outside project locks
parent: OOMPAH-992
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-10T10:52:35.641259Z'
updated_at: '2026-08-10T11:13:50.944856Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Refactor quality-gate result and workflow publication so tracker reads, Git head/dependency checks, state-branch generation, and diff work occur outside project and delivery-authority locks. Use external preflight followed by a constant-time in-memory generation/CAS finalization that rejects superseded results while preserving terminal-first, result-first, head-change, and dependency-change behavior. Add barrier-based concurrency tests proving publication I/O is lock-free and unrelated task creation and health/control requests remain responsive.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-10 11:13
---
Implemented and pushed exact branch head 853fa473ec258e9171a12d550891789b20906242. Quality-gate publication now performs tracker/task/dependency/project/Git-head preflight without project or standalone-delivery locks, then finalizes under project + authority fences using project-scoped managed-tracker and workflow revisions. Durable workflow state-branch generation and scoped Git-diff proof now run before publication locks; final publication compares the in-memory tracker epoch, terminal/workflow revisions, and SQLite lane authority. Liveness observation authority is released around external preflight and its policy epoch is revalidated so health/control requests remain responsive. Managed native and external tracker writes now advance an atomic project-scoped publication epoch. Barrier regressions prove terminal revocation and external task creation proceed during stalled quality tracker reads, and project control + health reads proceed during stalled workflow Git-diff preflight. Focused verification: 349 quality/workflow tests passed; 125 provenance/project/terminal-metadata tests passed; 203 native tracker/state-branch/protocol tests passed; py_compile and git diff --check passed; make terminal-audit-scan passed; make check-secrets and commit hooks passed. No full suite run, per assignment.
---
author: oompah
created: 2026-08-10 11:13
---
Submission attempted after push but the server rejected it with: submission Git authority rejected: origin/epic-OOMPAH-992 is not published. Implementation is complete and branch OOMPAH-995 is clean/up to date at 853fa473ec258e9171a12d550891789b20906242; parent integration must publish/restore the expected epic-OOMPAH-992 authority before resubmitting.
---
<!-- COMMENTS:END -->
