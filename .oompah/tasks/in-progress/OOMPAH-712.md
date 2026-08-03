---
id: OOMPAH-712
type: task
status: In Progress
priority: null
title: Keep retiring terminal auditors visible until provider exit
parent: null
children: []
blocked_by: []
start_blocked_by: &id001
- OOMPAH-710
labels:
- human-only
assignee: null
created_at: '2026-08-03T00:23:44.424551Z'
updated_at: '2026-08-03T00:24:48.757750Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.start_blocked_by: *id001
---
## Summary

Live post-deployment regression of OOMPAH-701 observed on OOMPAH-706 at 2026-08-03 00:21 UTC. Completion auditor attempt #2 (Claude/Sonnet, pid 2796973) remained alive for roughly a minute after /api/v1/state.running became empty. During the same interval terminal_audit reported queued=1,running=1. The exact provider command/process was confirmed alive under /proc while the dashboard had no agent row. It later exited after the bounded repeated-policy-denial guard, but runtime visibility was false during retirement.\n\nImplementation scope:\n- Trace every auditor normal/forced/policy-denial exit path from RunningEntry removal through ACP session/process retirement.\n- Keep the RunningEntry and its captured provider/process identities in state.running with retirement_pending until every exact descendant has exited, including policy-denial forced termination and SDK cleanup callbacks.\n- Reconcile terminal-audit running metrics from the same live ownership record so agents, health, and gauges cannot contradict each other.\n- Ensure replacement auditor dispatch waits for old provider retirement and cannot share the audit worktree.\n- Preserve OOMPAH-701 behavior for revoked implementation workers and OOMPAH-710 bounded tool-result handling.\n\nRequired tests:\n- A cancellation-resistant terminal auditor reaches the policy-denial stop path; assert the provider remains visible in /api/v1/state until process exit, then disappears exactly once.\n- Assert terminal_audit.running and running auditor rows agree throughout retirement.\n- Assert no replacement auditor launches while the old provider survives.\n- Cover normal ACP exit, forced policy-denial exit, restart drain, and survivor retry cleanup.\n- Focused provider-retirement/auditor-dispatch/observability tests and make test/check-secrets pass.\n\nAcceptance criteria:\n- Replaying the OOMPAH-706 Sonnet sequence never yields a live provider with zero visible running agents.\n- No hidden process, phantom gauge, or overlapping replacement exists at any observed boundary.\n- Runtime cleanup remains bounded and eventual.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-03 00:24
---
Direct owner claim. OOMPAH-710 is a hard prerequisite because it fixes the provider-private spill trigger and stale audit gauge; this task now isolates the remaining lifecycle visibility gap where a live retiring auditor provider outlives its RunningEntry.
---
<!-- COMMENTS:END -->
