---
id: OOMPAH-1087
type: task
status: Ready to Integrate
priority: null
title: Prevent redundant WebSocket keepalive races during dashboard reconnects
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-11T13:38:34.915522Z'
updated_at: '2026-08-11T13:51:43.046940Z'
work_branch: OOMPAH-1087
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.create_once:
  version: 1
  project_id: proj-14849f1b
  operation_kind: api_task_create
  creation_marker: 26ecd924-6fee-4fc9-9b64-dcf37334f4d8
  request_fingerprint: a4c85ef17eaf3089604c59256d01d1ebab7be8ce232c89a37ae0046f73c9a3c1
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: standalone
  task_branch: OOMPAH-1087
  head_sha: 4d8c7b9a9fdda0e0119fe6ebbe6a0951c0631f71
  submitted_at: '2026-08-11T13:45:24.216406+00:00'
  updated_at: '2026-08-11T13:45:24.216406+00:00'
oompah.work_branch: OOMPAH-1087
---
## Summary

Live deployed main fe06a0ff logged an uncaught websockets legacy protocol ERROR at 2026-08-11 13:35:40 UTC: keepalive_ping failed in ping -> write_frame -> drain with AssertionError waiter is None or waiter.cancelled. The dashboard had disconnected/reconnected immediately beforehand while large state refreshes were under load. OOMPAH-690 already implements application-level browser ping/pong, stale-socket closure, reconnect, and backfill, so Uvicorn/websockets protocol keepalive may be redundant and racing connection close/backpressure. Reproduce the server lifecycle with concurrent/buffered sends plus client disconnect/reconnect at the protocol keepalive boundary; determine whether to disable Uvicorn protocol pings when the application heartbeat owns liveness or repair close/send serialization. Do not merely suppress ERROR logs. Preserve proxy liveness detection, browser application pong/freshness, sequence/full-sync recovery, client isolation, and graceful shutdown. Apply the fix consistently to both Uvicorn construction paths in oompah/__main__.py and any Granian fallback semantics. Add tests asserting the configured keepalive ownership, reconnect under blocked send/close emits no protocol assertion, application heartbeat still detects stale sockets and backfills, and no duplicate reconnect/send owner. Run focused WebSocket lifecycle/liveness/fault-injection tests and the canonical exact branch gate. Acceptance: the live disconnect/reconnect shape cannot emit a keepalive assertion or leave a stale UI connection, and dashboard recovery remains automatic.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-11 13:45
---
Reproduced the ownership conflict from the live 13:35:40 UTC keepalive_ping assertion: Uvicorn defaulted to a second protocol ping owner even though OOMPAH-690 dashboard application ping/pong already owns freshness, reconnect, and full-state backfill. Exact head 4d8c7b9a9 disables Uvicorn protocol pings through one shared config helper used by both default and Granian-fallback startup paths; transport WebSockets remain enabled. Focused dashboard liveness/WebSocket lifecycle/fault-injection/bootstrap coverage passed 99/99, Ruff (excluding one pre-existing unrelated F401), py_compile, diff check, commit hooks, and paranoid secret scan are green.
---
author: oompah
created: 2026-08-11 13:45
---
Made the dashboard application heartbeat the sole WebSocket liveness owner in both embedded Uvicorn paths, eliminating redundant protocol keepalive close/backpressure assertions while preserving reconnect and full-sync recovery.
---
author: oompah
created: 2026-08-11 13:51
---
Branch quality gate passed for `4d8c7b9a9fdda0e0119fe6ebbe6a0951c0631f71` using `make test` in 176.9s. Review creation may proceed.
---
<!-- COMMENTS:END -->
