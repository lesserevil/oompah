---
id: OOMPAH-286
type: task
status: Merged
priority: 1
title: Define the external-content trust model and prompt-injection threat model
parent: OOMPAH-285
children: []
blocked_by: []
labels:
- focus-complete:duplicate_detector
assignee: null
created_at: '2026-07-21T14:51:39.881239Z'
updated_at: '2026-07-21T16:11:21.978830Z'
work_branch: OOMPAH-286
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/466
review_number: '466'
merged_at: null
oompah.agent_run_id: 862aa3ed-662e-41ed-8030-95bf851ebe0c
oompah.task_costs:
  total_input_tokens: 205660
  total_output_tokens: 7712
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 205660
      output_tokens: 7712
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 205572
    output_tokens: 1674
    cost_usd: 0.0
    recorded_at: '2026-07-21T15:46:06.254292+00:00'
  - profile: default
    model: unknown
    input_tokens: 63
    output_tokens: 1657
    cost_usd: 0.0
    recorded_at: '2026-07-21T16:04:43.701419+00:00'
  - profile: standard
    model: unknown
    input_tokens: 25
    output_tokens: 4381
    cost_usd: 0.0
    recorded_at: '2026-07-21T16:06:57.336265+00:00'
oompah.review_url: https://github.com/lesserevil/oompah/pull/466
oompah.review_number: '466'
oompah.work_branch: OOMPAH-286
oompah.target_branch: main
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
author: oompah
created: 2026-07-21 16:04
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 0, Tool calls: 40
- Tokens: 63 in / 1.7K out [1.7K total]
- Cost: $0.0000
- Exit: terminated, Duration: 18m 27s
- Log: OOMPAH-286__20260721T154620Z.jsonl
---
author: oompah
created: 2026-07-21 16:04
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-21 16:04
---
Focus: Test Engineer
---
author: oompah
created: 2026-07-21 16:05
---
Understanding (Test Engineer, attempt #2): The previous test engineer agent was terminated after 18 minutes. I will now: (1) explore the codebase to understand the 5 key prompt paths already discovered, (2) create plans/prompt-injection-protection.md with the full trust/threat model and machine-readable provenance contract, and (3) write the documentation/contract test in tests/ that asserts the inventory names all required components. Then commit, push, and close.
---
author: oompah
created: 2026-07-21 16:06
---
Implementation: Created plans/prompt-injection-protection.md (644 lines) and tests/test_prompt_injection_protection.py (260 lines).

The plan document covers:
- §2: Trust levels (trusted sources, untrusted sources, mixed)
- §3: Trust propagation rules (4 rules)
- §4: 5 attack scenarios (issue-body, comment-delivery, attachment, triage, repo-file injection)
- §5: Delimiter structure and escaping rules
- §6: Inventory of all 5 prompt paths with component names, modules, functions, data flows, trust levels
- §7: Server-side authoritative controls table (8 controls)
- §8: Machine-readable provenance contract JSON schema with 6 fields (version, component, source, trust, delimiter, issue_identifier)
- §9: Non-goals

The test file has 29 contract tests across 7 test classes, verifying all structural requirements as a hard gate.
---
author: oompah
created: 2026-07-21 16:06
---
Verification: All 29 contract tests pass (python -m pytest tests/test_prompt_injection_protection.py -v → 29 passed in 0.11s). Branch OOMPAH-286 pushed to origin.
---
author: oompah
created: 2026-07-21 16:06
---
Completion: Delivered plans/prompt-injection-protection.md and tests/test_prompt_injection_protection.py on branch OOMPAH-286.

Acceptance criteria met:
- A developer can determine if a new input is untrusted (§2 trust level tables)
- Labeling and delimiters are specified (§5: oompah:untrusted XML tags with source attribute)
- Server-side controls are listed as authoritative (§7 table + §3 rule 4)
- Machine-readable provenance contract defined (§8 JSON schema)
- All 5 required inventory components named: intake_bridge, focus_triage, prompt_renderer, continuation_prompts, agent_system_prompt (§6)
- 29 tests enforce these as hard gates
---
author: oompah
created: 2026-07-21 16:06
---
Created plans/prompt-injection-protection.md (trust model, threat scenarios, 5-component inventory, provenance contract, non-goals) and tests/test_prompt_injection_protection.py (29 contract tests, all passing). Branch OOMPAH-286 pushed.
---
author: oompah
created: 2026-07-21 16:06
---
Agent completed successfully in 119s (4406 tokens)
---
author: oompah
created: 2026-07-21 16:06
---
Run #2 [attempt=2, profile=standard, role=standard -> Claude/default]
- Turns: 39, Tool calls: 24
- Tokens: 25 in / 4.4K out [4.4K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 59s
- Log: OOMPAH-286__20260721T160500Z.jsonl
---
author: oompah
created: 2026-07-21 16:07
---
Close refused by orchestrator: branch `OOMPAH-286` has 1 commit not on `main` and no open PR targets `main` from this branch.

Diagnostic:
  Unmerged commits: 1
    37bfca985 OOMPAH-286: Add prompt-injection trust model doc and contract tests
  Open PRs from this branch: 0
  Merged PRs from this branch: 0

Required: open a PR before closing.
  gh pr create --base main --head OOMPAH-286 --title "OOMPAH-286: Define the external-content trust model and prompt-injection threat model" --body "..."

Task reopened. Re-dispatch on the next tick will see this comment in its prompt context.
---
author: oompah
created: 2026-07-21 16:07
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-21 16:07
---
Focus: Test Engineer
---
author: oompah
created: 2026-07-21 16:11
---
Completion: All work delivered on branch OOMPAH-286, PR #466 opened (https://github.com/lesserevil/oompah/pull/466).

Deliverables:
- plans/prompt-injection-protection.md (396 lines): full trust/threat model with trusted vs untrusted sources, trust propagation rules, 5 attack scenarios, delimiter spec, inventory of all 5 prompt paths, 8 server-side authority controls, machine-readable provenance contract JSON schema, and non-goals
- tests/test_prompt_injection_protection.py (371 lines): 29 contract tests, all passing (0.14s)

Acceptance criteria met:
- Developer can determine if a new input is untrusted (§2 trust level tables)
- Labeling and delimiters specified (§5: oompah:untrusted XML tags with source attribute)
- Server-side controls listed as authoritative (§7 + §3 rule 4)
- Machine-readable provenance contract defined (§8 JSON schema)
- All 5 required inventory components named (intake_bridge, focus_triage, prompt_renderer, continuation_prompts, agent_system_prompt) in §6
- 29 tests enforce requirements as hard gates
---
author: oompah
created: 2026-07-21 16:11
---
YOLO: merged PR #466.
---
author: oompah
created: 2026-07-21 16:11
---
Created plans/prompt-injection-protection.md (trust/threat model, 5-component prompt-path inventory, provenance contract) and tests/test_prompt_injection_protection.py (29 contract tests, all passing). PR #466 open at https://github.com/lesserevil/oompah/pull/466.
---
<!-- COMMENTS:END -->
