---
id: TASK-338
title: '[backend:api_agent] ApiAgentSession.run_task failed: HTTP 400 from http://100.64.0.3:8888/v1/chat/completions:
  {"error":{"message":"This model''s maximum context length is 196608 tokens. However,
  yo...'
status: Done
assignee: []
created_date: 2026-05-05 00:36
updated_date: 2026-05-05 00:54
labels:
- bug
- beads-migrated
dependencies: []
priority: high
ordinal: 1000
type: bug
beads:
  id: oompah-zlz_2-px3
  state: closed
  parent_id: null
  dependencies: []
  branch_name: oompah-zlz_2-px3
  target_branch: null
  url: null
  created_at: '2026-05-05T00:36:40Z'
  updated_at: '2026-05-05T00:54:25Z'
  closed_at: '2026-05-05T00:54:25Z'
---
## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
ApiAgentSession.run_task failed: HTTP 400 from http://100.64.0.3:8888/v1/chat/completions: {"error":{"message":"This model's maximum context length is 196608 tokens. However, you requested 32768 output tokens and your prompt contains at least 163841 input tokens, for a total of at least 196609 tokens. Please reduce the length of the input prompt or the number of requested output tokens. (parameter=input_tokens, value=163841)","type":"BadRequestError","param":"input_tokens","code":400}}
<!-- SECTION:DESCRIPTION:END -->

## Comments
<!-- COMMENTS:BEGIN -->
<!-- COMMENT:BEGIN -->
index: 019df59a-68fd-7c58-98e7-7a684255397c
author: oompah
created: 2026-05-05T00:47:11Z

Starting work. Root cause: oompah/api_agent.py:958 hardcodes max_tokens=32768 on every chat-completions call regardless of how full the conversation history is. Once messages cross (model_max_context - 32768) input tokens, the provider 400s with off-by-one overflow and every retry fails identically. Plan: (1) add per-model max_context to ModelProvider config; (2) before each _call_api, estimate the prompt's token count and (a) prune oldest non-system messages until it fits with a safety margin, (b) clamp max_tokens to the remaining budget. Approximation: tokens ≈ len(json.dumps(messages))/4 — good enough since we already need a safety margin for tokenizer drift.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df59a-a6da-7b69-82c2-766c6c98286d
author: oompah
created: 2026-05-05T00:47:26Z

Focus: Software Engineer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df59a-c4d5-77d3-b621-1a4161cf28e8
author: oompah
created: 2026-05-05T00:47:34Z

Agent dispatched (profile: default)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df59c-f252-7426-ad6d-9ab5f4072372
author: oompah
created: 2026-05-05T00:49:57Z

Agent dispatched (profile: default)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df59c-fbab-7841-9901-3973e39efe34
author: oompah
created: 2026-05-05T00:49:59Z

Focus: Software Engineer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df59f-0b7a-78d5-9e36-b9f2a1776fa7
author: oompah
created: 2026-05-05T00:52:14Z

Implementation done. Changes: (1) ModelProvider gained 'model_contexts: dict[str,int]' for per-model window size + a get_model_context(model) accessor. (2) api_agent.py gained two pure helpers — _estimate_tokens (4-chars-per-token rule + JSON serialization) and _prune_messages_to_fit (drops oldest assistant+tool-response groups in pairs, never touches system/initial-user, never orphans tool messages). (3) ApiAgentSession.__init__ takes a new model_max_context arg; _call_api budgets each call: prunes if needed, then clamps max_tokens to (window - est_input - safety_margin), floored at 1024 so the model can always reply. (4) Orchestrator threads provider.get_model_context(model) into the session. (5) .oompah/providers.json now declares model_contexts={'nvidia/MiniMax-M2.7-NVFP4': 196608} for Godspeed. Behavior is opt-in: if a provider doesn't set model_contexts, the legacy fixed max_tokens=32768 still applies. Added tests/test_api_agent_budget.py with 14 tests covering token estimation, pruning invariants (head preserved, tool/assistant pairing never broken, idempotence when already fits), session construction, and end-to-end _call_api behavior with the HTTP layer mocked. Full suite: 1141 passed (was 1127).
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df59f-b0f6-7dcb-90da-901939016197
author: oompah
created: 2026-05-05T00:52:57Z

Agent dispatched (profile: default)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df59f-f16e-700b-a0d8-2f01a585d318
author: oompah
created: 2026-05-05T00:53:13Z

Focus: Software Engineer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df5a0-fd71-7138-87de-6c93d61910aa
author: oompah
created: 2026-05-05T00:54:22Z

Verification: full test suite (1141 passed, was 1127 — 14 new tests cover token estimation, prune invariants, session construction, and end-to-end _call_api budget behavior with HTTP mocked). Service restarted (pid 56860); orchestrator picked up the new model_max_context wiring from .oompah/providers.json. Closing.
<!-- COMMENT:END -->
<!-- COMMENTS:END -->
