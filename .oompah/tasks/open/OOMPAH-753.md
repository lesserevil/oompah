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
updated_at: '2026-08-04T02:04:47.174169Z'
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
  evidence: ''
  claim_id: 8176b80e-a5b9-4de5-9316-c0a6f9ceb4c5
  claim_owner: 1c23f4c6-4c13-43af-86f6-1edf14468b70
  claimed_at: '2026-08-04T02:04:37.314155+00:00'
  claim_expires_at: '2026-08-04T02:34:37.314155+00:00'
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: ae9a47db-7783-47e9-b959-e820e3255e58
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
<!-- COMMENTS:END -->
