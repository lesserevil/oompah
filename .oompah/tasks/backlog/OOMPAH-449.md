---
id: OOMPAH-449
type: task
status: Backlog
priority: null
title: Do not merge a newly updated PR before its CI checks register
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-26T04:35:24.362802Z'
updated_at: '2026-07-26T04:35:24.362802Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Triggered by PR #555 / OOMPAH-447.

Problem
At 2026-07-26 04:26:36-04:26:37 UTC, PR #555 received head ed815c908 and a synchronize webhook. Oompah queried combined status and check-runs at 04:26:39; both APIs returned successfully but the new workflow run had not registered yet. The workflow was created at 04:26:40 and jobs started at 04:26:42, while YOLO merged the PR at 04:26:43. GitHub logs confirm the replacement matrix did not finish until 04:32:58. GitHubProvider._fetch_ci_status_and_warnings currently returns passed when both APIs report zero checks, and the YOLO gate accepts passed/empty, creating a post-push race that bypasses CI.

Implementation
Make an empty check set fail closed for a recently created or synchronized PR head when the repository/PR is known to use CI. Preserve legitimate YOLO merging for repositories with no CI configured. Use authoritative head-SHA and review/update timing or a bounded observation state/grace period so a new SHA must either acquire checks and reach passed, or be positively classified as no-CI. Invalidate any prior-head CI verdict on synchronize. Relevant code: oompah/scm.py GitHubProvider._fetch_ci_status_and_warnings and list_open_reviews, oompah/orchestrator.py YOLO merge gate, webhook/cache refresh paths.

Tests
Add a regression sequence for old SHA failed -> synchronize to new SHA -> successful empty status/check-runs response -> checks later pending -> passed. Assert no merge/enqueue occurs during the empty registration window and merge becomes eligible only after the new SHA passes. Add a true no-CI repository case that remains mergeable and a stale prior-SHA verdict case. Run make test.

Acceptance Criteria
- A PR head update can never inherit or synthesize a passed CI verdict before checks for that exact SHA register.
- YOLO does not merge or enqueue during the post-synchronize empty-check race.
- Once required checks for the current SHA pass, normal YOLO delivery resumes.
- Repositories positively known to have no CI retain their current automatic merge behavior.
- Tests reproduce the PR #555 timestamp ordering and make test passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

