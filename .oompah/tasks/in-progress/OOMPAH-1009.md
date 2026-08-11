---
id: OOMPAH-1009
type: bug
status: In Progress
priority: 1
title: Prevent terminal-audit churn from starving restart workflow publication
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-11T01:46:41.855802Z'
updated_at: '2026-08-11T03:05:33.265676Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.create_once:
  version: 1
  project_id: proj-14849f1b
  operation_kind: api_task_create
  creation_marker: oompah-1007-restart-publication-audit-livelock
  request_fingerprint: 56211e72ee6c928596d6a0a03326c7af1effd81070a90595f4617bc17cc3e15b
---
## Summary

Triggered by: OOMPAH-1007

Live reproduction on deployed main f9060c80e after graceful restart: workflow liveness remained restart_overdue with reconstruction_pending=true, current exhausted/quarantined/action_required all zero, and OOMPAH-1007 terminal audits active. _run_durable_workflow_tick dispatches the terminal-audit lane before WorkflowRuntime.reconcile_async. The auditor then writes comments/status metadata while the long whole-world restart publication is collecting tracker authority, so tracker_publication_revision becomes unavailable or changes and the publication is superseded with requires_reconcile=true. The coalesced retry runs, but can launch another auditor first and invalidate itself again, producing a restart publication livelock until audit churn stops. Scope: give restart reconstruction/reconciliation publication priority over terminal-audit launch, or install an equivalent exact fence so an audit started by a tick cannot invalidate that tick's optimistic publication window. Preserve fail-closed tracker CAS, bounded event continuations, audit capacity/fairness, paused-project semantics, terminal authority binding, and ordinary post-restart audit recovery. Relevant code: Orchestrator._run_durable_workflow_tick ordering and continuation requests, WorkflowRuntime publication authority capture, terminal-audit dispatch admission, and restart liveness recovery. Required tests: production-shaped restart with a pending terminal audit whose dispatch mutates tracker authority; prove a complete accepted liveness publication occurs within the restart deadline without owner intervention, the audit then launches exactly once, publication supersession remains safe for genuinely concurrent external writes, continuation events stay coalesced/bounded, and pause/restart paths remain safe. Include a control with repeated auditor comments/results and a multi-minute-equivalent slow scan. Acceptance: make workflow-rollout-check reaches healthy after restart with OOMPAH-1007-like pending audits; no restart_overdue livelock, duplicate auditor launch, current divergence/exhaustion, or action-required alert remains.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-11 02:16
---
Claimed for direct-owner implementation in the current systemic workflow recovery program. Work will be isolated on this task branch, covered by focused regression tests, independently reviewed, fully gated, pushed, and submitted through the protected delivery path.
---
author: oompah
created: 2026-08-11 02:32
---
Implementation is committed and pushed at exact head 47e2777a8539baf66d4201d314a0a2868bf82137. Enforce-mode restart reconstruction now prioritizes the first accepted liveness publication; audit rollback/finalization/migration/health remain active while only fresh provider ownership is neutrally deferred. Healthy and off/shadow modes retain audit-first fairness. Exact-head validation passed 593 targeted tests, mutation scan 21/21, secret scan, compile, and diff checks. Independent review is active before protected integration.
---
author: oompah
created: 2026-08-11 03:05
---
Independent re-review accepted exact head 43a0d794ae1ac5dde5fb0005a7455878caef9d46 with no findings. Recovery/finalization now precede potentially failing reconciliation, restart reconciliation suppresses ordinary worker admission, fresh audit launch remains ahead of continuation admission, and a real two-tick authority-CAS regression proves supersession then convergence with exactly one provider launch. The combined four-fix branch passed 827 changed-path tests.
---
<!-- COMMENTS:END -->
