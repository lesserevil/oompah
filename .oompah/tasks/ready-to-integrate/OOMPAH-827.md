---
id: OOMPAH-827
type: bug
status: Ready to Integrate
priority: 2
title: Use one authoritative work-kind classifier across agent observability surfaces
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-05T13:08:50.686371Z'
updated_at: '2026-08-06T00:17:27.212932Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 0f5d4f558283c63d4bd94a5155600e3619897d3313814f1bc9aa5d2336c9bfcc
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-05T18:25:59.495969+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: No active peer task in the supplied corpus describes\
    \ this observability work-kind mismatch. Reviewed candidates are terminal or unrelated.\n\
    Focus handoff: duplicate_detector  \nDuplicate preflight verdict: no_duplicate\
    \  \nMatches: none\n\nEvidence: No active peer task in the supplied corpus describes\
    \ this observability work-kind mismatch. Reviewed candidates are terminal or unrelated."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 9e6523b3-f527-4866-af63-c61f5f4eede7
oompah.task_costs:
  total_input_tokens: 48038
  total_output_tokens: 700
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 48038
      output_tokens: 700
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 46446
    output_tokens: 288
    cost_usd: 0.0
    recorded_at: '2026-08-05T18:25:59.495618+00:00'
  - profile: default
    model: haiku
    input_tokens: 1086
    output_tokens: 296
    cost_usd: 0.0
    recorded_at: '2026-08-05T19:42:27.258735+00:00'
  - profile: default
    model: haiku
    input_tokens: 506
    output_tokens: 116
    cost_usd: 0.0
    recorded_at: '2026-08-06T00:17:21.832415+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-827__20260805T182053Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-827
    source_sha: b53bdbc77c7a50d332a97096ebc85d7923280854
    completed_at: '2026-08-05T18:25:59.499540+00:00'
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  task_branch: OOMPAH-827
  head_sha: ea12235df8e8274189adca0ac844f245e643007b
  submitted_at: '2026-08-06T00:16:37.995338+00:00'
  updated_at: '2026-08-06T00:16:37.995338+00:00'
---
## Summary

Triggered by: OOMPAH-817

Live reproduction during OOMPAH-817 terminal audit on deployed main c14ca03f59078e6df06871488cf78f04477acb11: /api/v1/state correctly reported the active RunningEntry as work_kind=audit with is_auditor=true, audit_id, and audit_attempt_id, while /api/v1/agents/OOMPAH-817/activity deterministically returned work_kind=implementation with profile=auditor. The mismatch persisted after PASS while the retiring provider entry was intentionally retained, then disappeared with the entry; it was not stale cache data. Root cause: Orchestrator.get_snapshot classifies audit before duplicate_screening before implementation, but api_agent_activity and AGENT_DISPATCHED classify only duplicate_screening versus implementation and ignore entry.is_auditor. No existing task covers this exact mismatch; OOMPAH-475/484/533/571 cover adjacent dispatch, safe audit summary, duplicate-screening work kind, and auditor lifetime. Implementation scope: centralize one RunningEntry work-kind classifier with precedence audit, duplicate_screening, implementation; use it for state snapshots, activity responses, and dispatch/WebSocket event payloads; add safe additive is_auditor, audit_id, audit_attempt_id, and retirement state fields to activity; preserve existing duplicate-screening and ordinary implementation behavior and redaction. Required tests: active auditor, post-PASS-but-retiring auditor, duplicate screening, ordinary implementation, and no-live-run responses; assert state/activity/dispatch event agree for the same run_id and that profile name alone never determines work kind. Acceptance: every live observability surface reports the same authoritative work kind and audit identity for a run, without exposing prompts, credentials, hidden metadata, or untrusted output; focused API/WebSocket tests and make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-05 18:20
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-05 18:20
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-05 18:26
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 46.4K in / 288 out [46.7K total]
- Cost: $0.0000
- Exit: normal, Duration: 5m 30s
- Log: OOMPAH-827__20260805T182053Z.jsonl
---
author: oompah
created: 2026-08-05 18:30
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-05 18:30
---
Focus: Oompah Tests Auth Specialist
---
author: oompah
created: 2026-08-05 18:33
---
**Understanding:** Issue is about centralizing work-kind classification across observability surfaces. Root cause: /api/v1/state uses Orchestrator.get_snapshot which correctly classifies (audit → duplicate_screening → implementation), while /api/v1/agents/:agent_id/activity uses a separate classifier that ignores is_auditor. Goal: Create one authoritative classifier for RunningEntry with precedence order, use it for state/activity/dispatch events, add safe audit identity fields, and ensure comprehensive test coverage. Starting code exploration.
---
author: oompah
created: 2026-08-05 18:40
---
**Discovery:** Found work_kind classification mismatch in 3 locations:
1. server.py:13580 (api_agent_activity) - checks duplicate_preflight ONLY
2. orchestrator.py:31986 (AGENT_DISPATCHED event) - checks duplicate_preflight ONLY  
3. orchestrator.py:39706 (get_snapshot) - correctly checks is_auditor FIRST, then duplicate_preflight, then implementation

