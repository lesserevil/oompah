---
id: OOMPAH-251
type: task
status: Backlog
priority: null
title: Make Release Delivery candidate discovery bounded for Trickle-scale history
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-19T22:01:10.371010Z'
updated_at: '2026-07-19T22:01:10.371010Z'
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

