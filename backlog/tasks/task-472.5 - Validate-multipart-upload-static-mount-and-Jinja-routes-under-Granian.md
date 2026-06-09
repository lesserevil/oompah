---
id: TASK-472.5
title: 'Validate multipart upload, static mount, and Jinja routes under Granian'
status: In Progress
assignee: []
created_date: '2026-06-09 04:19'
updated_date: '2026-06-09 15:58'
labels:
  - 'needs:backend'
  - 'needs:test'
dependencies: []
parent_task_id: TASK-472
priority: high
ordinal: 194000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Exercise the non-JSON routes under granian: the 3 UploadFile/multipart attachment endpoints, the /static StaticFiles mount, and the Jinja/HTML routes (cache-busting headers). Confirm parity with uvicorn.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Multipart uploads succeed under granian
- [ ] #2 /static assets and HTML routes serve with correct headers
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-09 15:43
---
Agent dispatched (profile: standard)
---

author: oompah
created: 2026-06-09 15:53
---
UNDERSTANDING: Task is to write tests that exercise non-JSON routes under Granian ASGI server: (1) the 3 multipart/UploadFile attachment endpoints (list, upload, serve+delete), (2) the /static StaticFiles mount, and (3) Jinja/HTML routes with cache-busting headers. Goal is parity confirmation vs uvicorn.

APPROACH: Write tests/test_granian_parity.py that:
- Skip cleanly if granian is not installed (pytest.importorskip)
- Boot a real Granian server subprocess on a random port with oompah.server:app in ASGI mode
- Wait for server readiness via httpx polling
- Test HTML routes return 200 with correct Cache-Control/Pragma/Expires headers
- Test /static/favicon.svg returns with correct Content-Type
- Test multipart upload endpoint: Granian must parse multipart body correctly (503 = orchestrator absent = transport OK; 400/422 = Granian transport failure)
- Verify parity with TestClient results for each assertion
---

author: oompah
created: 2026-06-09 15:58
---
DISCOVERY: Key findings from codebase exploration:

1. Granian 2.7.5 is installed in the project venv (manually, not in pyproject.toml yet — TASK-472.1).
2. The --server granian flag and bootstrap.py are NOT committed yet (prototype exists at /tmp/granian_e2e/).
3. The non-JSON routes are: HTML/Jinja routes (/, /providers, /projects-manage, /foci, /reviews) via _html_response() with _NO_CACHE_HEADERS; /static/favicon.svg via StaticFiles mount; and 3 attachment endpoints (GET list, POST upload with UploadFile, GET serve, DELETE).
4. Granian must run in ASGI interface mode (not its default RSGI) for the FastAPI app.
5. Without orchestrator: attachment endpoints return 503 (orchestrator guard fires); static and HTML routes work fine (no orchestrator needed).
6. Parity confirmed: Granian and TestClient return identical status codes, headers, and bodies for all tested routes.
---

author: oompah
created: 2026-06-09 15:58
---
IMPLEMENTATION: Created tests/test_granian_parity.py with 44 tests organized in 3 classes:

1. TestHtmlRoutes (26 tests): Parametrized over 5 HTML routes. Verifies 200 status, Cache-Control: no-cache/no-store/must-revalidate, Pragma: no-cache, Expires: 0, text/html content-type, and exact body parity between Granian and TestClient.

2. TestStaticMount (5 tests): Verifies /static/favicon.svg returns 200 with image/svg+xml, non-empty SVG body, exact byte/content-type parity with TestClient, and 404 for missing assets.

3. TestMultipartAttachmentEndpoints (13 tests): Verifies Granian ASGI transport correctly parses multipart bodies (503 from orchestrator guard, not 400/422 from transport failure), MIME rejection parity, list/serve/delete endpoint reachability, path traversal handling, and JSON response content-type.

Module-scoped granian_base_url fixture starts Granian as subprocess in ASGI mode on a random port, polls for readiness, and tears down cleanly. Tests skip if granian is not installed.
---
<!-- COMMENTS:END -->
