---
id: OOMPAH-809
type: task
status: Done
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
updated_at: '2026-08-09T20:14:09.677189Z'
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
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-99b285f7c52f
    project_id: proj-14849f1b
    task_id: OOMPAH-809
    target_state: Done
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: cb54242eb68658cc9724f994f62682ca52a07854e13e8b5ec8a3c7a2c1cefc3a
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: Systemic composition delivered and deployed at d796a4be9a7b0f2dd079cef8ce17e6ec6ecfd62d;
      exact-head make test passed (18,744 passed, 7 skipped, 2 xfailed; artifact /home/shedwards/.oompah/tmp/OOMPAH-763-full-d796a4b.R3hV9b).
      This task scope is contained in that validated head; owner override avoids fabricating
      a separate branch/integration generation.
    created_at: '2026-08-08T16:27:05.693552+00:00'
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-809
    target_state: Done
    evidence_fingerprint: cb54242eb68658cc9724f994f62682ca52a07854e13e8b5ec8a3c7a2c1cefc3a
    audit_ids: []
    kind: override
    applied: true
    retired_at: '2026-08-08T16:27:14.809002+00:00'
  oompah.terminal_audit_result_intents: []
  oompah.terminal_provenance_suppression:
    version: 1
    suppressed: true
    authority_generation: 0
    reason: Project owner confirms OOMPAH-809 is a completed historical/provenance-only
      legacy record; this is not a landing claim.
    marked_at: '2026-08-09T20:14:08.044745+00:00'
    updated_at: '2026-08-09T20:14:08.044745+00:00'
    history:
    - kind: mark
      actor:
        version: 1
        identity: oompah-cli
        source: api
      reason: Project owner confirms OOMPAH-809 is a completed historical/provenance-only
        legacy record; this is not a landing claim.
      recorded_at: '2026-08-09T20:14:08.044745+00:00'
      authority_generation: 0
    actor:
      version: 1
      identity: oompah-cli
      source: api
  version: 1
  pending_chain: []
  attempt_history: []
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
author: oompah
created: 2026-08-04 22:03
---
Additional live evidence at 22:02 UTC: the most recent scheduler tick took 562,919 ms. audit_scan/audit_dispatch alone consumed 303,441 ms, reconcile consumed 108,265 ms, and integration-queue maintenance has not run since 21:45:48. OOMPAH-781/782/791 were unblocked when OOMPAH-793 became Done at 22:02, but their ready rows remained attempts=0/unleased because the shared scheduler lane had not reached integration maintenance. The repair must bound audit work so integration/durable workflow jobs also receive a bounded service interval; lane reservation only at agent launch is insufficient.
---
author: oompah
created: 2026-08-04 23:03
---
Additional live evidence after OOMPAH-806 integrated at 23:01 UTC: the next scheduler tick still took 412,653 ms. audit_scan/audit_dispatch consumed 240,789 ms, reconcile 104,591 ms, and watchdog 11,582 ms. Six historical terminal auditors occupied provider capacity while newly integrated OOMPAH-806 remained queued without an auditor; OOMPAH-811 duplicate screening also consumed the only non-audit worker slot. OOMPAH-812 could start its exact gate only after this multi-minute tick. This confirms both bounded audit scanning and reserved control/repair capacity are required.
---
author: oompah
created: 2026-08-06 03:54
---
New fe6257b live evidence after OOMPAH-826 exact-gate completion: /healthz accepted a connection but returned no body within a 2-second probe while the server main thread was CPU-bound. The subsequent state snapshot reported total_ms=364394 and dispatch_ms=354332, including audit_scan/audit_dispatch=2909ms, candidate_selection=3227ms, normal_dispatch=11535ms, and duplicate_preflight_dispatch=10944ms, yet health.status still reported healthy. The endpoint recovered about five seconds later. This is another concrete multi-minute scheduler service-interval violation for OOMPAH-809; bound all unaccounted dispatch work and ensure health/liveness projection cannot call a 364-second tick healthy.
---
author: oompah
created: 2026-08-08 08:29
---
Direct implementation complete at c91f12888 on the systemic base. The scheduler now selects authoritative runnable non-audit work before audit launch, reserves configurable implementation/control-plane capacity, and durably alternates audit/implementation turns at total concurrency one. Audit scanning rotates through a persisted cursor, launch attempts have a separate per-tick cap, and state exposes reservation, lane occupancy, deferred count/cursor, and oldest runnable implementation age. Configured partial scans are informational; actual tracker scan failures remain actionable. Focused config/audit-health/audit-observability/tick/lane matrix: 293 passed in 64.35s. Diff/compile and full secret scan are clean. Awaiting composition and exact-head full gate before terminalization.
---
author: oompah
created: 2026-08-08 16:27
---
Override by oompah-cli: terminal transition to Done applied by project owner.

Reason: Systemic composition delivered and deployed at d796a4be9a7b0f2dd079cef8ce17e6ec6ecfd62d; exact-head make test passed (18,744 passed, 7 skipped, 2 xfailed; artifact /home/shedwards/.oompah/tmp/OOMPAH-763-full-d796a4b.R3hV9b). This task scope is contained in that validated head; owner override avoids fabricating a separate branch/integration generation.
---
<!-- COMMENTS:END -->
