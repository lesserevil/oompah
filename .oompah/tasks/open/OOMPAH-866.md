---
id: OOMPAH-866
type: bug
status: Open
priority: 1
title: Honor canonical child mappings after direct epic conflict rebases
parent: OOMPAH-763
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-06T20:39:34.818552Z'
updated_at: '2026-08-06T20:42:06.383012Z'
work_branch: epic-OOMPAH-763--task-OOMPAH-866
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: f6fa104c55944a49b854bbec75c62de4274454d3c9988840d226afcba8e0b265
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 216bdcef-0fcf-4ba3-8633-01a10785235d
  claim_owner: d499f6a6-5717-4e4a-8ad7-bc38cc47251d
  claimed_at: '2026-08-06T20:40:27.136617+00:00'
  claim_expires_at: '2026-08-06T21:10:27.136617+00:00'
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 507e1570-42af-456d-8dab-4cc33e54ef1a
oompah.work_branch: epic-OOMPAH-763--task-OOMPAH-866
oompah.integration:
  version: 2
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-763--task-OOMPAH-866
  base_branch: epic-OOMPAH-763
  base_sha: 72cc4481c3eee5605345a4a36c3fe688149572b8
  updated_at: '2026-08-06T20:40:43.457732+00:00'
oompah.task_costs:
  total_input_tokens: 10
  total_output_tokens: 3166
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 10
      output_tokens: 3166
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 3166
    cost_usd: 0.0
    recorded_at: '2026-08-06T20:41:56.235275+00:00'
---
## Summary

Fix the shared-epic landing gate regression reproduced by OOMPAH-740 PR 731: child OOMPAH-741 original head d3cc87e was authoritatively conflict-rebased to canonical 0321c898 while preserving current-main validation telemetry, but child validation recognizes only ancestry or git-cherry patch equivalence and reports both OOMPAH-741 and descendant OOMPAH-745 as unlanded. During direct epic rebase, persist durable per-affected-child old range to canonical range evidence with project, epic, child, base, source, target, and generation fencing; consume and validate that evidence in _child_has_durable_landing_evidence and _child_landing_evidence_block_reason without accepting stale, tampered, foreign-epic, tree-only, or unverified mappings. Preserve original SHA provenance and do not require child-ref rewrites. Relevant code: oompah/orchestrator.py direct rebase/canonical landing evidence and shared-child landing validators; existing tests/test_canonical_landing_evidence.py and epic landing suites. Required tests: conflict-resolved direct epic rebase maps the affected child; a descendant shared child does not inherit a false unlanded ancestor; exact unchanged commits still use normal evidence; restart persists mapping; stale/tampered/wrong project or epic evidence fails closed; OOMPAH-740 d3cc87e to 0321c898 scenario allows the epic PR only when every child range is accounted for. Acceptance: PR 731 topology passes landing validation without rewriting child branches, while any genuinely missing child work still blocks merge with an actionable identity.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-06 20:40
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-06 20:40
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-06 20:42
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 3.2K out [3.2K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 21s
- Log: OOMPAH-866__20260806T204102Z.jsonl
---
<!-- COMMENTS:END -->
