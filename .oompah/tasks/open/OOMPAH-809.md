---
id: OOMPAH-809
type: task
status: Open
priority: null
title: Reserve workflow-repair capacity while terminal audits drain
parent: OOMPAH-763
children: []
blocked_by: []
start_blocked_by: &id001
- OOMPAH-768
labels: []
assignee: null
created_at: '2026-08-04T21:49:44.289735Z'
updated_at: '2026-08-04T22:02:44.887986Z'
work_branch: epic-OOMPAH-763--task-OOMPAH-809
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.start_blocked_by: *id001
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: f7f39182d02c06cf016d898dfdba86f8c5f101d264e7e9fcc3a606de6ce6194d
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-04T22:02:38.669210+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: No active task matches the cross-lane capacity starvation\
    \ and bounded terminal-audit scheduling problem. OOMPAH-807 addresses revisionless\
    \ audit lifecycle; OOMPAH-808 addresses stale nested-epic dispatch; OOMPAH-770\
    \ and OOMPAH-768 are broader workflow-engine efforts. Historical terminal tasks\
    \ were excluded.\nFocus handoff: duplicate_detector  \nDuplicate preflight verdict:\
    \ no_duplicate  \nMatches: none  \n\nEvidence: No active task matches the cross-lane\
    \ capacity starvation and bounded terminal-audit scheduling problem. OOMPAH-807\
    \ addresses revisionless audit lifecycle; OOMPAH-808 addresses stale nested-epic\
    \ dispatch; OOMPAH-770 and OOMPAH-768 are broader workflow-engine efforts. Historical\
    \ terminal tasks were excluded."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 3072f981-04cd-4b8b-b25b-0ef059685ea4
oompah.work_branch: epic-OOMPAH-763--task-OOMPAH-809
oompah.integration:
  version: 2
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-763--task-OOMPAH-809
  base_branch: epic-OOMPAH-763
  base_sha: f1e7925b7263f980517f943291102c8c83335ed2
  updated_at: '2026-08-04T21:54:03.548455+00:00'
oompah.task_costs:
  total_input_tokens: 46702
  total_output_tokens: 242
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 46702
      output_tokens: 242
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 46702
    output_tokens: 242
    cost_usd: 0.0
    recorded_at: '2026-08-04T22:02:38.667845+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-809__20260804T215419Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: epic-OOMPAH-763--task-OOMPAH-809
    source_sha: f1e7925b7263f980517f943291102c8c83335ed2
    completed_at: '2026-08-04T22:02:38.699157+00:00'
---
## Summary

Live reproduction on 2026-08-04: OOMPAH-806 occupied one implementation slot while terminal auditors for OOMPAH-793, OOMPAH-527, and OOMPAH-461 filled the remaining usable provider slots. OOMPAH-796, OOMPAH-807, and OOMPAH-808 stayed Open even though OOMPAH-807 repairs the audit lifecycle itself. State advertised effective_max=11, but no implementation dispatch occurred, and recent terminal-audit scan/dispatch phases took roughly 174-201 seconds. This is distinct from merged OOMPAH-749, which bounds historical integration-ledger audit replay before Ready claims; this bug is cross-lane agent-capacity starvation and slow terminal-audit scheduling.\n\nImplementation scope:\n- Add an explicit scheduler lane budget or reservation so terminal audits cannot consume every usable agent/provider slot while runnable implementation or workflow-repair jobs exist. Preserve at least one implementation/control-plane slot, with tunables exposed only as OOMPAH_* values in .env/.env.example.\n- Bound terminal-audit candidate scanning and dispatch work per tick with durable cursors/budgets so audit backlog size cannot create multi-minute scheduler phases.\n- Use the shared WorkDecision/durable-job capacity disposition: capacity waits are informational with a next reassessment, not operator warnings.\n- Preserve terminal-audit progress, project fairness, independent-candidate selection, global concurrency, exact audit ownership, and restart recovery. Do not allow implementation work to starve audits indefinitely either.\n- Expose lane occupancy, reserved capacity, deferred audit count/cursor, oldest runnable implementation age, and bounded phase durations in state metrics.\n\nRelevant code: oompah/orchestrator.py terminal-audit dispatch/scans and _available_slots scheduling; oompah/config.py and .env.example; workflow-job scheduling/WorkDecision capacity reasons; state metrics and alert projection. Coordinate with OOMPAH-781/796/804 rather than creating a parallel lifecycle.\n\nRequired tests:\n- With all general slots apparently available to an audit backlog and a runnable implementation repair, at least one implementation slot is preserved and the repair dispatches within one bounded scheduler interval.\n- Hundreds of pending audits are scanned/dispatched incrementally across ticks/restart without duplicate ownership or lost progress.\n- Audit and implementation lanes both make fair bounded progress across projects; configured low concurrency (including one slot) remains safe and explicit.\n- Capacity waits remain informational and clear automatically; genuine exhausted recovery remains actionable.\n- Focused scheduler/auditor/config/state tests plus make test pass.\n\nAcceptance criteria: runnable workflow-repair work cannot be indefinitely starved by terminal-audit backlog; audits still advance fairly; terminal-audit scheduling phases are bounded independently of backlog size; state explains lane deferral without a false global warning.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-04 21:53
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-04 21:54
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-04 22:02
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 46.7K in / 242 out [46.9K total]
- Cost: $0.0000
- Exit: normal, Duration: 8m 45s
- Log: OOMPAH-809__20260804T215419Z.jsonl
---
<!-- COMMENTS:END -->
