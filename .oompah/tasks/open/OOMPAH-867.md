---
id: OOMPAH-867
type: task
status: Open
priority: null
title: Use canonical epic branches for terminal-audit workspace resolution
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-06T22:21:55.244164Z'
updated_at: '2026-08-06T22:23:39.984565Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 7ed010ec83df7aee6b7a686c688bf468afb4b0622425498a3b4babafcbde5cdd
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-06T22:23:29.140514+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: No active duplicate appears in the supplied corpus. Closest\
    \ reviewed tasks\u2014OOMPAH-163, OOMPAH-165, and OOMPAH-168\u2014are terminal\
    \ and address different epic-branch dispatch/landing behavior.\nFocus handoff:\
    \ duplicate_detector  \nDuplicate preflight verdict: no_duplicate  \nMatches:\
    \ none  \n\nEvidence: No active duplicate appears in the supplied corpus. Closest\
    \ reviewed tasks\u2014OOMPAH-163, OOMPAH-165, and OOMPAH-168\u2014are terminal\
    \ and address different epic-branch dispatch/landing behavior."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 0e600d54-41a0-4b4a-88f3-c3371556fd6e
oompah.task_costs:
  total_input_tokens: 46702
  total_output_tokens: 461
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 46702
      output_tokens: 461
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 46702
    output_tokens: 461
    cost_usd: 0.0
    recorded_at: '2026-08-06T22:23:29.139115+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-867__20260806T222306Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-867
    source_sha: f2b319c1182cd654112db622a0498171e508dead
    completed_at: '2026-08-06T22:23:29.153258+00:00'
---
## Summary

Live release-blocking regression reproduced on OOMPAH-768 at 2026-08-06 22:15 UTC: terminal-audit evidence fingerprinting resolves the canonical standalone epic branch epic-OOMPAH-768, but Orchestrator._create_workspace_for_auditor independently builds candidates from source_branch/work_branch/integration.task_branch/branch_name and tries only origin/OOMPAH-768. The published origin/epic-OOMPAH-768 revision is therefore reported as having no safely resolvable revision; two infrastructure attempts exhaust and move the completed parent epic to Needs Human, hard-start blocking OOMPAH-809 and OOMPAH-811. OOMPAH-746 added canonical epic branch resolution to fingerprinting but did not unify detached audit workspace selection. Implementation scope: define one typed, ordered terminal-audit revision candidate resolver consumed by both evidence fingerprinting and detached workspace creation; include immutable SHA precedence, explicit work/source/integration branches, canonical standalone epic branch, nested shared parent branch then private epic fallback, and only the already-authorized merged/archive default fallback. Persist/compare the exact selected revision and SHA so fingerprint and workspace cannot diverge across tracker refresh or restart. Never substitute a branch tip when immutable evidence was recorded. Relevant files: oompah/terminal_audit.py, oompah/orchestrator.py _create_workspace_for_auditor, project branch helpers, tests/test_terminal_audit.py, tests/test_parallel_epic_children.py, and restart audit tests. Required tests: exact OOMPAH-768 standalone epic with no work_branch resolves origin/epic-OOMPAH-768; nested epic shared/private ordering; absent/unavailable candidates fail closed; immutable missing SHA never falls back; fingerprint/workspace parity; restart/retry uses the same exact candidate; ordinary tasks unchanged. Acceptance: completed standalone/nested epics with published canonical branches can enter terminal audit without Needs Human infrastructure exhaustion, and every workspace revision is the same authority represented by the evidence fingerprint.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-06 22:22
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-06 22:22
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-06 22:23
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 46.7K in / 461 out [47.2K total]
- Cost: $0.0000
- Exit: normal, Duration: 36s
- Log: OOMPAH-867__20260806T222306Z.jsonl
---
<!-- COMMENTS:END -->
