---
id: OOMPAH-763
type: epic
status: Backlog
priority: 1
title: Build a unified, durable, live workflow engine
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels:
- human-only
- architecture
assignee: null
created_at: '2026-08-04T13:54:42.220415Z'
updated_at: '2026-08-04T13:54:42.220415Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Problem: Oompah task progression is currently implemented by multiple local reconcilers, status writers, process-local authority maps, SQLite ledgers, Git/forge probes, watchdogs, and UI-specific eligibility summaries. Safety is generally fail-closed, but no single machine enforces transition legality or guarantees bounded progress, so operators repeatedly file bugs and manually recover stranded nonterminal work. Scope: implement the complete workflow-engine migration: formal lifecycle contract and liveness invariants; a single task-transition service and journal; unified versioned facts and pure WorkDecision evaluator; durable leased workflow jobs with restart-safe sagas; domain cutovers for integration, terminal audit, review, implementation ownership, and epic landing; a universal liveness controller and truthful alerts; model-based/fault-injection/100-task qualification; and final removal of legacy reconcilers plus orchestrator modularization. Preserve the native Markdown tracker as authoritative for user-visible task status, existing terminal safety guarantees, actor authorization, exact-head fencing, project scoping, and restart recovery throughout staged shadow/enforce rollout. Configuration flags must be OOMPAH_* values in .env/.env.example, not WORKFLOW.md. Required verification: focused tests for every child, complete make test at review-ready heads, state-machine safety and eventual-progress properties, kill/restart injection at every persistence boundary, historical incident replays for OOMPAH-562/731/732/739/748/749/751, and a multi-project 100-task soak. Acceptance: one transition writer, one shared decision for scheduler/UI/watchdogs, every nonterminal task has exactly one durable disposition and bounded reassessment, normal automatic recovery is not an operator warning, all historical incidents recover without manual mutation, legacy paths are deleted, and production workflow code is materially reduced after migration.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

