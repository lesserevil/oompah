---
id: TASK-445
title: '[frontend] Failed to fetch'
status: Done
assignee: []
created_date: '2026-06-04 12:42'
updated_date: '2026-06-04 18:05'
labels:
  - bug
dependencies: []
priority: low
ordinal: 81000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
TypeError: Failed to fetch
    at fetchIssues (http://100.64.0.9:8090/:2167:21)
    at updateIssue (http://100.64.0.9:8090/:2218:24)
    at async HTMLDivElement.<anonymous> (http://100.64.0.9:8090/:2817:7)
<!-- SECTION:DESCRIPTION:END -->

## Comments
<!-- COMMENTS:BEGIN -->
<!-- COMMENT:BEGIN -->
index: 3270fcde-26ef-4173-912f-5076f65f7fb1
author: oompah
created: 2026-06-04T18:00:00Z

Understanding: Investigated whether TASK-445 is a duplicate of TASK-444. Both are '[frontend] Failed to fetch' bugs, but they are different functions: TASK-444 covers `openDetailPanel`, while TASK-445 covers `fetchIssues` (called from `updateIssue`'s error-recovery catch block). Not a duplicate. Root cause: `fetchIssues()` has no try-catch around `fetch()`, so when the network is down it throws `TypeError: Failed to fetch` instead of returning null. The fix is to wrap the `fetch(url)` call in `fetchIssues` with a try-catch that returns null on network error.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: edb5308e-4092-42a5-9dc5-9304ff31ed03
author: oompah
created: 2026-06-04T18:05:24Z

Discovery: Not a duplicate of TASK-444. TASK-444 covers `openDetailPanel` (already being fixed). TASK-445 is a separate instance of the same missing-try-catch pattern in `fetchIssues`. The `fetchIssues()` function had no try-catch around `fetch(url)`, causing unhandled TypeError when called from `updateIssue`'s error-recovery path (lines 2229, 2241) while the network is still down.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 5ab34496-b256-41b2-96ef-7922c7fefcce
author: oompah
created: 2026-06-04T18:05:24Z

Implementation: Wrapped the `fetch(url)` call in `fetchIssues()` with try/catch that returns null on network error. This matches the existing null-on-error contract callers already handle via `if (data) renderBoard(data)`. Added regression tests in `tests/test_fetch_issues_network_error.py` (4 tests covering try-catch presence, null return, !res.ok check, and ordering).
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 7bb1ca05-e1ef-4df2-8b2c-caa9234949df
author: oompah
created: 2026-06-04T18:05:24Z

Verification: All 4 new tests pass. All related existing tests (openDetailPanel, dashboard_refresh, dashboard_dispatch_optimistic, server_edit_protection) also pass. Branch pushed to origin/TASK-445.
<!-- COMMENT:END -->
<!-- COMMENTS:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Fixed: wrapped fetch() in fetchIssues() with try-catch returning null on network error. Not a duplicate of TASK-444 (which covers openDetailPanel). Added regression tests in tests/test_fetch_issues_network_error.py.
<!-- SECTION:FINAL_SUMMARY:END -->
