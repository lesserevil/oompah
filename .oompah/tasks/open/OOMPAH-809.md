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
updated_at: '2026-08-04T21:50:39.601189Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.start_blocked_by: *id001
---
## Summary

Live reproduction on 2026-08-04: OOMPAH-806 occupied one implementation slot while terminal auditors for OOMPAH-793, OOMPAH-527, and OOMPAH-461 filled the remaining usable provider slots. OOMPAH-796, OOMPAH-807, and OOMPAH-808 stayed Open even though OOMPAH-807 repairs the audit lifecycle itself. State advertised effective_max=11, but no implementation dispatch occurred, and recent terminal-audit scan/dispatch phases took roughly 174-201 seconds. This is distinct from merged OOMPAH-749, which bounds historical integration-ledger audit replay before Ready claims; this bug is cross-lane agent-capacity starvation and slow terminal-audit scheduling.\n\nImplementation scope:\n- Add an explicit scheduler lane budget or reservation so terminal audits cannot consume every usable agent/provider slot while runnable implementation or workflow-repair jobs exist. Preserve at least one implementation/control-plane slot, with tunables exposed only as OOMPAH_* values in .env/.env.example.\n- Bound terminal-audit candidate scanning and dispatch work per tick with durable cursors/budgets so audit backlog size cannot create multi-minute scheduler phases.\n- Use the shared WorkDecision/durable-job capacity disposition: capacity waits are informational with a next reassessment, not operator warnings.\n- Preserve terminal-audit progress, project fairness, independent-candidate selection, global concurrency, exact audit ownership, and restart recovery. Do not allow implementation work to starve audits indefinitely either.\n- Expose lane occupancy, reserved capacity, deferred audit count/cursor, oldest runnable implementation age, and bounded phase durations in state metrics.\n\nRelevant code: oompah/orchestrator.py terminal-audit dispatch/scans and _available_slots scheduling; oompah/config.py and .env.example; workflow-job scheduling/WorkDecision capacity reasons; state metrics and alert projection. Coordinate with OOMPAH-781/796/804 rather than creating a parallel lifecycle.\n\nRequired tests:\n- With all general slots apparently available to an audit backlog and a runnable implementation repair, at least one implementation slot is preserved and the repair dispatches within one bounded scheduler interval.\n- Hundreds of pending audits are scanned/dispatched incrementally across ticks/restart without duplicate ownership or lost progress.\n- Audit and implementation lanes both make fair bounded progress across projects; configured low concurrency (including one slot) remains safe and explicit.\n- Capacity waits remain informational and clear automatically; genuine exhausted recovery remains actionable.\n- Focused scheduler/auditor/config/state tests plus make test pass.\n\nAcceptance criteria: runnable workflow-repair work cannot be indefinitely starved by terminal-audit backlog; audits still advance fairly; terminal-audit scheduling phases are bounded independently of backlog size; state explains lane deferral without a false global warning.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

