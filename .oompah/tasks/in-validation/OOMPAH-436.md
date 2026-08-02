---
id: OOMPAH-436
type: task
status: In Validation
priority: null
title: Allow network-addressable access to the embedded MCP endpoint
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-24T02:29:45.093119Z'
updated_at: '2026-08-02T01:14:04.845483Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.terminal_audit:
  queued_comment_posted: true
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-18093e16b318
    project_id: proj-14849f1b
    task_id: OOMPAH-436
    target_state: Archived
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: bab61718ac6bf6719c6b099a647f625953c154214a35f5b46b94063d24762fcb
    attempts: []
    requested_by:
      version: 1
      identity: oompah
      source: auto_archive
    previous_state: Merged
    created_at: '2026-08-02T01:14:01.230493+00:00'
  attempt_history: []
---
## Summary

Make the embedded MCP transport network-addressable when explicitly enabled by service configuration. Preserve the existing loopback-only Host-header policy by default; add an OOMPAH_MCP_ALLOW_NETWORK environment setting, set it true for this deployment, and disable FastMCP DNS-rebinding Host validation only in that explicit mode. Update the OpenAPI MCP policy documentation and add tests for both default-local and enabled-network settings. Acceptance: clients can initialize the MCP endpoint through a non-loopback Host header when enabled, local-only remains default, and make test passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-24 02:31
---
Implemented explicit network MCP mode. OOMPAH_MCP_ALLOW_NETWORK=true disables FastMCP's exact Host-header allow-list only when requested; the default remains loopback-only. Added configuration reference, policy documentation, and tests for both modes. Focused suite passed (296 tests) and required full make test passed; committing and deploying next.
---
author: oompah
created: 2026-07-24 02:34
---
Implemented and deployed in 8fc368e6d. OOMPAH_MCP_ALLOW_NETWORK=true is active; an MCP initialize request using non-loopback Host 192.0.2.10:8090 returned HTTP 200. Default remains loopback-only.
---
author: oompah
created: 2026-07-26 00:29
---
Delivery reconciled: configured network access to the embedded MCP endpoint is present on origin/main in commit 8fc368e6d. This task was Done rather than waiting for an agent; it is now being aligned with the delivered repository state.
---
author: oompah
created: 2026-07-26 00:29
---
Verified delivered on origin/main in 8fc368e6d and reconciled stale Done state.
---
author: oompah
created: 2026-08-02 01:14
---
Queued Archived audit: Aged Merged auto-archive (closed 7 days ago). An auditor will review before the task is retired.
---
<!-- COMMENTS:END -->
