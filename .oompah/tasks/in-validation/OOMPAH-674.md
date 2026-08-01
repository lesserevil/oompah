---
id: OOMPAH-674
type: bug
status: In Validation
priority: 1
title: Include authenticated state in dashboard WebSocket bootstrap
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-01T04:42:35.189136Z'
updated_at: '2026-08-01T05:07:56.027813Z'
work_branch: OOMPAH-674
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/637
review_number: '637'
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
  total_input_tokens: 1460250
  total_output_tokens: 24777
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 1460250
      output_tokens: 24777
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 1459760
    output_tokens: 5743
    cost_usd: 0.0
    recorded_at: '2026-08-01T04:46:09.787965+00:00'
  - profile: default
    model: haiku
    input_tokens: 490
    output_tokens: 19034
    cost_usd: 0.0
    recorded_at: '2026-08-01T04:52:07.777103+00:00'
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
  - run_id: OOMPAH-674__20260801T044626Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: event_api
    source_branch: OOMPAH-674
    source_sha: 15eea17a142a79a33d69464d6e6c608c23e1eac4
    completed_at: '2026-08-01T04:52:07.781733+00:00'
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  task_branch: OOMPAH-674
  base_branch: main
  head_sha: 939abfda0d393cd98d95b61a71fb92df7ea740d0
  submitted_at: '2026-08-01T04:59:38.274093+00:00'
  updated_at: '2026-08-01T04:59:38.274093+00:00'
oompah.review_url: https://github.com/lesserevil/oompah/pull/637
oompah.review_number: '637'
oompah.work_branch: OOMPAH-674
oompah.target_branch: main
oompah.terminal_audit:
  queued_comment_posted: true
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-f2c5c85797e8
    project_id: proj-14849f1b
    task_id: OOMPAH-674
    target_state: Done
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: c5f72648c1528946f42facaee0d7f6a06fc734b696b9ac77091148fbebca7cb3
    attempts: []
    requested_by:
      version: 1
      identity: lesserevil
      source: forge
    previous_state: In Review
    created_at: '2026-08-01T05:07:51.113032+00:00'
  - version: 1
    audit_id: audit-975420f01fba
    project_id: proj-14849f1b
    task_id: OOMPAH-674
    target_state: Merged
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: c5f72648c1528946f42facaee0d7f6a06fc734b696b9ac77091148fbebca7cb3
    attempts: []
    requested_by:
      version: 1
      identity: lesserevil
      source: forge
    previous_state: In Review
    created_at: '2026-08-01T05:07:51.113032+00:00'
  attempt_history: []
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
author: oompah
created: 2026-08-01 04:51
---
Verification: All tests passing (119 total)

Test results:
✓ test_websocket_authenticated_bootstrap.py: 14/14 - WebSocket auth bootstrap tests
✓ test_server_auth.py: 73/73 - HTTP Basic authentication tests
✓ test_dashboard_authenticated_mutations.py: 13/13 - Dashboard mutation auth behavior
✓ test_state_api_responsiveness.py: 19/19 - State API caching and responsiveness

Implementation verified:
✓ WebSocket bootstrap includes http_auth.enabled
✓ WebSocket refresh includes http_auth.enabled
✓ REST and WebSocket metadata is consistent
✓ No credentials leak in payloads
✓ Backward compatibility preserved (unauthenticated mode)
✓ Authenticated dashboards can now do drag/drop and status changes without actor_mismatch
✓ Build ID and service instance ID included for both REST and WebSocket

Branch ready for integration.
---
author: oompah
created: 2026-08-01 04:51
---
Implemented centralized state snapshot enrichment for WebSocket and REST endpoints. WebSocket bootstrap now includes authenticated state (http_auth.enabled) matching REST behavior. Fixes actor_mismatch errors in authenticated dashboards. All 119 tests passing including 14 new regression tests for WebSocket authentication bootstrap.
---
author: oompah
created: 2026-08-01 04:52
---
Agent completed successfully in 345s (19524 tokens)
---
author: oompah
created: 2026-08-01 04:52
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 155, Tool calls: 60
- Tokens: 490 in / 19.0K out [19.5K total]
- Cost: $0.0000
- Exit: normal, Duration: 5m 45s
- Log: OOMPAH-674__20260801T044626Z.jsonl
---
author: oompah
created: 2026-08-01 04:59
---
Branch quality gate passed for `15eea17a142a79a33d69464d6e6c608c23e1eac4` using `make test` in 399.0s. Review creation may proceed.
---
author: oompah
created: 2026-08-01 04:59
---
Centralized redacted state enrichment across REST and every WebSocket state path so authenticated dashboards no longer send mismatched actor identities. Added bootstrap, refresh, redaction, backward-compatibility, and scheduler-broadcast regression coverage; 161 focused tests pass. The configured four-worker full gate separately reproduced an existing xdist worker-replacement failure unrelated to this patch.
---
author: oompah
created: 2026-08-01 05:07
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-01 05:07
---
YOLO: merged PR #637.
---
<!-- COMMENTS:END -->
