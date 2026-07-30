---
id: OOMPAH-622
type: task
status: Ready to Integrate
priority: null
title: Reject verdict-incapable Codex CLI auditor sessions
parent: OOMPAH-585
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-30T21:26:15.242500Z'
updated_at: '2026-07-30T21:33:44.293335Z'
work_branch: epic-OOMPAH-585--task-OOMPAH-622
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 358500985d6afae0d9aaba6843d1b29f02c968a20ef02191175e51dc8c18d628
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-07-30T21:30:08.146571+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\n\nDuplicate preflight verdict: no_duplicate\n\
    \nMatches: none\n\nEvidence: Active OOMPAH-281 and OOMPAH-282 are unrelated. Archived\
    \ OOMPAH-28, OOMPAH-30, and OOMPAH-163 concern tracker transitions, decomposition,\
    \ and branch dispatch\u2014not verdict-incapable auditor sessions. No matching\
    \ active duplicate exists."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
oompah.agent_run_id: dff267f8-746d-4da4-b01c-ad139e6facae
oompah.work_branch: epic-OOMPAH-585--task-OOMPAH-622
oompah.integration:
  version: 1
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-585--task-OOMPAH-622
  base_branch: epic-OOMPAH-585
  base_sha: 58915e5f0b116cf4269f6bb882dd81aa4010ec03
  updated_at: '2026-07-30T21:33:13.753946+00:00'
oompah.task_costs:
  total_input_tokens: 521031
  total_output_tokens: 3032
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 521022
      output_tokens: 3008
      cost_usd: 0.0
    sonnet:
      input_tokens: 9
      output_tokens: 24
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 520552
    output_tokens: 2888
    cost_usd: 0.0
    recorded_at: '2026-07-30T21:30:08.145232+00:00'
  - profile: default
    model: haiku
    input_tokens: 470
    output_tokens: 120
    cost_usd: 0.0
    recorded_at: '2026-07-30T21:32:39.974629+00:00'
  - profile: standard
    model: sonnet
    input_tokens: 9
    output_tokens: 24
    cost_usd: 0.0
    recorded_at: '2026-07-30T21:33:41.729562+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-622__20260730T212807Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: epic-OOMPAH-585--task-OOMPAH-622
    source_sha: 58915e5f0b116cf4269f6bb882dd81aa4010ec03
    completed_at: '2026-07-30T21:30:08.153718+00:00'
---
## Summary

Implementation scope: eliminate the terminal-audit dispatch race in which a subscription-backed Codex native CLI session can be selected as a completion auditor even though that transport cannot expose submit_audit_result, leaving a reviewed task permanently In Validation and triggering repeated auditor attempts. Filter only ACP Codex providers using subscription billing from terminal-auditor candidates until that transport has a real verdict channel; preserve Codex API/token-backed auditors and all capable Claude/OpenCode candidates. Independently force every completion-auditor ACP session into read-only mode, including native Codex sandbox/network/additional-directory options, while leaving implementation sessions unchanged. Return an actionable no-capable-candidate diagnostic instead of silently cycling when every configured auditor lacks verdict transport. Relevant files: oompah/auditor_candidate_selector.py, oompah/orchestrator.py, oompah/acp_backends/codex.py as needed, and focused auditor/ACP tests. Tests: reproduce mixed-candidate selection, subscription-only exhaustion, token-backed Codex eligibility, auditor read-only propagation, native CLI sandbox/network behavior, and unchanged implementation dispatch. Acceptance criteria: no verdict-incapable provider is launched as an auditor; all auditor sessions are read-only; capable candidates continue to submit terminal verdicts; focused tests and the combined-tree gate pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-30 21:26
---
Claimed directly by the operator Codex session because the bug itself prevents subscription-backed Codex auditors from completing terminal validation. I will implement, test, push, submit, and prune the temporary worktree.
---
author: oompah
created: 2026-07-30 21:28
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-30 21:28
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-30 21:30
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 11
- Tokens: 520.6K in / 2.9K out [523.4K total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 8s
- Log: OOMPAH-622__20260730T212807Z.jsonl
---
author: oompah
created: 2026-07-30 21:30
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-30 21:30
---
Focus: Software Engineer
---
author: oompah
created: 2026-07-30 21:30
---
Understanding: Implementing filter to reject subscription-backed Codex CLI sessions from auditor candidates, enforce read-only mode for all auditor ACP sessions, and provide actionable diagnostics when no capable candidates exist. Will examine auditor_candidate_selector.py, orchestrator.py, and acp_backends/codex.py.
---
author: oompah
created: 2026-07-30 21:31
---
Discovery: Found key code paths:

1. auditor_candidate_selector.py - has _is_subscription_acp() method, needs filter in _eligible_candidates()
2. orchestrator.py line 21400-21659 - controls auditor ACP session creation, currently read_only only set on duplicate_preflight
3. auditor.py - has AUDITOR_CAPABILITY_POLICY and read_only enforcement
4. Codex backend check needed: _is_subscription_acp() uses mode='acp' and billing_model='subscription'

Planned implementation: 
- Add 'verdict_incapable' reason to NoCandidateReason
- Filter subscription-backed Codex from eligible candidates in auditor selection
- Force read_only=True for all auditor ACP sessions
- Add tests for mixed candidates, subscription exhaustion, and token-backed Codex eligibility
---
author: oompah
created: 2026-07-30 21:32
---
Agent failed: Exception: Command failed with exit code 143 (exit code: 143)
Error output: Check stderr output for details. Retrying in 10s (attempt #1)
---
author: oompah
created: 2026-07-30 21:32
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 58, Tool calls: 29
- Tokens: 470 in / 120 out [590 total]
- Cost: $0.0000
- Exit: error, Duration: 2m 22s
- Log: OOMPAH-622__20260730T213027Z.jsonl
---
author: oompah
created: 2026-07-30 21:32
---
Implemented at ebb5b12d9: subscription-backed Codex native-CLI candidates are excluded from terminal audits with a missing_audit_capability diagnostic; Codex per-token/API and capable ACP backends remain eligible. Every ACP auditor now receives read_only=True at both catalog and session boundaries. Verification: 383 selector/Codex/orchestrator tests passed; 78 audit-dispatch/focus/project-tool tests passed; 10 focused capability/authority regressions passed; terminal mutation scan passed.
---
author: oompah
created: 2026-07-30 21:32
---
Prevented verdict-incapable auditor dispatch and forced ACP auditors into read-only authority, with focused selection, propagation, catalog, and native-sandbox regressions.
---
author: oompah
created: 2026-07-30 21:33
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-30 21:33
---
Focus: Software Engineer
---
author: oompah
created: 2026-07-30 21:33
---
Run #2 [attempt=2, profile=standard, role=standard -> Claude/sonnet]
- Turns: 0, Tool calls: 2
- Tokens: 9 in / 24 out [33 total]
- Cost: $0.0000
- Exit: terminated, Duration: 32s
- Log: OOMPAH-622__20260730T213317Z.jsonl
---
<!-- COMMENTS:END -->
