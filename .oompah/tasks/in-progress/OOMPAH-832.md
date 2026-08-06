---
id: OOMPAH-832
type: task
status: In Progress
priority: null
title: Bootstrap terminal-auditor inspection contract onto main
parent: null
children: []
blocked_by: []
start_blocked_by: &id001
- OOMPAH-831
labels: []
assignee: null
created_at: '2026-08-05T15:52:49.064850Z'
updated_at: '2026-08-06T18:27:20.354674Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.start_blocked_by: *id001
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 021b424b90fa3b4d4c36d58fb47ac251afa35bc811b0ef3bdeed4c57f7f945bd
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-05T23:59:50.112442+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: OOMPAH-831 is the active implementation task for repairing\
    \ terminal-auditor contracts. OOMPAH-832 is a distinct follow-on deployment/bootstrap\
    \ task requiring porting the reviewed repair onto current main and controlled\
    \ restart validation.\nFocus handoff: duplicate_detector  \nDuplicate preflight\
    \ verdict: no_duplicate  \nMatches: none\n\nEvidence: OOMPAH-831 is the active\
    \ implementation task for repairing terminal-auditor contracts. OOMPAH-832 is\
    \ a distinct follow-on deployment/bootstrap task requiring porting the reviewed\
    \ repair onto current main and controlled restart validation."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: c649b31a-3afd-4fb1-9cf5-3c3fc36d2e60
oompah.task_costs:
  total_input_tokens: 46646
  total_output_tokens: 314
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 46646
      output_tokens: 314
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 46646
    output_tokens: 314
    cost_usd: 0.0
    recorded_at: '2026-08-05T23:59:50.107402+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-832__20260805T235932Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-832
    source_sha: b98ebb40d269ebeb7a134dc43add36bf782d9402
    completed_at: '2026-08-05T23:59:50.115041+00:00'
---
## Summary

Triggered by: OOMPAH-831.

The terminal-auditor search/read/git-inspection contract repair is being implemented on the systemic epic OOMPAH-763 branch, but the running server must audit many intermediate tasks before that root can land. After OOMPAH-831 reaches a reviewed Done state, port the same logical repair patch-equivalently onto then-current main as a standalone deployment bootstrap.

Implementation scope:
- Apply only the reviewed OOMPAH-831 tool-contract, bounded-context, safe read-only git classification, prompt/schema, and health-classification changes to current main.
- Reconcile main-only changes without broadening auditor write authority, arbitrary-code execution, network/credential access, path scope, or allowed mutation surface.
- Preserve exact task/audit identity, output bounds, timeout/cancellation behavior, backend parity, and recoverable-versus-fatal denial accounting.

Required tests:
- Run the complete OOMPAH-831 focused auditor/ACP/output/policy/health matrix against the standalone composition.
- Replay the OOMPAH-542 search/read/git-inspection trace and the OOMPAH-815 read-only ref-inspection trace, proving one candidate can reach submit_audit_result without consuming fatal mutation budget.
- Prove arbitrary python -c, redirection, mutation, credential/path escape, process control, and state-changing git remain fatal.
- Run terminal mutation and secret scans plus the configured full Makefile gate.

Acceptance criteria:
- The reviewed standalone head contains no unrelated systemic-epic work and is merged to main.
- A controlled make restart deploys that exact main revision after active agents drain.
- A live terminal audit can use the advertised search/read inspection path without policy-incompatibility health, and no auditor mutation authority is added.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-05 23:59
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-05 23:59
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-05 23:59
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 46.6K in / 314 out [47.0K total]
- Cost: $0.0000
- Exit: normal, Duration: 30s
- Log: OOMPAH-832__20260805T235932Z.jsonl
---
author: oompah
created: 2026-08-06 18:27
---
Agent dispatched (profile: default)
---
<!-- COMMENTS:END -->
