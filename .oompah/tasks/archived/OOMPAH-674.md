---
id: OOMPAH-674
type: bug
status: Archived
priority: 1
title: Include authenticated state in dashboard WebSocket bootstrap
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-01T04:42:35.189136Z'
updated_at: '2026-08-08T06:09:20.963215Z'
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
  total_input_tokens: 1460326
  total_output_tokens: 32294
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 1460250
      output_tokens: 24777
      cost_usd: 0.0
    unknown:
      input_tokens: 76
      output_tokens: 7517
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
  - profile: auditor
    model: unknown
    input_tokens: 35
    output_tokens: 6026
    cost_usd: 0.0
    recorded_at: '2026-08-01T05:11:57.300453+00:00'
  - profile: auditor
    model: unknown
    input_tokens: 41
    output_tokens: 1491
    cost_usd: 0.0
    recorded_at: '2026-08-01T05:14:47.405919+00:00'
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
  applied_result_attempts:
    attempt-a14907dc5a93: '2026-08-01T05:11:38.787775+00:00'
    attempt-af077b3208be: '2026-08-01T05:14:29.909974+00:00'
    attempt-65c55e3b2782: '2026-08-08T06:09:08.807186+00:00'
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-674
    target_state: Done
    evidence_fingerprint: c5f72648c1528946f42facaee0d7f6a06fc734b696b9ac77091148fbebca7cb3
    audit_ids:
    - audit-f2c5c85797e8
    kind: result
    applied: true
    retired_at: '2026-08-01T05:11:38.787784+00:00'
  - project_id: proj-14849f1b
    task_id: OOMPAH-674
    target_state: Merged
    evidence_fingerprint: c5f72648c1528946f42facaee0d7f6a06fc734b696b9ac77091148fbebca7cb3
    audit_ids:
    - audit-975420f01fba
    kind: result
    applied: true
    retired_at: '2026-08-01T05:14:29.909996+00:00'
  - project_id: proj-14849f1b
    task_id: OOMPAH-674
    target_state: Archived
    evidence_fingerprint: 3c776126423075d0892fd4326cfe444e471f24909e23e9996e76534b1ad644bb
    audit_ids:
    - audit-19d1d5d121ef
    kind: result
    applied: true
    retired_at: '2026-08-08T06:09:08.807207+00:00'
  oompah.terminal_audit_result_intents:
  - project_id: proj-14849f1b
    task_id: OOMPAH-674
    audit_id: audit-f2c5c85797e8
    attempt_id: attempt-a14907dc5a93
    target_state: Done
    evidence_fingerprint: c5f72648c1528946f42facaee0d7f6a06fc734b696b9ac77091148fbebca7cb3
    status: In Validation
    audit_ids:
    - audit-f2c5c85797e8
    applied: true
    created_at: '2026-08-01T05:11:38.787795+00:00'
    applied_at: '2026-08-01T05:11:42.670008+00:00'
  - project_id: proj-14849f1b
    task_id: OOMPAH-674
    audit_id: audit-975420f01fba
    attempt_id: attempt-af077b3208be
    target_state: Merged
    evidence_fingerprint: c5f72648c1528946f42facaee0d7f6a06fc734b696b9ac77091148fbebca7cb3
    status: Merged
    audit_ids:
    - audit-975420f01fba
    applied: true
    created_at: '2026-08-01T05:14:29.910021+00:00'
    applied_at: '2026-08-01T05:14:35.270876+00:00'
  - project_id: proj-14849f1b
    task_id: OOMPAH-674
    audit_id: audit-19d1d5d121ef
    attempt_id: attempt-65c55e3b2782
    target_state: Archived
    evidence_fingerprint: 3c776126423075d0892fd4326cfe444e471f24909e23e9996e76534b1ad644bb
    status: Archived
    audit_ids:
    - audit-19d1d5d121ef
    kind: result
    applied: true
    created_at: '2026-08-08T06:09:08.807230+00:00'
    applied_at: '2026-08-08T06:09:19.343961+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-f2c5c85797e8
    project_id: proj-14849f1b
    task_id: OOMPAH-674
    target_state: Done
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: c5f72648c1528946f42facaee0d7f6a06fc734b696b9ac77091148fbebca7cb3
    attempts:
    - version: 1
      attempt_id: attempt-a14907dc5a93
      target_state: Done
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: c5f72648c1528946f42facaee0d7f6a06fc734b696b9ac77091148fbebca7cb3
      created_at: '2026-08-01T05:08:59.426284+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-01T05:08:59.426284+00:00'
      branch_key: OOMPAH-674
      verdict: pass
      completed_at: '2026-08-01T05:11:38.787635+00:00'
      ended_at: '2026-08-01T05:11:38.787635+00:00'
    requested_by:
      version: 1
      identity: lesserevil
      source: forge
    previous_state: In Review
    created_at: '2026-08-01T05:07:51.113032+00:00'
    updated_at: '2026-08-01T05:11:38.787635+00:00'
  - version: 1
    audit_id: audit-975420f01fba
    project_id: proj-14849f1b
    task_id: OOMPAH-674
    target_state: Merged
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: c5f72648c1528946f42facaee0d7f6a06fc734b696b9ac77091148fbebca7cb3
    attempts:
    - version: 1
      attempt_id: attempt-af077b3208be
      target_state: Merged
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: c5f72648c1528946f42facaee0d7f6a06fc734b696b9ac77091148fbebca7cb3
      created_at: '2026-08-01T05:11:59.552699+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-01T05:11:59.552699+00:00'
      branch_key: OOMPAH-674
      verdict: pass
      completed_at: '2026-08-01T05:14:29.909730+00:00'
      ended_at: '2026-08-01T05:14:29.909730+00:00'
    requested_by:
      version: 1
      identity: lesserevil
      source: forge
    previous_state: In Review
    created_at: '2026-08-01T05:07:51.113032+00:00'
    updated_at: '2026-08-01T05:14:29.909730+00:00'
  - version: 1
    audit_id: audit-19d1d5d121ef
    project_id: proj-14849f1b
    task_id: OOMPAH-674
    target_state: Archived
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 3c776126423075d0892fd4326cfe444e471f24909e23e9996e76534b1ad644bb
    attempts:
    - version: 1
      attempt_id: attempt-65c55e3b2782
      target_state: Archived
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 3c776126423075d0892fd4326cfe444e471f24909e23e9996e76534b1ad644bb
      created_at: '2026-08-08T06:05:09.856615+00:00'
      provider_id: prov-651d553c
      model: sonnet
      started_at: '2026-08-08T06:05:09.856615+00:00'
      branch_key: OOMPAH-674
      selected_ref: 939abfda0d393cd98d95b61a71fb92df7ea740d0
      selected_sha: 939abfda0d393cd98d95b61a71fb92df7ea740d0
      verdict: pass
      completed_at: '2026-08-08T06:09:08.806892+00:00'
      ended_at: '2026-08-08T06:09:08.806892+00:00'
    requested_by:
      version: 1
      identity: oompah
      source: auto_archive
    previous_state: Merged
    created_at: '2026-08-08T06:03:52.087250+00:00'
    selected_ref: 939abfda0d393cd98d95b61a71fb92df7ea740d0
    selected_sha: 939abfda0d393cd98d95b61a71fb92df7ea740d0
    updated_at: '2026-08-08T06:09:08.806892+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-a14907dc5a93
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: c5f72648c1528946f42facaee0d7f6a06fc734b696b9ac77091148fbebca7cb3
    created_at: '2026-08-01T05:08:59.426284+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-01T05:08:59.426284+00:00'
    branch_key: OOMPAH-674
  - version: 1
    attempt_id: attempt-af077b3208be
    target_state: Merged
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: c5f72648c1528946f42facaee0d7f6a06fc734b696b9ac77091148fbebca7cb3
    created_at: '2026-08-01T05:11:59.552699+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-01T05:11:59.552699+00:00'
    branch_key: OOMPAH-674
  - version: 1
    attempt_id: attempt-65c55e3b2782
    target_state: Archived
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 3c776126423075d0892fd4326cfe444e471f24909e23e9996e76534b1ad644bb
    created_at: '2026-08-08T06:05:09.856615+00:00'
    provider_id: prov-651d553c
    model: sonnet
    started_at: '2026-08-08T06:05:09.856615+00:00'
    branch_key: OOMPAH-674
    selected_ref: 939abfda0d393cd98d95b61a71fb92df7ea740d0
    selected_sha: 939abfda0d393cd98d95b61a71fb92df7ea740d0
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
author: oompah
created: 2026-08-01 05:09
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-08-01 05:09
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-01 05:11
---
Audit PASS — Done

