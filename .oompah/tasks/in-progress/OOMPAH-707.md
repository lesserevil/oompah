---
id: OOMPAH-707
type: task
status: In Progress
priority: null
title: Preserve explicit owner work from orphaned-In-Progress reset
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-02T22:19:11.796639Z'
updated_at: '2026-08-02T22:39:31.861578Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 7d4d9cd88ad1c84fe1c9d9dcb34803d9be4586a3b35ef419bd3cfa27efa0e822
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-02T22:39:06.357208+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector  \nDuplicate preflight verdict: no_duplicate\
    \  \nMatches: none  \n\nEvidence: No active peer task covers direct-owner claims\
    \ or orphan watchdog resets. Closest reviewed tasks OOMPAH-160, OOMPAH-163, and\
    \ OOMPAH-165 are archived and address different mechanisms."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: f1dfc558-8b09-4a7a-8956-ed39503796d9
oompah.task_costs:
  total_input_tokens: 50340
  total_output_tokens: 904
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 50340
      output_tokens: 904
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 50340
    output_tokens: 904
    cost_usd: 0.0
    recorded_at: '2026-08-02T22:39:06.355945+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-707__20260802T223833Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-707
    source_sha: 53b14479d528381299b101f602dae6fae1161df9
    completed_at: '2026-08-02T22:39:06.408255+00:00'
---
## Summary

Triggered by: OOMPAH-701\n\nProduction evidence on 2026-08-02: the authenticated project owner placed human-only OOMPAH-701 In Progress for direct implementation with an explicit handoff comment and active task worktree, but _reset_orphaned_in_progress changed it back to Open twice because no scheduler RunningEntry was attached. This makes direct owner work look idle and can expose it to conflicting lifecycle automation.\n\nImplementation scope:\n- Represent a durable direct-owner claim/lease, or another explicit ownership fence, that distinguishes intentional owner work from a genuinely orphaned scheduler assignment.\n- Make _reset_orphaned_in_progress preserve a live owner claim while retaining recovery of truly abandoned tasks.\n- Expose the ownership source and staleness/expiry evidence in API/UI state.\n- Define bounded expiry/release behavior so an abandoned owner claim cannot strand work indefinitely.\n\nRelevant code: oompah/orchestrator.py _reset_orphaned_in_progress and watchdog maintenance; task status/assignment APIs; native Markdown tracker metadata; dashboard task/agent ownership state.\n\nRequired tests:\n- Direct owner claim plus human-only and In Progress survives repeated orphan watchdog scans.\n- Expired/explicitly released owner claim is safely reset through the existing recovery path.\n- Scheduler-owned orphan behavior remains unchanged.\n- Owner claim versus watchdog scan is serialized so neither transition can overwrite a newer decision.\n\nAcceptance criteria:\n- Intentional direct owner work remains visibly In Progress without a scheduler agent.\n- Genuine orphan recovery stays bounded and automatic.\n- Focused race tests and make test/check-secrets pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-02 22:37
---
Promoted to Open after confirming the live watchdog reset direct project-owner work twice. The description contains the production evidence, implementation scope, required race tests, and bounded owner-claim acceptance criteria; Oompah may dispatch it normally while the directly owned OOMPAH-701 repair proceeds.
---
author: oompah
created: 2026-08-02 22:38
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-02 22:38
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-02 22:39
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 50.3K in / 904 out [51.2K total]
- Cost: $0.0000
- Exit: normal, Duration: 37s
- Log: OOMPAH-707__20260802T223833Z.jsonl
---
author: oompah
created: 2026-08-02 22:39
---
Agent dispatched (profile: default)
---
<!-- COMMENTS:END -->
