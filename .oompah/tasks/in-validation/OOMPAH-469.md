---
id: OOMPAH-469
type: feature
status: In Validation
priority: 1
title: Add the reserved read-only auditor focus and prompt contract
parent: OOMPAH-458
children: []
blocked_by:
- OOMPAH-461
- OOMPAH-457
labels: []
assignee: null
created_at: '2026-07-28T13:06:09.346734Z'
updated_at: '2026-08-05T18:49:39.801060Z'
work_branch: epic-OOMPAH-458
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 4fa10114-a7a3-45ba-9b5f-471c0393a727
oompah.work_branch: epic-OOMPAH-458
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: fc95dc43786acea1fa29f7e6b793dad2c457cbea2c2d863770d6dbc5a33d2d33
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-07-28T23:49:47.984137+00:00'
  matched_identifiers: []
  evidence: 'Focus handoff: duplicate_detector


    Duplicate preflight verdict: no_duplicate


    Matches: none


    Evidence: OOMPAH-470, OOMPAH-471, OOMPAH-474, and OOMPAH-475 are distinct downstream
    auditor candidate, evidence, result-tool, and dispatch work. OOMPAH-457/461/468
    and OOMPAH-287/290/291 are terminal or prerequisite infrastructure, not duplicates.
    No files or tracker state were modified.'
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 1
  retry_after: null
oompah.task_costs:
  total_input_tokens: 29193869
  total_output_tokens: 64860
  total_cost_usd: 0.0
  by_model:
    sonnet:
      input_tokens: 56
      output_tokens: 1511
      cost_usd: 0.0
    haiku:
      input_tokens: 29193813
      output_tokens: 63349
      cost_usd: 0.0
  runs:
  - profile: standard
    model: sonnet
    input_tokens: 56
    output_tokens: 1511
    cost_usd: 0.0
    recorded_at: '2026-07-28T22:17:11.398503+00:00'
  - profile: default
    model: haiku
    input_tokens: 967398
    output_tokens: 5968
    cost_usd: 0.0
    recorded_at: '2026-07-28T22:50:37.903543+00:00'
  - profile: default
    model: haiku
    input_tokens: 545724
    output_tokens: 2928
    cost_usd: 0.0
    recorded_at: '2026-07-28T23:49:47.983657+00:00'
  - profile: default
    model: haiku
    input_tokens: 376
    output_tokens: 74
    cost_usd: 0.0
    recorded_at: '2026-07-28T23:51:06.469457+00:00'
  - profile: default
    model: haiku
    input_tokens: 27680315
    output_tokens: 54379
    cost_usd: 0.0
    recorded_at: '2026-07-29T00:33:07.856480+00:00'
oompah.terminal_audit:
  queued_comment_posted: true
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-720c324ed427
    project_id: proj-14849f1b
    task_id: OOMPAH-469
    target_state: Archived
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: eb4b81678b2206993ec6248508ee7fefa75cbd3aacb838a588587f73dadc11b8
    attempts:
    - version: 1
      attempt_id: attempt-83cbc77f9941
      target_state: Archived
      request_state: in_progress
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: eb4b81678b2206993ec6248508ee7fefa75cbd3aacb838a588587f73dadc11b8
      created_at: '2026-08-05T18:49:28.668165+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-05T18:49:28.668165+00:00'
      branch_key: epic-OOMPAH-458
    requested_by:
      version: 1
      identity: oompah
      source: auto_archive
    previous_state: Merged
    created_at: '2026-08-05T18:22:23.660401+00:00'
    updated_at: '2026-08-05T18:49:28.668165+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-83cbc77f9941
    target_state: Archived
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: eb4b81678b2206993ec6248508ee7fefa75cbd3aacb838a588587f73dadc11b8
    created_at: '2026-08-05T18:49:28.668165+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-05T18:49:28.668165+00:00'
    branch_key: epic-OOMPAH-458
---
## Summary

Implementation scope