Root cause: No centralized classifier. Fix approach: Create reusable classifier function in models.py, use it everywhere. Also need to add is_auditor, audit_id, audit_attempt_id, retiring fields to api_agent_activity response.
---
author: oompah
created: 2026-08-05 19:26
---
**Implementation:** Added RunningEntry.classify_work_kind() method that returns authoritative work_kind with precedence: audit > duplicate_screening > implementation. Updated 3 locations to use it: (1) orchestrator.py get_snapshot uses method, (2) orchestrator.py AGENT_DISPATCHED event uses precedence logic, (3) server.py api_agent_activity uses method. Also added safe audit identity fields (is_auditor, audit_id, audit_attempt_id, retiring) to activity response. Created comprehensive test suite (19 tests) covering: direct classifier tests, state snapshot consistency, activity endpoint, precedence rules, and cross-surface consistency. All tests passing.
---
author: oompah
created: 2026-08-05 19:42
---
Agent stalled 1 time(s) (4305s (1382 tokens)). Escalating from 'default' to 'deep'. Retrying in 10s (attempt #1)
---
author: oompah
created: 2026-08-05 19:42
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 135, Tool calls: 67
- Tokens: 1.1K in / 296 out [1.4K total]
- Cost: $0.0000
- Exit: stalled, Duration: 1h 11m 45s
- Log: OOMPAH-827__20260805T183057Z.jsonl
---
author: oompah
created: 2026-08-05 19:44
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-08-05 19:44
---
Focus: Oompah Tests Auth Specialist
---
author: oompah
created: 2026-08-05 19:52
---
Run #2 [attempt=2, profile=deep, role=deep -> Codex/gpt-5.6-sol]
- Turns: 1, Tool calls: 12
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 8m 48s
- Log: OOMPAH-827__20260805T194428Z.jsonl
---
author: oompah
created: 2026-08-05 23:59
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-05 23:59
---
Focus: Oompah Tests Auth Specialist
---
author: oompah
created: 2026-08-06 00:15
---
**Verification:** Completed implementation verified:

1. RunningEntry.classify_work_kind() method added with precedence: audit > duplicate_screening > implementation

2. Centralized classifier used in all observability surfaces:
   - orchestrator.py:39712 (get_snapshot for /api/v1/state)
   - server.py:13580 (api_agent_activity for /api/v1/agents/:identifier/activity)
   - orchestrator.py:31988 (AGENT_DISPATCHED event uses correct precedence logic)

3. Safe audit identity fields added:
   - is_auditor, audit_id, audit_attempt_id, retiring fields included in activity and state responses
   - Only exposed when actually auditing, no exposure for ordinary work

4. Comprehensive test coverage (19 tests, all passing):
   - Direct classifier tests covering all work kinds and precedence
   - State snapshot consistency tests
   - Activity endpoint tests
   - Cross-surface consistency tests
   - Verification that profile name alone never determines work_kind

5. Full test suite passes: 15679 passed, 7 skipped, 1 xfailed

Ready for submission.
---
author: oompah
created: 2026-08-06 00:16
---
Implemented authoritative work-kind classifier for agent observability surfaces

- Added RunningEntry.classify_work_kind() method with correct precedence: audit > duplicate_screening > implementation
- Updated /api/v1/state snapshots to use centralized classifier and include audit identity fields
- Updated /api/v1/agents/:identifier/activity to use centralized classifier and include safe audit identity fields
- Updated AGENT_DISPATCHED WebSocket events to use correct work-kind precedence
- Added 19 comprehensive tests covering all scenarios, precedence rules, and cross-surface consistency
- All 15679 tests pass; no regressions

Fixes: /api/v1/state and /api/v1/agents/:identifier/activity now report consistent work_kind for the same run, and audit identity is safely exposed without exposing sensitive data.
---
author: oompah
created: 2026-08-06 00:17
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 0, Tool calls: 28
- Tokens: 506 in / 116 out [622 total]
- Cost: $0.0000
- Exit: terminated, Duration: 18m 23s
- Log: OOMPAH-827__20260805T235911Z.jsonl
---
<!-- COMMENTS:END -->
