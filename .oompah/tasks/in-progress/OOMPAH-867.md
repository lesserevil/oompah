---
id: OOMPAH-867
type: task
status: In Progress
priority: null
title: Use canonical epic branches for terminal-audit workspace resolution
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-06T22:21:55.244164Z'
updated_at: '2026-08-06T22:25:28.039844Z'
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
oompah.agent_run_id: 554c1f0e-e780-453e-b715-8f0473048bc4
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
author: oompah
created: 2026-08-06 22:24
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-06 22:24
---
Focus: Oompah Tests Auth Specialist
---
author: oompah
created: 2026-08-06 22:24
---
## Understanding

This is a release-blocking regression where terminal-audit evidence fingerprinting and workspace creation diverge on canonical epic branch resolution. The fingerprinting correctly resolves epic-OOMPAH-768, but _create_workspace_for_auditor uses different logic and fails to find it, causing infrastructure exhaustion and moving completed epics to Needs Human.

**Plan:**
1. Explore current terminal_audit.py fingerprinting logic and how it resolves canonical epic branches
2. Examine _create_workspace_for_auditor in orchestrator.py and understand its current candidate resolution
3. Design a unified, typed revision candidate resolver with ordered precedence: immutable SHA → work/source/integration branches → canonical epic branch → nested shared/private parent → authorized merged/archive fallback
4. Extract the resolver into a reusable component shared by both fingerprinting and workspace creation
5. Persist and compare exact SHA to prevent divergence across restarts
6. Add comprehensive tests for standalone/nested epics, absent candidates, immutable SHA handling, and parity between fingerprint/workspace
7. Verify ordinary tasks remain unchanged

**My expertise:** API/integration boundaries, clear interfaces, authorization/access control - I'll ensure the unified resolver is a clean, testable abstraction with proper validation and error handling.

Starting exploration now.
---
author: oompah
created: 2026-08-06 22:25
---
## Discovery

Found the root cause of the divergence:

**terminal_audit.py** (fingerprinting):
- Has \`_resolve_epic_branch_names()\` function that resolves canonical epic branches (epic-OOMPAH-768) 
- Uses it in \`compute_issue_evidence_fingerprint()\` as a fallback when no explicit work_branch
- For standalone epic without work_branch: tries epic-EPIC-ID
- For nested epic with parent: tries epic-PARENT-ID, then epic-EPIC-ID

**orchestrator.py _create_workspace_for_auditor()** (workspace creation):
- Builds candidates from: source_sha, integrated_sha, head_sha, target_sha
- Then: source_branch, work_branch, integration.task_branch, branch_name
- Then: origin/default_branch (if allowed)
- **Missing**: canonical epic branch resolution (epic-OOMPAH-768)

Result: For a standalone epic with no work_branch:
- Fingerprint: epic-OOMPAH-768 ✓
- Workspace: tries origin/OOMPAH-768 only ✗

Relevant code sections:
- terminal_audit.py lines 738-768 (_resolve_epic_branch_names)
- terminal_audit.py lines 920-1070 (compute_issue_evidence_fingerprint uses it)
- orchestrator.py lines 17561-17680 (_create_workspace_for_auditor has no epic branch logic)

Next: Create unified revision candidate resolver with ordered precedence.
---
<!-- COMMENTS:END -->