[REDACTED]

Safe evidence:
- merge_state: branch fully merged into main; git log main..HEAD is empty; both OOMPAH-674 commits reachable from main
- commits: 15eea17a142a79a33d69464d6e6c608c23e1eac4 (implementation, +442 lines) and 939abfda0d393cd98d95b61a71fb92df7ea740d0 (regression tightening)
- enrichment_helper: _enrich_state_snapshot() at oompah/server.py:3319 adds build_id, service_instance_id, http_auth (via _http_auth_reload_status()), api_metrics
- enrichment_call_sites: oompah/server.py lines 2549, 2569, 2902, 2924, 3384, 3391 — covers REST /api/v1/state, WebSocket initial bootstrap, WebSocket refresh, and both broadcast paths
- focused_tests: test_websocket_authenticated_bootstrap.py 14/14 pass; test_dashboard_authenticated_mutations.py + test_state_api_responsiveness.py + test_server_auth.py 105/105 pass locally
- branch_gate_history: Scheduler comment records 'Branch quality gate passed for 15eea17a142a79a33d69464d6e6c608c23e1eac4 using make test in 399.0s'
- pr_status: Scheduler comment records 'YOLO: merged PR #637'
---
author: oompah
created: 2026-08-01 05:11
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/opus]
- Turns: 36, Tool calls: 29
- Tokens: 35 in / 6.0K out [6.1K total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 57s
- Log: OOMPAH-674__20260801T050904Z.jsonl
---
author: oompah
created: 2026-08-01 05:12
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-08-01 05:12
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-01 05:14
---
Audit PASS — Merged

[REDACTED]

Safe evidence:
- merge_state: Branch fully merged into main via PR #637 (merge commit cde640113). git log main..HEAD returns empty; git log HEAD..main returns only the merge commit.
- commits_on_main: 15eea17a1 (implementation) and 939abfda0 (regression tightening) reachable from main.
- enrichment_helper: _enrich_state_snapshot at oompah/server.py:3319 adds build_id, service_instance_id, http_auth (via _http_auth_reload_status at line 1304), api_metrics.
- enrichment_call_sites: oompah/server.py lines 2549, 2569, 2902, 2924, 3384, 3391 — covers REST /api/v1/state (both branches), WebSocket initial bootstrap, WebSocket refresh, and both broadcast paths.
- redaction_confirmed: _http_auth_reload_status at line 1304 returns only {enabled, reload: {state, generation, retaining_last_known_good}} — no credentials.
- focused_tests: test_websocket_authenticated_bootstrap.py 14/14 pass in 0.98s; test_dashboard_authenticated_mutations + test_state_api_responsiveness + test_server_auth 105/105 pass in 3.97s.
- branch_gate_history: Scheduler comment records 'Branch quality gate passed for 15eea17a142a79a33d69464d6e6c608c23e1eac4 using make test in 399.0s'.
- pr_status: Scheduler comment records 'YOLO: merged PR #637'.
---
author: oompah
created: 2026-08-01 05:14
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/opus]
- Turns: 0, Tool calls: 26
- Tokens: 41 in / 1.5K out [1.5K total]
- Cost: $0.0000
- Exit: terminated, Duration: 2m 47s
- Log: OOMPAH-674__20260801T051209Z.jsonl
---
author: oompah
created: 2026-08-08 06:05
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/sonnet)
---
author: oompah
created: 2026-08-08 06:05
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-08 06:09
---
Audit PASS — Archived

