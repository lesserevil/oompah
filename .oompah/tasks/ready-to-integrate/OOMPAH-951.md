---
id: OOMPAH-951
type: task
status: Ready to Integrate
priority: 0
title: Align ACP auditor result tool schema with its advertised contract
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-09T10:46:27.644873Z'
updated_at: '2026-08-09T11:51:33.955832Z'
work_branch: OOMPAH-951
target_branch: null
review_url: https://github.com/lesserevil/oompah/pull/759
review_number: '759'
review_head: null
merged_at: null
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: standalone
  task_branch: OOMPAH-951
  head_sha: 5defaaa424e9a1303ee292ad523369e53e1b08e1
  submitted_at: '2026-08-09T10:52:11.207142+00:00'
  updated_at: '2026-08-09T10:52:11.207142+00:00'
oompah.work_branch: OOMPAH-951
oompah.review_url: https://github.com/lesserevil/oompah/pull/759
oompah.review_number: '759'
---
## Summary

Triggered by OOMPAH-939 live terminal audit attempt audit-4827a2c0df9f. The ACP/MCP auditor catalog advertises the canonical top-level AUDITOR_RESULT_TOOL_SCHEMA (audit_id, target_state, evidence_fingerprint, verdict, message), but both MCP @tool builders in oompah/acp_tools.py register {result: dict}. Claude correctly called the advertised top-level contract repeatedly and the transport rejected every call with Input validation error: 'result' is a required property, leaving OOMPAH-939 In Validation after a 26-minute full gate. Scope: make every auditor transport expose the same canonical top-level input schema and continue accepting only server-validated target-bound fields; remove obsolete envelope ambiguity; add provider-shaped MCP catalog/schema and end-to-end submission tests for both project-aware builders plus regression coverage proving a top-level result reaches the coordinator exactly once. Work around audit-4827a2c0df9f after deployment or through the exact authenticated audit authority without weakening its verdict/gate requirements. Acceptance: advertised and enforced schemas are identical across auditor transports, a valid top-level submission is accepted, envelope/schema drift fails tests, and OOMPAH-939 resumes naturally.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-09 10:52
---
Implemented and pushed exact head 5defaaa42. Claude/OpenCode MCP tools now register the canonical top-level AUDITOR_RESULT_TOOL_SCHEMA, Codex uses the same explicit FunctionTool schema, and the obsolete nested result envelope is rejected. Provider-shaped tests prove schema equality and exactly one accepted coordinator submission. Verification: 191 auditor contract/API/bridge/deadline/output tests passed; terminal mutation, secret, diff, and fatal/static scans passed.
---
author: oompah
created: 2026-08-09 10:52
---
Aligned ACP auditor result contract at 5defaaa42
---
author: oompah
created: 2026-08-09 11:51
---
Branch quality gate passed for `5defaaa424e9a1303ee292ad523369e53e1b08e1` using `make test` in 161.1s. Review creation may proceed.
---
<!-- COMMENTS:END -->
