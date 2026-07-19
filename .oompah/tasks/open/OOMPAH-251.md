---
id: OOMPAH-251
type: task
status: Open
priority: null
title: Make Release Delivery candidate discovery bounded for Trickle-scale history
parent: null
children: []
blocked_by:
- OOMPAH-250
labels: []
assignee: null
created_at: '2026-07-19T22:01:10.371010Z'
updated_at: '2026-07-19T22:06:40.707159Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Problem

After OOMPAH-250 correctly injects Trickle's project tracker, the live GET Release Delivery backlog for Trickle release/0.11 no longer completes within the UI/request timeout. Candidate discovery iterates all Merged records on the request path and can perform sequential work-branch rev-list calls, SCM PR commit API calls, per-item title reads, and tracker-only classification. With thousands of main commits and dozens of merged records this blocks the page instead of returning candidate rows.

Required implementation

- Make construction of the primary task/epic candidate list bounded and cacheable. It must not perform unbounded sequential SCM or subprocess operations per historical Merged item during a request.
- Establish a clear performance budget for the backlog endpoint and enforce per-operation timeouts; use a bounded concurrency/batch strategy or a durable per-project candidate index/cache.
- Build and return primary rows before optional diagnostics, title enrichment, and tracker-only classification. Those nonessential fields may be cached, deferred, or bounded, but must never block the primary list.
- Preserve correctness: candidate eligibility still requires Merged task/epic evidence and source commits reachable from default branch; release ancestry/ledger still control delivery status.
- Emit structured timing/logging sufficient to identify which discovery phase exceeds budget.

Tests

- Performance/API regression using a synthetic Trickle-scale fixture (thousands of source commits and dozens of Merged items, including deleted work branches and PR references) verifies the primary needs-delivery response completes within the documented service/UI timeout.
- Assert external SCM lookups and git subprocess calls are bounded rather than proportional to all historical items.
- Verify primary candidate rows are returned even when optional title/diagnostic enrichment is slow or fails.
- Regression test retains correct Not selected and delivered filtering for the returned rows.

Acceptance criteria

- The live Trickle release/0.11 Release Delivery dialog renders a non-empty, selectable candidate list without timing out.
- Optional unassociated-commit diagnostics cannot delay the primary backlog.
- make test passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-19 22:02
---
Requirement update from project owner: a long Trickle-scale discovery run is acceptable, provided the Release Delivery UI gives meaningful progress. This supersedes any implication that all discovery must complete synchronously within a short HTTP/UI timeout. Implement an observable asynchronous refresh model: (1) start or reuse one refresh job per project plus selected release branch, (2) retain and display the last completed candidate list while a refresh is active, (3) expose progress through the existing dashboard transport or a dedicated status endpoint with phase, completed/total counts where knowable, elapsed time, and actionable failure state, (4) render this status in the Release Delivery dialog with a determinate progress bar when a total is known and explicit phase text otherwise, and (5) allow retry after failure. Suggested phases: loading merged task metadata; resolving source commits/PR evidence; comparing release-branch ancestry; preparing rows; optional diagnostics. The primary list must not disappear or show an unexplained blank state while checks are running. Add dashboard and API tests for start, in-progress updates, successful completion, retained stale result, failure, and retry.
---
<!-- COMMENTS:END -->