Audit PASS — Archived. OOMPAH-674 is fully merged and safe to archive. Implementation is correct and complete; all focused tests pass; no unsafe_archive conditions found.

Safe evidence:
- merge_state: Branch fully merged; git log main..HEAD is empty. Merge commit cde640113 (PR #637) confirmed in main history. Main has 306 commits since accepted head 939abfda0.
- accepted_head_sha: 939abfda0d393cd98d95b61a71fb92df7ea740d0
- enrichment_helper: _enrich_state_snapshot() at oompah/server.py:3319 adds build_id, service_instance_id, http_auth (via _http_auth_reload_status()), api_metrics
- enrichment_call_sites: oompah/server.py lines 2549, 2569 (broadcast paths), 2902, 2924 (WebSocket bootstrap/refresh), 3384, 3391 (REST /api/v1/state)
- redaction_confirmed: _http_auth_reload_status() at line 1304 returns only {enabled, reload: {state, generation, retaining_last_known_good}} — no credentials
- focused_tests: test_websocket_authenticated_bootstrap.py 14/14 pass in 0.99s; test_dashboard_authenticated_mutations 13/13; test_server_auth 73/73; test_state_api_responsiveness 19/19 — total 119/119
- prior_audits: Two Opus auditors previously passed Done and Merged state audits for this task
- historical_gate: Scheduler recorded: Branch quality gate passed for 15eea17a142a79a33d69464d6e6c608c23e1eac4 using make test in 399.0s
- stale_gate_note: Full gate evidence is stale per scheduler; focused tests confirm implementation integrity; archive audit does not require re-merging
---
<!-- COMMENTS:END -->
