---
id: OOMPAH-286
type: task
status: In Progress
priority: 1
title: Define the external-content trust model and prompt-injection threat model
parent: OOMPAH-285
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-21T14:51:39.881239Z'
updated_at: '2026-07-21T15:45:25.415354Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: af45a5d2-e5c3-4df8-ba60-a98bad6b2106
---
## Summary

Create plans/prompt-injection-protection.md defining trusted versus untrusted sources, trust propagation, attack scenarios, protected actions, boundaries, and non-goals. Inventory every current path from GitHub issues/comments, PR metadata, webhooks, CI/log text, repository files, and attachments into LLM or agent prompts. Specify a machine-readable provenance contract for later tasks.

Tests: add a documentation/contract test asserting the inventory names the intake bridge, focus triage, prompt renderer, continuation prompts, and agent system prompt construction.

Acceptance criteria: a developer can determine whether a new input is untrusted, how it is labeled and delimited, and which server-side controls remain authoritative.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-21 15:45
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-21 15:45
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-21 15:45
---
Understanding: I will first perform the required duplicate screening for this prompt-injection trust-model task by searching internal tasks and design docs, then reading any candidate task records before deciding whether it is a duplicate.
---
<!-- COMMENTS:END -->
