---
id: TASK-473.3
title: Fix synchronous file reads on hot HTTP paths
status: Done
assignee: []
created_date: '2026-06-09 04:19'
updated_date: '2026-06-09 15:53'
labels:
  - performance
dependencies: []
parent_task_id: TASK-473
priority: high
ordinal: 201000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Found during benchmarking: the favicon route does fav.read_bytes() per request inside an async handler (templates are already cached, favicon is not). Cache or async-serve such static reads on hot paths.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Favicon and similar hot-path static assets are not re-read from disk per request on the event loop
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-09 15:32
---
Agent dispatched (profile: standard)
---

author: oompah
created: 2026-06-09 15:33
---
Focus: Duplicate Investigator
---

author: oompah
created: 2026-06-09 15:40
---
Agent failed: opencode serve exited with code -15. stderr: . Retrying in 10s (attempt #1)
---

author: oompah
created: 2026-06-09 15:40
---
Run #1 [attempt=1, profile=standard, role=standard -> Opencode/default]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 7m 22s
- Log: TASK-473.3__20260609T153333Z.jsonl
---

author: oompah
created: 2026-06-09 15:46
---
Agent dispatched (profile: default)
---

author: oompah
created: 2026-06-09 15:48
---
Understanding: No duplicate confirmed. TASK-473.2 (Move blocking calls out of server route handlers) is the closest sibling but it covers ALL blocking call sites broadly; TASK-473.3 is specifically about caching the favicon (and other static file reads) so read_bytes() doesn't block the event loop per-request. These are related but distinct issues within the same epic. Proceeding with the fix: find the favicon route in oompah/server.py and cache the bytes at startup.
---

author: oompah
created: 2026-06-09 15:50
---
Discovery: Found the issue in oompah/server.py lines 128-142. The favicon() async handler builds a Path object and calls fav.read_bytes() on every request — a synchronous disk read blocking the event loop. Templates already use a _template_cache dict. The fix: add _FAVICON_CACHE: bytes | None = _FAVICON_PATH.read_bytes() at module load time, so the handler returns cached bytes with zero disk I/O per request.
---

author: oompah
created: 2026-06-09 15:52
---
Implementation: Modified oompah/server.py to cache favicon bytes at module load time in _FAVICON_CACHE (bytes | None). The async favicon() handler now returns the cached bytes directly — zero disk I/O per request. Added _FAVICON_PATH and _FAVICON_CACHE module-level variables; handler checks _FAVICON_CACHE is None → 404, else returns cached Response. Added tests/test_server_favicon.py with 5 tests including one that verifies Path.read_bytes() is never called during request handling.
---

author: oompah
created: 2026-06-09 15:53
---
Verification: 5/5 new tests pass (test_server_favicon.py). Additional server tests (test_server_create_issue, test_server_issue_detail, test_server_label_api — 40 tests) all pass. Changes pushed to origin/epic-TASK-473.
---
<!-- COMMENTS:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Fixed synchronous disk read in hot favicon route. Added _FAVICON_CACHE module-level variable populated once at import time (same pattern as _template_cache). Handler now returns cached bytes with zero per-request I/O. 5 new tests in tests/test_server_favicon.py including a spy asserting read_bytes() is never called during request handling. All existing server tests pass.
<!-- SECTION:FINAL_SUMMARY:END -->