Add a built-in focus named auditor with role Completion Auditor, but exclude it from normal keyword/LLM focus triage. Its prompt must provide the requested target contract, trusted task metadata, delimited untrusted descriptions/comments, evidence summary, allowed read/test actions, and the auditor result tool schema. The focus must explicitly prohibit editing files, committing, pushing, merging, creating tasks, changing status, or fixing findings. Add a capability policy that exposes read-only repository/test operations plus the result tool and denies mutating task/Git actions server-side.

Tests

Verify auditor is never selected for ordinary work, renders all required instructions and untrusted boundaries, receives the target-specific contract, cannot call protected mutation tools, and can call the result tool. Add prompt-injection tests where task text asks the auditor to approve or modify code. Run focused tests and make test.

Acceptance criteria

Only the audit scheduler can select the focus; an auditor can inspect and report but cannot implement, merge, or change tracker state even when task content requests it.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-28 21:50
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-28 21:50
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-28 21:52
---
Understanding: I will complete duplicate screening for the reserved read-only auditor focus by searching all task states, plans, docs, and history for an existing auditor-focus/prompt-contract/server-side capability implementation; I will read the closest candidates in full and then either archive this as a confirmed duplicate or hand off with evidence. I will not modify code in this duplicate-investigator phase.
---
author: oompah
created: 2026-07-28 21:52
---
Discovery: No duplicate confirmed. I searched .oompah/tasks across all states plus plans/, docs/, README.md, WORKFLOW.md, source/tests, and git history. Read the full records for OOMPAH-457, OOMPAH-461, OOMPAH-468, OOMPAH-470, OOMPAH-471, OOMPAH-474, OOMPAH-475, and the closest prior prompt-injection tasks OOMPAH-287, OOMPAH-290, and OOMPAH-291. OOMPAH-457 is the terminal-audit state/coordinator foundation and explicitly does not dispatch auditor agents; OOMPAH-461 adds In Validation and explicitly excludes the auditor scheduler; OOMPAH-468 identifies OOMPAH-469 as the separate auditor-focus contract; OOMPAH-470, OOMPAH-471, OOMPAH-474, and OOMPAH-475 are downstream candidate/evidence/result/dispatch work. OOMPAH-287/290/291 cover general provenance, authority boundaries, and prompt-injection regression, not this reserved focus and target-specific contract.
---
author: oompah
created: 2026-07-28 21:52
---
Focus handoff: duplicate_detector — Outcome: no duplicate confirmed; OOMPAH-469 is a distinct implementation task. Evidence/decisions: searched with rg across .oompah/tasks, plans, docs, README.md, and WORKFLOW.md, plus git log/history; reviewed the full task records and comments for OOMPAH-457/461/468/470/471/474/475 and prior prompt-injection tasks OOMPAH-287/290/291. The terminal-audit foundation (OOMPAH-457) and In Validation status (OOMPAH-461) are prerequisites and explicitly leave auditor dispatch/focus work out of scope. OOMPAH-468 calls this task the separate auditor-focus contract; downstream tasks consume it. No code or tests were changed, so no focused test run is applicable in this phase. Remaining work/risks: implement the reserved auditor focus/prompt renderer and server-side read-only capability policy, preserve untrusted delimiters and target-specific contracts, exclude it from ordinary triage, and add prompt-injection/tool-authorization tests. Recommended next focus: feature.
---
author: oompah
created: 2026-07-28 21:53
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 0, Tool calls: 38
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 2m 35s
- Log: OOMPAH-469__20260728T215031Z.jsonl
---
author: oompah
created: 2026-07-28 22:14
---
Duplicate screening dispatched (profile: standard, task remains Open)
---
author: oompah
created: 2026-07-28 22:14
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-28 22:14
---
Understanding: Implementing the reserved read-only auditor focus and prompt contract. Plan: (1) explore existing focus/agent infrastructure to understand patterns, (2) add the auditor focus definition excluded from normal triage, (3) add its prompt contract with untrusted delimiters, target contract, and tool schema, (4) add capability policy denying mutating Git/task actions, (5) add tests covering exclusion from triage, required prompt sections, prompt-injection resistance, and tool authorization.
---
author: oompah
created: 2026-07-28 22:17
---
Run #1 [attempt=1, profile=standard, role=standard -> Claude/sonnet]
- Turns: 0, Tool calls: 32
- Tokens: 56 in / 1.5K out [1.6K total]
- Cost: $0.0000
- Exit: terminated, Duration: 2m 36s
- Log: OOMPAH-469__20260728T221438Z.jsonl
---
author: oompah
created: 2026-07-28 22:48
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-28 22:48
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-28 22:50
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 15
- Tokens: 967.4K in / 6.0K out [973.4K total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 12s
- Log: OOMPAH-469__20260728T224828Z.jsonl
---
author: oompah
created: 2026-07-28 22:52
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-28 22:52
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-28 22:53
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 0, Tool calls: 8
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 44s
- Log: OOMPAH-469__20260728T225249Z.jsonl
---
author: oompah
created: 2026-07-28 23:48
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-28 23:48
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-28 23:49
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 14
- Tokens: 545.7K in / 2.9K out [548.7K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 10s
- Log: OOMPAH-469__20260728T234839Z.jsonl
---
author: oompah
created: 2026-07-28 23:49
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-28 23:49
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-28 23:50
---
Understanding: I am implementing the reserved read-only auditor focus and prompt contract. The auditor is a built-in focus with role 'Completion Auditor' that must be explicitly excluded from normal keyword/LLM focus triage. Its prompt must deliver the target contract, trusted task metadata, delimited untrusted descriptions/comments, evidence summary, allowed read/test actions, and the auditor result tool schema. The focus must prohibit file editing, committing, pushing, merging, creating tasks, changing status, or fixing findings. A server-side capability policy must expose read-only repo/test operations plus the result tool while denying mutating task/Git actions. Plan: (1) examine existing capability policy infrastructure, (2) add the auditor focus definition excluded from triage, (3) implement its rendered prompt contract with untrusted delimiters, (4) add the capability policy, (5) add comprehensive tests covering exclusion from triage, required prompt sections, prompt-injection resistance, and tool authorization.
---
author: oompah
created: 2026-07-28 23:51
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 0, Tool calls: 23
- Tokens: 376 in / 74 out [450 total]
- Cost: $0.0000
- Exit: terminated, Duration: 1m 11s
- Log: OOMPAH-469__20260728T234959Z.jsonl
---
author: oompah
created: 2026-07-29 00:07
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-29 00:07
---
Focus: Security Auditor
---
author: oompah
created: 2026-07-29 00:33
---
Agent completed successfully in 1548s (27734694 tokens)
---
author: oompah
created: 2026-07-29 00:33
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 168
- Tokens: 27.7M in / 54.4K out [27.7M total]
- Cost: $0.0000
- Exit: normal, Duration: 25m 48s
- Log: OOMPAH-469__20260729T000722Z.jsonl
---
author: oompah
created: 2026-07-29 00:33
---
Agent completed without closing this issue (1548s (27734694 tokens)). Escalating from 'default' to 'standard'. Retrying in 10s (1/3).
---
author: oompah
created: 2026-07-29 00:34
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-29 00:34
---
Focus: Security Auditor
---
author: oompah
created: 2026-07-29 00:35
---
Recovered the completed worker handoff after its in-agent CLI received HTTP 401. Commit 4ee93839f is pushed on epic-OOMPAH-458; the branch is clean. Verification recorded by the worker: 393 focused auditor/prompt/authority tests and 188 ACP backend tests passed; Ruff and git diff checks passed. A redundant redispatch on the still-Open tracker record was stopped by completing this handoff.
---
author: oompah
created: 2026-07-29 00:35
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 0, Tool calls: 4
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 39s
- Log: OOMPAH-469__20260729T003443Z.jsonl
---
author: oompah
created: 2026-07-29 00:35
---
Implemented and pushed reserved auditor focus, prompt contract, read-only authority policy, and regression tests in 4ee93839f.
---
author: oompah
created: 2026-08-05 18:22
---
Queued Archived audit: Aged Merged auto-archive (closed 7 days ago). An auditor will review before the task is retired.
---
author: oompah
created: 2026-08-05 18:49
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-08-05 18:49
---
Focus: Completion Auditor
---
<!-- COMMENTS:END -->
