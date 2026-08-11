---
id: OOMPAH-1097
type: task
status: In Progress
priority: null
title: Keep HTTP available while auto-update drains retained workflow authority
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-11T17:34:07.685347Z'
updated_at: '2026-08-11T18:16:52.819215Z'
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
  creation_marker: 4b9b6ab4-7131-48c9-a1c0-97786475acff
  request_fingerprint: e0fd820824effc6879a1df6aeb0cedfec32714788765cc2af9af0df8e34a4e99
---
## Summary

Bug observed repeatedly on 2026-08-11, including 17:10:02-17:17:31 UTC: auto-update sets restart/stopping, Uvicorn immediately closes HTTP and WebSockets, then application cleanup safely waits minutes for active standalone quality-gate/workflow authority to drain. Health/state are unavailable and webhook forwarding loops on connection refused throughout the legitimate drain. Similar outages occurred around 15:17-15:20 and 15:45-15:47. Existing OOMPAH-974, OOMPAH-989, OOMPAH-1093, OOMPAH-1088, and OOMPAH-203 do not cover listener availability across a retained safe-stop. Implementation scope: two-phase Uvicorn and Granian restart lifecycle. First quiesce mutation/provider admission and drain retained workflow operations while HTTP health/state, WebSockets, and read-only observability remain available; stop webhook forwarders at the actual cutover boundary; only then close listener, exec/restart, and rebind. Preserve fail-closed mutation fencing and prevent new provider launches throughout drain. Relevant code: oompah/__main__.py restart supervisor ordering, orchestrator restart publication/cleanup, server lifespan, webhook forwarder lifecycle. Tests: deterministic active standalone-gate barrier triggers auto-update, proves health/state/WebSocket availability and no new dispatch while drain is retained, releases gate, proves orderly close/exec/rebind; cover Uvicorn and Granian plus webhook shutdown ordering. Acceptance: no connection-refused window longer than actual listener cutover, retained authority drains safely, replacement reports new build healthy, no duplicate effects.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-11 17:55
---
Implementation complete and pushed at exact head 172544459fd704612cefebe23d79e6aa8bdb0680 on branch OOMPAH-1097, rebased onto current origin/main. Added one idempotent listener-cutover coordinator shared by Uvicorn and Granian: restart now fences workflow/provider admission and unsafe HTTP mutations; keeps health, state, WebSocket, read-only HTTP, and forge ingress served while retained workflow/standalone authority drains fail-closed; stops webhook transports before closing the listener; then triggers Uvicorn should_exit or the Granian supervisor signal. Deterministic active-gate tests prove no early listener close, exact webhook/GitLab ordering, Uvicorn/Granian parity, read/mutation behavior, abnormal-exit behavior, and idempotent cleanup. Post-rebase evidence: 181 restart/webhook tests passed; 147 lifecycle/auto-update tests passed; 622 auth/webhook/WebSocket tests passed; 137 process/e2e tests passed; terminal status scan 21/21; py_compile and git show --check passed. Full gate deliberately not run per handoff. Awaiting independent exact-head review; task intentionally remains In Progress and is not submitted.
---
author: oompah
created: 2026-08-11 18:16
---
REJECT exact head 172544459fd704612cefebe23d79e6aa8bdb0680 against base b948150a808d80c331769fba8ae2a39e9a102a47. Concrete restart provider-fence defect: server.py:1090-1118 fences only HTTP middleware while intentionally retaining WebSockets. The retained /ws loop at server.py:5117-5149 continues accepting console_input, and _handle_console_input at server.py:5321-5341 creates/gets a ConsoleSession and awaits session.send without checking restart drain state or acquiring the orchestrator provider-admission fence. A direct exact-head probe with wants_restart=True and _stopping=True confirmed _restart_drain_blocks_mutation() was true while console_input still invoked session.send. This permits a new ACP provider turn after safe-stop authority has begun/finished, racing listener closure and process re-exec, violating the task acceptance requirement that no new provider launches occur throughout drain and undermining exact two-phase cutover. Retaining WebSocket observability is fine, but mutating WS message types must be rejected during restart drain or console provider authority must join the cutover drain/fence. Existing new tests cover connection retention only and miss this path. Other evidence: 317 focused restart/API/quiesce/webhook/WebSocket/console tests passed; 13 new/auto-update tests passed; terminal status scan passed 21/21; py_compile, diff-check, branch exactness clean. Branch left untouched.
---
<!-- COMMENTS:END -->
