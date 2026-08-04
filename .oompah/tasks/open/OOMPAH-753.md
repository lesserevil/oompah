---
id: OOMPAH-753
type: bug
status: Open
priority: 1
title: Keep denied non-mutating validator requests recoverable for terminal auditors
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-04T02:03:10.235988Z'
updated_at: '2026-08-04T02:06:32.665549Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 1e1a9046dd4acfb0dbe57f6a0b46d6b1c6201c151525cb893dd9f2792744659e
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: inconclusive\n\
    Matches: none\nEvidence: OOMPAH-753 describes a live regression in terminal auditor\
    \ denial-budget handling where non-mutating validator requests (focused pytest\
    \ commands) outside the project validation contract are incorrectly consuming\
    \ fatal policy budget, terminating the auditor prematurely. The issue explicitly\
    \ references OOMPAH-731 (the merged task that triggered this) and OOMPAH-736 (the\
    \ fix that introduced the regression). However, neither OOMPAH-731 nor OOMPAH-736\
    \ appear in the supplied corpus. The corpus shows 30 similarity candidates (all\
    \ in Archived terminal state) and notes omitted_similarity_candidate_count: 543.\
    \ None of the 30 provided candidates address auditor denial budgets, policy-contract\
    \ validation mismatches, or terminal-audit candidate recovery\u2014they cover\
    \ unrelated domains (tracker sync, release addendums, epic workflows, dashboard\
    \ UI). The structural peer tasks that directly caused and introduced this regression\
    \ cannot be evaluated. Recommend retry with full corpus including OOMPAH-731 an\n\
    Focus handoff: duplicate_detector\n\nDuplicate preflight verdict: inconclusive\n\
    \nMatches: none\n\nEvidence: OOMPAH-753 describes a live regression in terminal\
    \ auditor denial-budget handling where non-mutating validator requests (focused\
    \ pytest commands) outside the project validation contract are incorrectly consuming\
    \ fatal policy budget, terminating the auditor prematurely. The issue explicitly\
    \ references OOMPAH-731 (the merged task that triggered this) and OOMPAH-736 (the\
    \ fix that introduced the regression). However, neither OOMPAH-731 nor OOMPAH-736\
    \ appear in the supplied corpus. The corpus shows 30 similarity candidates (all\
    \ in Archived terminal state) and notes omitted_similarity_candidate_count: 543.\
    \ None of the 30 provided candidates address auditor denial budgets, policy-contract\
    \ validation mismatches, or terminal-audit candidate recovery\u2014they cover\
    \ unrelated domains (tracker sync, release addendums, epic workflows, dashboard\
    \ UI). The structural peer tasks that directly caused and introduced this regression\
    \ cannot be evaluated. Recommend retry with full corpus including OOMPAH-731 and\
    \ OOMPAH-736, or with the omitted 543 similarity candidates, to definitively confirm\
    \ whether an active duplicate exists in the auditor policy/health system."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 1
  retry_after: '2026-08-04T02:07:09.978007+00:00'
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: ae9a47db-7783-47e9-b959-e820e3255e58
oompah.task_costs:
  total_input_tokens: 10
  total_output_tokens: 2535
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 10
      output_tokens: 2535
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 2535
    cost_usd: 0.0
    recorded_at: '2026-08-04T02:06:09.974209+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-753__20260804T020449Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-753
    source_sha: 18e18a6b63b2f9a522b17c0132dac0f5a0d9e487
    completed_at: '2026-08-04T02:06:09.985128+00:00'
---
## Summary

Triggered by: OOMPAH-731

Live regression after merged OOMPAH-736 on OOMPAH-731 Merged audit attempt OOMPAH-731__20260804T014819Z. The sole contributor-independent Opus auditor verified exact HEAD, origin/main history, PR 696 merge ancestry, and the implemented symbols. It then requested a focused pytest command with output truncation and a simple direct pytest command. Both are non-mutating validation requests but outside the structured project validation contract, so enforcement denied them. Those two denials consumed the fatal policy budget and terminated the auditor immediately after it requested approved make test-fast; candidate exhaustion returned the already-merged task to Needs Human. OOMPAH-736 explicitly requires policy-contract mismatches not to exhaust all candidates, so this is a live regression rather than missing configuration. Implementation scope: classify syntactically non-mutating validator requests outside the advertised contract as recoverable validation mismatches that do not consume the fatal mutation or provider-failure budget; return structured allowed alternatives from the project contract; keep the auditor session alive so it can run an approved Make target or submit a verdict. Align prompt and tool schema so focused verification is requested only through approved templates. Preserve fatal handling for mutation, output-to-file redirection, credential access, path escape, process control, and state-changing git. Relevant code: auditor command classification and project validation contract, ACP run_command result metadata, orchestrator denial-budget handling, terminal-audit candidate retirement, independence selection, and health. Required tests: replay both exact OOMPAH-731 denied commands followed by make test-fast and accepted submit_audit_result; one independent candidate; repeated non-mutating contract mismatches; approved focused Make target; actual mutation and shell escape remain fatal; health distinguishes recoverable mismatch from policy incompatibility and transport failure. Acceptance criteria: replaying the OOMPAH-731 trace reaches a verdict without rotation or Needs Human, while no unapproved command executes and all write-capable commands remain fail closed.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-04 02:04
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-04 02:04
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-04 02:06
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 2.5K out [2.5K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 27s
- Log: OOMPAH-753__20260804T020449Z.jsonl
---
<!-- COMMENTS:END -->
