---
id: TASK-428
title: '[frontend] Uncaught ReferenceError: toggleHideMerged is not defined'
status: Merged
assignee: []
created_date: '2026-06-03 04:23'
updated_date: '2026-06-03 06:01'
labels:
- bug
dependencies: []
priority: low
ordinal: 63000
oompah.task_costs:
  total_input_tokens: 97
  total_output_tokens: 40249
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 97
      output_tokens: 40249
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 97
    output_tokens: 40249
    cost_usd: 0.0
    recorded_at: '2026-06-03T05:51:05.431297+00:00'
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
ReferenceError: toggleHideMerged is not defined
    at HTMLInputElement.onchange (http://100.64.0.9:8090/:1436:121)
<!-- SECTION:DESCRIPTION:END -->

## Comments
<!-- COMMENTS:BEGIN -->
<!-- COMMENT:BEGIN -->
index: 1
author: oompah
created: 2026-06-03 05:34

Agent dispatched (profile: default)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 2
author: oompah
created: 2026-06-03 05:34

Focus: Duplicate Investigator
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 3
author: oompah
created: 2026-06-03 05:45

Understanding: Error 'toggleHideMerged is not defined' at line 1436 of the served dashboard page. The function IS currently defined at line 2031 of dashboard.html. No duplicate found in backlog search. Root cause investigation: the function was added in commit ded2ea9 (May 7). The error was captured at 04:23 UTC today. Possible causes: (a) server was running stale cached template before auto-update triggered, (b) browser cached old page version. Investigating cache-control headers and template serving to determine if there is a reproducible bug or if it was transient.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 4
author: oompah
created: 2026-06-03 05:50

Discovery: Not a duplicate. Root cause identified: HTML page routes (/, /providers, /foci, /reviews, /projects-manage) return no Cache-Control headers. Without these, browsers may use heuristic caching and serve a stale version of dashboard.html from before May 7 (when toggleHideMerged was added). Also, the auto-update only triggers when the orchestrator is IDLE (no running agents), so the server may serve old HTML for hours during busy periods. Fix: add Cache-Control: no-cache headers to all HTML page responses so browsers always fetch fresh content from the server.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 5
author: oompah
created: 2026-06-03 05:51

Agent completed successfully in 1027s (40346 tokens)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 6
author: oompah
created: 2026-06-03 05:51

Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 194, Tool calls: 130
- Tokens: 97 in / 40.2K out [40.3K total]
- Cost: $0.0000
- Exit: normal, Duration: 17m 7s
- Log: TASK-428__20260603T053405Z.jsonl
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 7
author: oompah
created: 2026-06-03 05:55

Implementation: Added _html_response(name) helper in server.py that wraps _load_template() with Cache-Control: no-cache, no-store, must-revalidate + Pragma: no-cache + Expires: 0 headers. Updated all 5 HTML page routes (/, /providers, /projects-manage, /foci, /reviews) to use this helper. Added tests/test_dashboard_no_cache.py with 17 tests covering: helper unit tests, per-route cache header assertions for all HTML pages, and regression tests that toggleHideMerged is defined in the served HTML. All 57 related tests pass.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 8
author: oompah
created: 2026-06-03 06:00

Verification: All 17 new tests pass. All 168 server tests pass. All 39 hide_merged tests pass. Committed c583cbf and pushed to TASK-428 branch. Completion: Not a duplicate. Fixed missing Cache-Control headers on HTML page routes so browsers never cache stale dashboard HTML. The toggleHideMerged ReferenceError cannot recur from browser-cached stale pages.
<!-- COMMENT:END -->
<!-- COMMENTS:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
No duplicate found. Root cause: HTML page routes returned no Cache-Control headers, allowing browsers to serve stale cached copies that predated the toggleHideMerged function (added May 7). Fixed by adding Cache-Control: no-cache, no-store, must-revalidate + Pragma: no-cache + Expires: 0 headers to all HTML page routes via a new _html_response() helper in server.py. Added 17 regression tests in tests/test_dashboard_no_cache.py.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Not a duplicate. Root cause: HTML page routes (/, /providers, /projects-manage, /foci, /reviews) had no Cache-Control headers, so browsers could serve stale cached copies of dashboard.html from before toggleHideMerged was added (May 7). Fixed by adding Cache-Control: no-cache, no-store, must-revalidate headers via a new _html_response() helper in server.py. Added 17 regression tests in tests/test_dashboard_no_cache.py verifying cache headers on all HTML routes and that toggleHideMerged is present in the served dashboard. All 168 server tests pass.
<!-- SECTION:FINAL_SUMMARY:END -->
