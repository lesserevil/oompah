---
id: OOMPAH-1087
type: task
status: In Review
priority: null
title: Prevent redundant WebSocket keepalive races during dashboard reconnects
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-11T13:38:34.915522Z'
updated_at: '2026-08-11T14:59:37.656421Z'
work_branch: OOMPAH-1087
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/822
review_number: '822'
review_head: 0cf8f1586ddf6b48bd2315dd0b53234e36fdc061
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
  base_branch: main
  base_sha: fe9599111d478b8221a2949c878fecb61d558760
  head_sha: 0cf8f1586ddf6b48bd2315dd0b53234e36fdc061
  submitted_at: '2026-08-11T14:43:59.726348+00:00'
  updated_at: '2026-08-11T14:43:59.726348+00:00'
oompah.work_branch: OOMPAH-1087
oompah.review_url: https://github.com/lesserevil/oompah/pull/822
oompah.review_number: '822'
oompah.target_branch: main
oompah.review_head: 0cf8f1586ddf6b48bd2315dd0b53234e36fdc061
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
author: oompah
created: 2026-08-11 13:55
---
Fresh independent exact-head review ACCEPTED 4d8c7b9a9fdda0e0119fe6ebbe6a0951c0631f71. Reviewer verified both embedded Uvicorn construction paths use the shared configuration, Uvicorn 0.41 accepts ws_ping_interval=None and disables only protocol keepalive, while application ping/pong, 30-second stale closure, bounded reconnect, sequence/full-refresh backfill, and client cleanup remain intact. Evidence: 99/99 focused WebSocket/dashboard/bootstrap tests plus 7/7 direct causal/recovery assertions; exact clean pushed branch, canonical trailer, diff and secret scans green. Protected CI on PR #822 remains the next boundary.
---
author: oompah
created: 2026-08-11 14:41
---
Direct-owner refresh: PR 822 was green at 4d8c7b9 but its computed merge still targeted stale main fe06a0ff. With OOMPAH-1086 now merged to main fe959911, moving this task back to In Progress, rebasing its clean exact fix onto latest main, and requiring a fresh exact gate/review before merge.
---
author: oompah
created: 2026-08-11 14:43
---
Rebased cleanly onto latest main fe9599111 after OOMPAH-1086 landed. Replacement exact head is 0cf8f1586ddf6b48bd2315dd0b53234e36fdc061, pushed with an exact force-with-lease against prior 4d8c7b9. Post-rebase focused WebSocket/dashboard lifecycle suite: 124 passed; terminal mutation scan 21/21; diff check clean. This replacement head requires fresh exact review and canonical branch gate before merge.
---
author: oompah
created: 2026-08-11 14:44
---
Rebased the WebSocket keepalive ownership fix onto latest main fe959911; exact head 0cf8f158 with 124 focused lifecycle tests green.
---
author: oompah
created: 2026-08-11 14:58
---
Branch quality gate passed for `0cf8f1586ddf6b48bd2315dd0b53234e36fdc061` using `make test` in 185.8s. Review creation may proceed.
---
<!-- COMMENTS:END -->
