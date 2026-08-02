---
id: OOMPAH-701
type: bug
status: Backlog
priority: 1
title: Retire hidden provider processes when task ownership is revoked
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-02T20:20:26.676545Z'
updated_at: '2026-08-02T20:20:26.676545Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Triggered by: OOMPAH-698

Production reproduction on 2026-08-02: after OOMPAH-700 was moved out of automatic dispatch and claimed for direct owner work, the public agent list became empty but its Claude provider process remained a child of the server with the OOMPAH-700 prompt. At the same time OOMPAH-698 remained In Validation with terminal-audit metrics reporting queued=1 and running=0 while a live auditor provider process repeatedly triggered auditor_shell_mutation authority denials. These hidden processes survived after scheduler ownership disappeared and left lifecycle state and observability contradictory.\n\nImplementation scope:\n- Keep an authoritative run/session record until every provider subprocess actually exits; never remove a run from agents or audit running metrics merely because task state or scheduler ownership changed.\n- When a task is reopened, reassigned, directly claimed, superseded, or otherwise loses the run generation, cancel and await the exact provider process group with bounded escalation and persisted recovery evidence.\n- Bound repeated read-only auditor policy denials; fail the attempt and enter the normal independent retry path instead of allowing an invisible model loop.\n- Reconcile orphaned provider children during startup and graceful restart without killing unrelated current-generation runs.\n- Make UI agent state, terminal-audit queued/running counters, claimed issue ownership, and actual OS process liveness converge atomically.\n\nRelevant code: oompah/orchestrator.py run ownership and worker exit paths; oompah/terminal_audit.py dispatch and retry bookkeeping; oompah/agent.py and provider adapters process lifecycle; service-state and dashboard agent/audit metrics.\n\nRequired tests:\n- Transition an implementation task away from an active run and prove its provider process exits before the agent record is retired.\n- Reproduce an auditor repeatedly requesting a disallowed mutation and prove the attempt terminates, records a bounded failure, and retries through a different eligible candidate.\n- Simulate the state-change versus provider-exit race and prove no hidden child or stale claim remains.\n- Restart with an orphaned provider child and prove deterministic cleanup plus persisted audit recovery.\n- Assert agent UI state and terminal-audit running metrics remain truthful throughout cancellation and exit.\n\nAcceptance criteria:\n- No provider process survives without a visible current-generation run record.\n- OOMPAH-698 style audits cannot remain In Validation with queued/running metrics that contradict a live provider process.\n- Graceful restart drains or terminates every superseded provider process and retries durable pending work exactly once.\n- Focused race tests and make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

