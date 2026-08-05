---
id: OOMPAH-827
type: bug
status: Open
priority: 2
title: Use one authoritative work-kind classifier across agent observability surfaces
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-05T13:08:50.686371Z'
updated_at: '2026-08-05T13:08:55.157343Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Triggered by: OOMPAH-817

Live reproduction during OOMPAH-817 terminal audit on deployed main c14ca03f59078e6df06871488cf78f04477acb11: /api/v1/state correctly reported the active RunningEntry as work_kind=audit with is_auditor=true, audit_id, and audit_attempt_id, while /api/v1/agents/OOMPAH-817/activity deterministically returned work_kind=implementation with profile=auditor. The mismatch persisted after PASS while the retiring provider entry was intentionally retained, then disappeared with the entry; it was not stale cache data. Root cause: Orchestrator.get_snapshot classifies audit before duplicate_screening before implementation, but api_agent_activity and AGENT_DISPATCHED classify only duplicate_screening versus implementation and ignore entry.is_auditor. No existing task covers this exact mismatch; OOMPAH-475/484/533/571 cover adjacent dispatch, safe audit summary, duplicate-screening work kind, and auditor lifetime. Implementation scope: centralize one RunningEntry work-kind classifier with precedence audit, duplicate_screening, implementation; use it for state snapshots, activity responses, and dispatch/WebSocket event payloads; add safe additive is_auditor, audit_id, audit_attempt_id, and retirement state fields to activity; preserve existing duplicate-screening and ordinary implementation behavior and redaction. Required tests: active auditor, post-PASS-but-retiring auditor, duplicate screening, ordinary implementation, and no-live-run responses; assert state/activity/dispatch event agree for the same run_id and that profile name alone never determines work kind. Acceptance: every live observability surface reports the same authoritative work kind and audit identity for a run, without exposing prompts, credentials, hidden metadata, or untrusted output; focused API/WebSocket tests and make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

