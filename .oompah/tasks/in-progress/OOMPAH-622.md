---
id: OOMPAH-622
type: task
status: In Progress
priority: null
title: Reject verdict-incapable Codex CLI auditor sessions
parent: OOMPAH-585
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-30T21:26:15.242500Z'
updated_at: '2026-07-30T21:30:24.886315Z'
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
oompah.agent_run_id: 294fad7c-5c27-4b31-8ce2-e4ddcbe27241
oompah.work_branch: epic-OOMPAH-585--task-OOMPAH-622
oompah.integration:
  version: 1
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-585--task-OOMPAH-622
  base_branch: epic-OOMPAH-585
  base_sha: 58915e5f0b116cf4269f6bb882dd81aa4010ec03
  updated_at: '2026-07-30T21:30:22.234651+00:00'
oompah.task_costs:
  total_input_tokens: 520552
  total_output_tokens: 2888
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 520552
      output_tokens: 2888
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 520552
    output_tokens: 2888
    cost_usd: 0.0
    recorded_at: '2026-07-30T21:30:08.145232+00:00'
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
<!-- COMMENTS:END -->
