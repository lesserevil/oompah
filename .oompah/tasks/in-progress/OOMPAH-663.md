---
id: OOMPAH-663
type: task
status: In Progress
priority: null
title: Canonicalize integrated-task fingerprints for owner overrides
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-31T13:52:05.961085Z'
updated_at: '2026-07-31T14:07:59.680344Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 9c360850b6c5b27e660228b90dfb195a9e618c097840d9bc4e5d7613b84d84cf
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-07-31T14:04:00.236167+00:00'
  matched_identifiers: []
  evidence: "No repository or tracker mutations were made.\n\nFocus handoff: duplicate_detector\
    \  \nDuplicate preflight verdict: no_duplicate  \nMatches: none  \nEvidence: Active\
    \ OOMPAH-645, OOMPAH-658, and OOMPAH-661 cover transport-health, duplicate-preflight,\
    \ and retry-authority issues respectively. Closest terminal records OOMPAH-604,\
    \ OOMPAH-577, OOMPAH-626, OOMPAH-627, and OOMPAH-653 are Done/Merged and therefore\
    \ excluded; their scopes differ from this canonical integrated-evidence fingerprint\
    \ bug."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
oompah.agent_run_id: 8d63f73f-78c2-4e47-97e1-e15c730c90cd
oompah.task_costs:
  total_input_tokens: 3662929
  total_output_tokens: 8902
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 3662929
      output_tokens: 8902
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 3662929
    output_tokens: 8902
    cost_usd: 0.0
    recorded_at: '2026-07-31T14:04:00.235023+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-663__20260731T140033Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-663
    source_sha: ef2938146bf828ddc8d8d677501f4fad61d65a73
    completed_at: '2026-07-31T14:04:00.251325+00:00'
---
## Summary

Bug reproduction: OOMPAH-660 was integrated at 793bcc7969d39634dab560ed0a10b9dcad7a9716, but its integration-staged Done audit fingerprinted the epic branch and a git-branch contributor while the API owner-override path recomputed evidence from the normalized task issue. The legitimate project-owner override therefore failed with HTTP 409 until a duplicate Done request was restaged with the API fingerprint. Implementation scope: define one canonical evidence snapshot/fingerprint path for integrated-task terminal audit creation, API and ACP owner overrides, and restart recovery. Preserve auditor-independence provenance separately if it must not be part of the canonical task evidence. Relevant files include oompah/orchestrator.py, oompah/server.py, oompah/acp_tools.py, oompah/terminal_audit.py, and terminal-transition tests. Add regression coverage that stages an integrated task audit, routes it to Needs Human for no independent candidate, and applies an authorized owner override without restaging; also verify a genuinely changed integration SHA still fails closed. Acceptance criteria: the first valid override succeeds and retires the audit alert, no duplicate terminal request is needed, stale evidence remains rejected, and focused plus full Makefile gates pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-31 14:00
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-31 14:00
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-31 14:04
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 36
- Tokens: 3.7M in / 8.9K out [3.7M total]
- Cost: $0.0000
- Exit: normal, Duration: 3m 30s
- Log: OOMPAH-663__20260731T140033Z.jsonl
---
author: oompah
created: 2026-07-31 14:04
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-31 14:04
---
Focus: Event Api Redaction Specialist
---
author: oompah
created: 2026-07-31 14:04
---
**Understanding & Plan**: The issue reports fingerprint mismatches when OOMPAH-660's integration-staged audit used epic branch + git-branch contributor evidence, but the API owner-override path recomputed evidence from normalized task issue. This HTTP 409 conflict required duplicate restaging. 

Plan: (1) Identify the canonical fingerprinting path used by terminal audit creation, (2) trace how API and ACP owner-override paths diverge from it, (3) unify them to use the same evidence snapshot, (4) preserve auditor-independence provenance separately if needed, (5) add regression tests covering integrated task audit → Needs Human → authorized owner override without restaging, (6) verify changed SHA still fails. Focusing on oompah/orchestrator.py, oompah/server.py, oompah/acp_tools.py, oompah/terminal_audit.py and related tests.
---
author: oompah
created: 2026-07-31 14:07
---
**Discovery**: Reviewed terminal_audit.py, terminal_transition_coordinator.py, acp_tools.py, and server.py. Found:

1. Canonical fingerprint function exists: \`compute_issue_evidence_fingerprint\` in terminal_audit.py
2. Both API paths (acp_tools.py and server.py) already use this canonical function via \`_task_evidence_fingerprint\` and \`_terminal_evidence_fingerprint\`
3. Orchestrator's Done audit staging (orchestrator.py:27443) also uses \`compute_issue_evidence_fingerprint\`
4. Terminal audit enforcement (terminal_audit_enforcement.py) also uses \`compute_issue_evidence_fingerprint\`

The issue appears to be that during integration, the issue object passed to fingerprint computation might contain different evidence data (e.g., epic branch data or git-branch contributor data) compared to when the override is applied later. The fingerprint functions fall back to integration record data when available, so the key is ensuring the SAME issue snapshot is used across all paths (integration staging, API override, and restart recovery).
---
<!-- COMMENTS:END -->
