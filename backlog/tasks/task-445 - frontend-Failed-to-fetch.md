---
id: TASK-445
title: '[frontend] Failed to fetch'
status: In Progress
assignee: []
created_date: '2026-06-04 12:42'
updated_date: '2026-06-04 17:59'
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
<!-- COMMENTS:END -->
