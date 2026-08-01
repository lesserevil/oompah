---
id: OOMPAH-674
type: bug
status: In Progress
priority: 1
title: Include authenticated state in dashboard WebSocket bootstrap
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-01T04:42:35.189136Z'
updated_at: '2026-08-01T04:51:21.788935Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 8ea86dc11708d3327cad1b4170a7bc0479709b0d035394c916c46d95e64eb484
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-01T04:46:09.842498+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector  \nDuplicate preflight verdict: no_duplicate\
    \  \nMatches: none  \nEvidence: OOMPAH-670 is the predecessor fix; OOMPAH-674\
    \ uniquely addresses server-side WebSocket state enrichment. OOMPAH-13 and OOMPAH-205\
    \ are archived and cover different behavior. Active OOMPAH-281 and OOMPAH-282\
    \ are unrelated."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
oompah.agent_run_id: ca12a5d3-6dc7-4666-b490-7289e979dd91
oompah.task_costs:
  total_input_tokens: 1459760
  total_output_tokens: 5743
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 1459760
      output_tokens: 5743
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 1459760
    output_tokens: 5743
    cost_usd: 0.0
    recorded_at: '2026-08-01T04:46:09.787965+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-674__20260801T044338Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-674
    source_sha: f64c1c9b35d46b4028d323697eb75287f60d04a7
    completed_at: '2026-08-01T04:46:09.867194+00:00'
---
## Summary

Bug follow-up to OOMPAH-670. The dashboard normally initializes from /ws, but websocket_endpoint sends _cached_state_snapshot_or_unavailable() directly while /api/v1/state augments the snapshot with http_auth. Therefore a fresh authenticated dashboard keeps httpAuthEnabled=false and status mutations include actor_login, which the authenticated server correctly rejects as actor_mismatch. Implementation scope: centralize and enrich public state snapshots so REST and every WebSocket state message include the same redacted build, service, and auth metadata; ensure no credentials or secret material can enter the payload. Add regression tests that exercise initial WebSocket state and refresh state under HTTP Basic auth and prove the dashboard status mutation omits client-supplied actor identity. Acceptance criteria: authenticated drag/drop and status changes succeed without actor_mismatch; REST and WebSocket expose consistent redacted http_auth.enabled; unauthenticated deployments preserve compatibility; focused tests and the configured Makefile gate pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-01 04:43
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-01 04:43
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-01 04:46
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 36
- Tokens: 1.5M in / 5.7K out [1.5M total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 36s
- Log: OOMPAH-674__20260801T044338Z.jsonl
---
author: oompah
created: 2026-08-01 04:46
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-01 04:46
---
Focus: Event Api Redaction Specialist
---
author: oompah
created: 2026-08-01 04:46
---
Understanding: This is a bug follow-up to OOMPAH-670. The issue is that the WebSocket endpoint doesn't include HTTP auth state in the initial state snapshot, while the REST /api/v1/state endpoint does. This causes authenticated dashboards to have httpAuthEnabled=false and incorrectly include actor_login in status mutations, triggering actor_mismatch rejections. 

Planned approach:
1. Find the _cached_state_snapshot_or_unavailable() implementation in the websocket endpoint
2. Find how /api/v1/state augments the snapshot with http_auth
3. Centralize state snapshot enrichment so both REST and WebSocket paths use the same logic
4. Add tests verifying WebSocket bootstrap includes auth state under HTTP Basic auth
5. Verify status mutations omit client-supplied actor identity
6. Ensure backward compatibility for unauthenticated deployments

Starting investigation now.
---
author: oompah
created: 2026-08-01 04:48
---
Discovery: Found the bug in oompah/server.py:

The WebSocket endpoint (line 2896) sends _cached_state_snapshot_or_unavailable() directly without augmenting it with http_auth state.

The REST /api/v1/state endpoint (lines 3308-3362) calls the same function but then enriches the snapshot with:
- snapshot["http_auth"] = _http_auth_reload_status() 
- snapshot["build_id"]
- snapshot["service_instance_id"]
- snapshot["api_metrics"]

This is why authenticated dashboards connecting via WebSocket have httpAuthEnabled=false, causing status mutations to include actor_login which triggers actor_mismatch errors.

Solution: Create a helper function to enrich snapshots consistently, use it in both REST and WebSocket endpoints. Add regression tests for WebSocket bootstrap with HTTP Basic auth.
---
author: oompah
created: 2026-08-01 04:51
---
Implementation: Centralized state snapshot enrichment in oompah/server.py

Changes made:
1. Created _enrich_state_snapshot() helper function that enriches snapshots with:
   - http_auth (redacted reload status, no credentials)
   - build_id
   - service_instance_id
   - api_metrics

2. Updated WebSocket endpoint to use enriched snapshots:
   - Initial state bootstrap now includes http_auth.enabled
   - Refresh state also includes http_auth.enabled
   - Both REST and WebSocket now send identical metadata

3. Updated broadcast functions:
   - _on_state_only_change() enriches before broadcast
   - _on_orchestrator_change() enriches before broadcast
   
4. Simplified REST API endpoint to use the same enrichment function

5. Created comprehensive test suite (test_websocket_authenticated_bootstrap.py):
   - 14 tests covering WebSocket bootstrap with/without auth
   - Tests verify REST/WebSocket consistency
   - Tests verify no credentials leak in payloads
   - Tests verify backward compatibility

All tests pass, including:
- New WebSocket authentication bootstrap tests: 14/14 ✓
- Existing dashboard authenticated mutations tests: 13/13 ✓
- Existing server auth tests: 73/73 ✓
- Existing state API responsiveness tests: 19/19 ✓
---
<!-- COMMENTS:END -->
