---
id: OOMPAH-641
type: task
status: Open
priority: null
title: Finish shared-epic pre-PR and reconciliation hardening from OOMPAH-428
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-31T05:59:48.550048Z'
updated_at: '2026-07-31T06:09:29.247285Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 185422e4b0e806f107adfa94370a37c1fab993031e705aca37b3ace64ccd6271
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-07-31T06:09:21.929728+00:00'
  matched_identifiers: []
  evidence: 'Focus handoff: duplicate_detector


    Duplicate preflight verdict: no_duplicate


    Matches: none


    Evidence: OOMPAH-428 is Archived and explicitly superseded by OOMPAH-641. OOMPAH-426,
    OOMPAH-307, and OOMPAH-501 are terminal adjacent work; active OOMPAH-640 is unrelated
    dispatch-recovery coverage.'
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
oompah.agent_run_id: 1aaa1857-82ca-4ddd-b588-deb35e2e9def
oompah.task_costs:
  total_input_tokens: 1005636
  total_output_tokens: 5072
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 1005636
      output_tokens: 5072
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 1005636
    output_tokens: 5072
    cost_usd: 0.0
    recorded_at: '2026-07-31T06:09:21.929155+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-641__20260731T060717Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-641
    source_sha: bb0fd760c3b2938d15ec2026ef5bfc2fd34b0682
    completed_at: '2026-07-31T06:09:21.941067+00:00'
---
## Summary

Follow-up to incomplete OOMPAH-428 after parent epic OOMPAH-426 and PR #544 merged. Implement the remaining defense-in-depth for shared-epic children. Scope: ensure _ensure_review_exists blocks per-child PR creation even when work_branch is stale to the child identifier; fail closed when parent_id is absent in a partial issue but a parent epic is authoritatively resolvable; verify _create_workspace_for_issue always corrects the in-memory work/branch identity before routing even if metadata persistence fails; and ensure independently merged reconciliation detects a child whose own stale work_branch bypassed its epic. Relevant files: oompah/orchestrator.py, tests/test_epic_strategy.py, and independently-merged reconciliation tests. Required regressions: stale own work_branch with parent_id; missing parent_id but resolvable parent; persistence failure still corrects memory; EXOCOMP-57-style independently merged child detection. Acceptance: no child-to-main PR can be created through these pre-merge edge cases, the invalid merged-child path is actionable, focused epic strategy tests and terminal mutation scan pass, and make test passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-31 06:07
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-31 06:07
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-31 06:09
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 18
- Tokens: 1.0M in / 5.1K out [1.0M total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 9s
- Log: OOMPAH-641__20260731T060717Z.jsonl
---
<!-- COMMENTS:END -->
