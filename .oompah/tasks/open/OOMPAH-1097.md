---
id: OOMPAH-1097
type: task
status: Open
priority: null
title: Keep HTTP available while auto-update drains retained workflow authority
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-11T17:34:07.685347Z'
updated_at: '2026-08-11T17:34:49.425117Z'
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

