---
id: OOMPAH-286
type: task
status: Backlog
priority: 1
title: Define the external-content trust model and prompt-injection threat model
parent: OOMPAH-285
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-21T14:51:39.881239Z'
updated_at: '2026-07-21T14:51:39.881239Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Create plans/prompt-injection-protection.md defining trusted versus untrusted sources, trust propagation, attack scenarios, protected actions, boundaries, and non-goals. Inventory every current path from GitHub issues/comments, PR metadata, webhooks, CI/log text, repository files, and attachments into LLM or agent prompts. Specify a machine-readable provenance contract for later tasks.

Tests: add a documentation/contract test asserting the inventory names the intake bridge, focus triage, prompt renderer, continuation prompts, and agent system prompt construction.

Acceptance criteria: a developer can determine whether a new input is untrusted, how it is labeled and delimited, and which server-side controls remain authoritative.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

