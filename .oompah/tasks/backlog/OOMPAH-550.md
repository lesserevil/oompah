---
id: OOMPAH-550
type: epic
status: Backlog
priority: 0
title: Broker durable coordination between concurrent agents
parent: null
children:
- OOMPAH-551
- OOMPAH-552
- OOMPAH-553
- OOMPAH-554
blocked_by: []
labels:
- human-only
assignee: null
created_at: '2026-07-29T16:23:13.053468Z'
updated_at: '2026-07-29T16:24:00.402339Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Goal

Allow concurrently running agents to exchange durable, auditable coordination messages without relying on tracker comments or a specific model provider.

Implementation scope

Create a restart-safe coordination timeline and derived peer suggestion graph from dependencies, epic ancestry, active siblings, and changed-path overlap. Add worker-scoped API/CLI/tools for peers, inbox, send, and checkpoint. Deliver messages at safe live turn boundaries for supported ACP backends with durable fallback for every backend. Generate automatic peer, change, conflict-risk, submission, and integration notices. Add observability, bounded retention, authorization, and loop prevention.

Acceptance criteria

Agents can communicate while running, messages survive restarts, only authorized suggested peers can exchange messages, unavailable live injection falls back without loss, communication never becomes a completion deadlock, conflict-risk peers are notified automatically, and focused tests plus make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-29 16:23
---
Claimed by the interactive Codex session for the owner-requested parallel-epic execution implementation. Keep human-only; do not dispatch another worker. Work will be completed, tested, pushed, and handed off through the parent epic.
---
<!-- COMMENTS:END -->
