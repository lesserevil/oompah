---
id: OOMPAH-490
type: epic
status: Merged
priority: 1
title: Prune redundant tests and isolate the suite from live infrastructure
parent: null
children:
- OOMPAH-491
- OOMPAH-492
- OOMPAH-493
- OOMPAH-494
- OOMPAH-495
- OOMPAH-496
- OOMPAH-497
- OOMPAH-498
- OOMPAH-499
- OOMPAH-500
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-28T13:51:11.052512Z'
updated_at: '2026-07-28T17:11:24.362629Z'
work_branch: epic-OOMPAH-490
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/563
review_number: '563'
merged_at: null
oompah.review_url: https://github.com/lesserevil/oompah/pull/563
oompah.review_number: '563'
oompah.work_branch: epic-OOMPAH-490
oompah.target_branch: main
---
## Summary

Objective

Reduce the pytest suite's maintenance burden and runtime without weakening behavior coverage, and make the suite safe to run from a developer checkout. The July 28 audit found 282 test modules, about 201,700 test lines, and 12,347 collected cases. A timed run reached 5,954 passing tests in 309.78 seconds before it was stopped because improperly isolated tests invoked the checkout's real `git push origin HEAD:main`. The audit also found stale design-only tests, repeated removed-UI assertions, repeated Granian process startups, overlapping release-delivery page suites, exact duplicate assertions, and test definitions hidden by duplicate Python names.

Scope and constraints

First add a suite-wide barrier against outbound Git remotes. Then isolate known slow tests, consolidate subprocess scenarios, remove tests that exercise only test-authored constants or fixtures, and merge duplicate static UI contracts. Preserve separate backend/forge adapter contracts, MCP route policy cases that use different route data, and still-reachable release compatibility behavior. Do not change production behavior merely to make pruning easier. A child may remove a test only after identifying the surviving test that protects the same behavior.

Child task standard

Each child description identifies the files and retained contracts. Use focused pytest commands while developing and run `make test` when the safety and isolation prerequisites are present. Record before/after collected-case counts for the files changed. Any deliberately retained duplication must be explained in a short code comment only when the reason is not obvious from the test name.

Acceptance criteria

All children are complete; no test can contact or push to an HTTP(S), SSH, or git-protocol remote; local temporary bare-remotes still work; the full `make test` suite passes from a clean checkout; redundant cases are measurably reduced; and unique tracker, provider, compatibility, lifecycle, and failure-path coverage remains intact.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-28 17:04
---
YOLO: merged PR #563.
---
<!-- COMMENTS:END -->
