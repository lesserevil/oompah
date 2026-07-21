---
id: OOMPAH-286
type: task
status: In Progress
priority: 1
title: Define the external-content trust model and prompt-injection threat model
parent: OOMPAH-285
children: []
blocked_by: []
labels:
- focus-complete:duplicate_detector
assignee: null
created_at: '2026-07-21T14:51:39.881239Z'
updated_at: '2026-07-21T15:50:34.170009Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: a6bc5819-7944-4cf9-9139-00bd07db8c5e
oompah.task_costs:
  total_input_tokens: 205572
  total_output_tokens: 1674
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 205572
      output_tokens: 1674
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 205572
    output_tokens: 1674
    cost_usd: 0.0
    recorded_at: '2026-07-21T15:46:06.254292+00:00'
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
author: oompah
created: 2026-07-21 15:45
---
Focus handoff: duplicate_detector\n\n1. Outcome: no duplicate confirmed. OOMPAH-286 is the first child of OOMPAH-285 and uniquely defines the trust/threat model plus provenance contract; its deliverable is not implemented by an existing task.\n2. Evidence: searched , , , , and  for prompt injection, trust, provenance, external content, and threat-model terms. Closest reviewed task: OOMPAH-211 (merged), which injects new task/GitHub comments into live ACP sessions; it defines delivery behavior only, not external-content trust, delimiters, provenance, authority boundaries, or the required inventory. Relevant related design references are , , , and .\n3. Remaining work/risks: create , accurately inventory every current prompt path, define machine-readable provenance, and add the specified documentation-contract test. The delivery path from OOMPAH-211 must be included in the inventory.\n4. Recommended next focus: security (threat-model/design documentation with source-path audit and contract test).
---
author: oompah
created: 2026-07-21 15:46
---
Focus handoff: duplicate_detector

1. Outcome: no duplicate confirmed. OOMPAH-286 is the first child of OOMPAH-285 and uniquely defines the trust/threat model plus provenance contract; its deliverable is not implemented by an existing task.
2. Evidence: searched task records, plans, docs, README, and WORKFLOW for prompt injection, trust, provenance, external content, and threat-model terms. Closest reviewed task: OOMPAH-211 (merged), which injects new task/GitHub comments into live ACP sessions; it defines delivery behavior only, not external-content trust, delimiters, provenance, authority boundaries, or the required inventory. Related design references: plans/comment-delivery.md, plans/agentic-focus-triage.md, plans/multimodal-attachments.md, and plans/acp-agent.md.
3. Remaining work/risks: create plans/prompt-injection-protection.md, accurately inventory every current prompt path, define machine-readable provenance, and add the specified documentation-contract test. The delivery path from OOMPAH-211 must be included in the inventory.
4. Recommended next focus: security (threat-model/design documentation with source-path audit and contract test).
---
author: oompah
created: 2026-07-21 15:46
---
Agent completed successfully in 56s (207246 tokens)
---
author: oompah
created: 2026-07-21 15:46
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/default]
- Turns: 1, Tool calls: 6
- Tokens: 205.6K in / 1.7K out [207.2K total]
- Cost: $0.0000
- Exit: normal, Duration: 56s
- Log: OOMPAH-286__20260721T154514Z.jsonl
---
author: oompah
created: 2026-07-21 15:46
---
Focus handoff from `duplicate_detector` is complete. Queued a fresh agent run for the next applicable focus. The next agent should begin with the preceding Focus handoff comment.
---
author: oompah
created: 2026-07-21 15:46
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-21 15:46
---
Focus: Test Engineer
---
author: oompah
created: 2026-07-21 15:46
---
Understanding (Test Engineer): My role is to write the documentation/contract test that asserts plans/prompt-injection-protection.md inventories the required components: intake bridge, focus triage, prompt renderer, continuation prompts, and agent system prompt construction. I will first explore the codebase to understand the test patterns, check if the plan doc exists yet, and then write the test. If the plan doc doesn't exist, I'll write the test so it fails descriptively until a docs agent creates the doc.
---
author: oompah
created: 2026-07-21 15:48
---
Discovery: Found 5 key prompt paths that need to be inventoried: (1) intake bridge (github_intake_bridge.py — imports GitHub issue body/comments into native tasks), (2) focus triage (_build_triage_prompt in focus.py — issue title/desc/labels go into LLM triage call), (3) prompt renderer (render_prompt in prompt.py — renders WORKFLOW.md template with issue data, comments, focus text), (4) continuation prompts (build_continuation_prompt in prompt.py — mid-turn injection via comment delivery), (5) agent system prompt construction (orchestrator.py:15115 — hard-coded system prompt passed to ApiAgentSession). The plan doc plans/prompt-injection-protection.md does not yet exist. I will create both the plan document and the contract test.
---
<!-- COMMENTS:END -->
