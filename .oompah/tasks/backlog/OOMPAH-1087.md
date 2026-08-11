---
id: OOMPAH-1087
type: task
status: Backlog
priority: null
title: Prevent redundant WebSocket keepalive races during dashboard reconnects
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-11T13:38:34.915522Z'
updated_at: '2026-08-11T13:38:34.915522Z'
work_branch: null
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
---
## Summary

Live deployed main fe06a0ff logged an uncaught websockets legacy protocol ERROR at 2026-08-11 13:35:40 UTC: keepalive_ping failed in ping -> write_frame -> drain with AssertionError waiter is None or waiter.cancelled. The dashboard had disconnected/reconnected immediately beforehand while large state refreshes were under load. OOMPAH-690 already implements application-level browser ping/pong, stale-socket closure, reconnect, and backfill, so Uvicorn/websockets protocol keepalive may be redundant and racing connection close/backpressure. Reproduce the server lifecycle with concurrent/buffered sends plus client disconnect/reconnect at the protocol keepalive boundary; determine whether to disable Uvicorn protocol pings when the application heartbeat owns liveness or repair close/send serialization. Do not merely suppress ERROR logs. Preserve proxy liveness detection, browser application pong/freshness, sequence/full-sync recovery, client isolation, and graceful shutdown. Apply the fix consistently to both Uvicorn construction paths in oompah/__main__.py and any Granian fallback semantics. Add tests asserting the configured keepalive ownership, reconnect under blocked send/close emits no protocol assertion, application heartbeat still detects stale sockets and backfills, and no duplicate reconnect/send owner. Run focused WebSocket lifecycle/liveness/fault-injection tests and the canonical exact branch gate. Acceptance: the live disconnect/reconnect shape cannot emit a keepalive assertion or leave a stale UI connection, and dashboard recovery remains automatic.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

