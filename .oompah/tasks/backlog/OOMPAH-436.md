---
id: OOMPAH-436
type: task
status: Backlog
priority: null
title: Allow network-addressable access to the embedded MCP endpoint
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-24T02:29:45.093119Z'
updated_at: '2026-07-24T02:29:45.093119Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Make the embedded MCP transport network-addressable when explicitly enabled by service configuration. Preserve the existing loopback-only Host-header policy by default; add an OOMPAH_MCP_ALLOW_NETWORK environment setting, set it true for this deployment, and disable FastMCP DNS-rebinding Host validation only in that explicit mode. Update the OpenAPI MCP policy documentation and add tests for both default-local and enabled-network settings. Acceptance: clients can initialize the MCP endpoint through a non-loopback Host header when enabled, local-only remains default, and make test passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

