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
updated_at: '2026-08-05T18:26:14.155928Z'
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
oompah.agent_run_id: 724dee77-fd2c-400b-a75c-5c4dc654e861
oompah.task_costs:
  total_input_tokens: 46446
  total_output_tokens: 288
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 46446
      output_tokens: 288
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 46446
    output_tokens: 288
    cost_usd: 0.0
    recorded_at: '2026-08-05T18:25:59.495618+00:00'
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
<!-- COMMENTS:END -->
