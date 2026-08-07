---
id: OOMPAH-872
type: bug
status: In Progress
priority: 1
title: Resolve the service checkout to a safe management project for operational error
  filing
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-07T05:27:00.661610Z'
updated_at: '2026-08-07T07:27:38.992290Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 2cfe576018288934d70a7eab658c211eff3f8f9ee5438660a1072303e84d4ff3
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-07T07:17:59.454529+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: No active duplicate was confirmed. Closest reviewed tasks\u2014\
    OOMPAH-15 and OOMPAH-156\u2014are Archived and address different ErrorWatcher\
    \ behavior; OOMPAH-161 is also Archived and concerns project-name lookup, not\
    \ safe repository-identity resolution.\nFocus handoff: duplicate_detector  \n\
    Duplicate preflight verdict: no_duplicate  \nMatches: none  \n\nEvidence: No active\
    \ duplicate was confirmed. Closest reviewed tasks\u2014OOMPAH-15 and OOMPAH-156\u2014\
    are Archived and address different ErrorWatcher behavior; OOMPAH-161 is also Archived\
    \ and concerns project-name lookup, not safe repository-identity resolution."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 8c5fcabf-5ae6-40af-9a88-12f8dddb6bbc
oompah.task_costs:
  total_input_tokens: 47922
  total_output_tokens: 212
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 47922
      output_tokens: 212
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 47922
    output_tokens: 212
    cost_usd: 0.0
    recorded_at: '2026-08-07T07:17:59.432425+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-872__20260807T071650Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-872
    source_sha: 45e2b83356dd041200d7cad0970c7e6f939dc757
    completed_at: '2026-08-07T07:17:59.496533+00:00'
---
## Summary

At service startup from /home/shedwards/src/oompah, the global backend/frontend ErrorWatcher cannot select a safe management tracker because the configured managed project repo_path is /home/shedwards/.oompah/repos/oompah. It therefore disables operational error-task creation even though the Oompah project is registered and project log watchers remain active. Implement identity-safe checkout-to-project resolution for service/runtime clones without weakening OOMPAH-511/OOMPAH-512/OOMPAH-514 fail-closed protections. Prefer durable canonical repository identity and explicit configured management-project authority over path coincidence; reject ambiguous or foreign matches. Relevant code: service startup ErrorWatcher wiring, project repository identity/path resolution, management tracker selection, startup health/alerts. Required tests: canonical service clone maps to the one configured Oompah project; cached mirror and agent worktree aliases resolve only with matching repository identity; ambiguous matches disable filing with an actionable diagnostic; foreign/unmanaged clones remain rejected; restart retains the mapping. Acceptance: the normal production checkout enables backend/frontend operational task filing to the intended project, while unsafe or ambiguous topologies still fail closed.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-07 07:16
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-07 07:16
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-07 07:18
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 47.9K in / 212 out [48.1K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 47s
- Log: OOMPAH-872__20260807T071650Z.jsonl
---
author: oompah
created: 2026-08-07 07:26
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-07 07:26
---
Focus: Oompah Tests Auth Specialist
---
author: oompah
created: 2026-08-07 07:26
---
Understanding: the service ErrorWatcher must map its runtime checkout to the explicitly configured Oompah management project using durable repository identity, while rejecting ambiguous or foreign matches and preserving fail-closed protections. I will trace startup wiring and project identity resolution, implement focused resolver changes, add regression tests for canonical/alias/ambiguous/foreign/restart cases, then run focused checks.
---
author: oompah
created: 2026-08-07 07:27
---
Discovery: Orchestrator._management_tracker_scope in oompah/orchestrator.py:3990-4022 uses exact workflow-root/path coincidence. The global tracker is deliberately fail-closed in managed mode, and server.set_orchestrator disables the global ErrorWatcher when this scope lookup raises. I will add durable git repository identity matching with explicit management-project authority and retain strict ambiguity/foreign rejection.
---
<!-- COMMENTS:END -->
