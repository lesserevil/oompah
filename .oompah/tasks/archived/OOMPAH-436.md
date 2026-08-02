---
id: OOMPAH-436
type: task
status: Archived
priority: null
title: Allow network-addressable access to the embedded MCP endpoint
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-24T02:29:45.093119Z'
updated_at: '2026-08-02T01:24:32.960552Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.terminal_audit:
  queued_comment_posted: true
  applied_result_attempts:
    attempt-9fc30ccce8df: '2026-08-02T01:24:27.504424+00:00'
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-436
    target_state: Archived
    evidence_fingerprint: bab61718ac6bf6719c6b099a647f625953c154214a35f5b46b94063d24762fcb
    audit_ids:
    - audit-18093e16b318
    kind: result
    applied: true
    retired_at: '2026-08-02T01:24:27.504436+00:00'
  oompah.terminal_audit_result_intents:
  - project_id: proj-14849f1b
    task_id: OOMPAH-436
    audit_id: audit-18093e16b318
    attempt_id: attempt-9fc30ccce8df
    target_state: Archived
    evidence_fingerprint: bab61718ac6bf6719c6b099a647f625953c154214a35f5b46b94063d24762fcb
    status: Archived
    audit_ids:
    - audit-18093e16b318
    applied: true
    created_at: '2026-08-02T01:24:27.504453+00:00'
    applied_at: '2026-08-02T01:24:32.074267+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-18093e16b318
    project_id: proj-14849f1b
    task_id: OOMPAH-436
    target_state: Archived
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: bab61718ac6bf6719c6b099a647f625953c154214a35f5b46b94063d24762fcb
    attempts:
    - version: 1
      attempt_id: attempt-9fc30ccce8df
      target_state: Archived
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: bab61718ac6bf6719c6b099a647f625953c154214a35f5b46b94063d24762fcb
      created_at: '2026-08-02T01:16:20.130966+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-02T01:16:20.130966+00:00'
      branch_key: OOMPAH-436
      verdict: pass
      completed_at: '2026-08-02T01:24:27.504229+00:00'
      ended_at: '2026-08-02T01:24:27.504229+00:00'
    requested_by:
      version: 1
      identity: oompah
      source: auto_archive
    previous_state: Merged
    created_at: '2026-08-02T01:14:01.230493+00:00'
    updated_at: '2026-08-02T01:24:27.504229+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-9fc30ccce8df
    target_state: Archived
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: bab61718ac6bf6719c6b099a647f625953c154214a35f5b46b94063d24762fcb
    created_at: '2026-08-02T01:16:20.130966+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-02T01:16:20.130966+00:00'
    branch_key: OOMPAH-436
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
author: oompah
created: 2026-08-02 01:16
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-08-02 01:16
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-02 01:24
---
Audit PASS — Archived

[REDACTED]

Safe evidence:
- delivery_commit: 8fc368e6d Allow configured network MCP access
- commit_on_main: true (git log 8fc368e6d..origin/main shows only later commits)
- gateway_symbols: mcp_network_access_enabled, mcp_transport_security_settings, _MCP_ALLOW_NETWORK_ENV=OOMPAH_MCP_ALLOW_NETWORK
- default_hosts: 127.0.0.1, 127.0.0.1:*, localhost, localhost:*
- network_mode_effect: TransportSecuritySettings(enable_dns_rebinding_protection=False)
- tests_present: test_mcp_defaults_to_loopback_host_protection; test_mcp_can_be_explicitly_enabled_for_network_hosts; test_network_enabled_mcp_transport_still_challenges_missing_basic_auth
- docs_updated: plans/mcp-openapi-exposure-policy.md section 3 documents OOMPAH_MCP_ALLOW_NETWORK and its trust boundary
- previous_state: Merged (aged 7 days per scheduler evidence)
---
<!-- COMMENTS:END -->
