---
id: OOMPAH-951
type: task
status: Open
priority: null
title: Align ACP auditor result tool schema with its advertised contract
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-09T10:46:27.644873Z'
updated_at: '2026-08-09T10:46:39.432518Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Triggered by OOMPAH-939 live terminal audit attempt audit-4827a2c0df9f. The ACP/MCP auditor catalog advertises the canonical top-level AUDITOR_RESULT_TOOL_SCHEMA (audit_id, target_state, evidence_fingerprint, verdict, message), but both MCP @tool builders in oompah/acp_tools.py register {result: dict}. Claude correctly called the advertised top-level contract repeatedly and the transport rejected every call with Input validation error: 'result' is a required property, leaving OOMPAH-939 In Validation after a 26-minute full gate. Scope: make every auditor transport expose the same canonical top-level input schema and continue accepting only server-validated target-bound fields; remove obsolete envelope ambiguity; add provider-shaped MCP catalog/schema and end-to-end submission tests for both project-aware builders plus regression coverage proving a top-level result reaches the coordinator exactly once. Work around audit-4827a2c0df9f after deployment or through the exact authenticated audit authority without weakening its verdict/gate requirements. Acceptance: advertised and enforced schemas are identical across auditor transports, a valid top-level submission is accepted, envelope/schema drift fails tests, and OOMPAH-939 resumes naturally.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

