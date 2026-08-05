---
id: OOMPAH-824
type: task
status: In Progress
priority: null
title: Bootstrap heavyweight validation arbitration onto main
parent: null
children: []
blocked_by: []
start_blocked_by: &id001
- OOMPAH-816
labels: []
assignee: null
created_at: '2026-08-05T08:20:26.696471Z'
updated_at: '2026-08-05T11:11:48.225310Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.start_blocked_by: *id001
---
## Summary

The currently deployed main server at a165ee90e includes the lifecycle hot-loop repair but not systemic child OOMPAH-816. The oompah project must remain paused because terminal auditors can still launch broad/full pytest commands concurrently with exact BranchQualityGate runs, recreating I/O starvation and nondeterministic gate failures. After OOMPAH-816 reaches Done at an independently reviewed exact head, port the same logical validation-resource-lease commits onto then-current main as a standalone deployment bootstrap. Scope: preserve the process-safe/restart-safe configured validation lease; exact gate priority and cache/authority lock ordering; durable waiter/owner fencing; PID-safe cancellation and descendant handling; strict heavyweight command classification across shell segments/native launchers; post-acquire liveness/runtime accounting; ACP/Codex authority-generation matching; and informational observability. Reconcile main-only changes without broadening authority or copying unrelated epic work. Relevant files include oompah/validation_resource_lease.py, quality_gate.py, api_agent.py, acp_tools.py, codex_agent.py, config.py, orchestrator.py, server.py, native wrapper/launcher helpers, .env.example, and corresponding tests. Required verification: the complete OOMPAH-816 focused lease/gate/liveness/classifier/native/Codex/config/API matrix; explicit exact-gate versus auditor concurrency and crash/restart/cancellation reproducers; terminal mutation scan; secret/diff checks; canonical full make test; independent exact-head review; merge to main; controlled make restart; live proof that a queued auditor cannot launch a competing heavyweight pytest tree. Acceptance: the deployed /healthz revision contains the reviewed OOMPAH-816 lease, normal waits are non-actionable and self-clearing, no unrelated process is terminated, and proj-14849f1b can be safely unpaused for OOMPAH-821/807 and downstream server dispatch.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

