---
id: OOMPAH-289
type: task
status: In Progress
priority: 1
title: Harden focus triage and other model-only decisions against external instructions
parent: OOMPAH-285
children: []
blocked_by:
- OOMPAH-288
labels:
- focus-complete:duplicate_detector
assignee: null
created_at: '2026-07-21T14:51:55.684579Z'
updated_at: '2026-07-21T22:48:18.942336Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 3a31ebdb-eed6-42e6-9539-e061555c6916
oompah.task_costs:
  total_input_tokens: 1428560
  total_output_tokens: 15529
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 1428560
      output_tokens: 15529
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 479334
    output_tokens: 2697
    cost_usd: 0.0
    recorded_at: '2026-07-21T22:26:22.068916+00:00'
  - profile: default
    model: unknown
    input_tokens: 25
    output_tokens: 5629
    cost_usd: 0.0
    recorded_at: '2026-07-21T22:32:22.794863+00:00'
  - profile: default
    model: unknown
    input_tokens: 949201
    output_tokens: 7203
    cost_usd: 0.0
    recorded_at: '2026-07-21T22:38:21.580704+00:00'
---
## Summary

Update focus triage and every model-only decision path found in the threat model. Pass untrusted title/body/comment text only through the shared safe renderer, use structured output validation, and retain deterministic validation/fallbacks. Ensure injections cannot select arbitrary foci, alter priority, bypass approval, or create follow-up work.

Dependency: Render untrusted content in explicit prompt data boundaries.

Tests: mock model calls with injected content and malicious model output; verify invalid outputs are rejected, deterministic fallback is used, and no unauthorized side effect occurs.

Acceptance criteria: triage remains constrained to configured foci and server-side eligibility rules regardless of external text.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-21 22:25
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-21 22:25
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-21 22:26
---
Agent completed successfully in 77s (482031 tokens)
---
author: oompah
created: 2026-07-21 22:26
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/default]
- Turns: 1, Tool calls: 9
- Tokens: 479.3K in / 2.7K out [482.0K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 17s
- Log: OOMPAH-289__20260721T222507Z.jsonl
---
author: oompah
created: 2026-07-21 22:26
---
Agent completed without closing this issue (77s (482031 tokens)). Escalating from 'default' to 'standard'. Retrying in 10s (1/3).
---
author: oompah
created: 2026-07-21 22:30
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-21 22:30
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-21 22:32
---
Focus handoff: duplicate_detector

1. Outcome: No duplicate confirmed. OOMPAH-289 is a unique child task of OOMPAH-285 (epic: Defend Oompah agents against prompt injection from external content). It covers hardening focus triage and all model-only decision paths against injection attacks — a scope not covered by any existing task.

2. Evidence reviewed:
   - Searched .oompah/tasks/ across all states (archived 223 files, merged 55 files, done, backlog, needs-ci-fix, needs-rebase) for keywords: focus triage, model-only, injection, safe renderer, structured output validation, harden, arbitrary foci, alter priority, bypass approval, threat model, untrusted. Zero hits matched OOMPAH-289's scope.
   - Reviewed OOMPAH-285 (epic, In Progress): parent with children OOMPAH-286, 287, 335, 288, 289, 290, 291 — OOMPAH-289 is listed as a distinct child with its own scope.
   - OOMPAH-286 (Merged): defines the threat model in plans/prompt-injection-protection.md — planning artifact, not an implementation of triage hardening.
   - OOMPAH-287 (Merged): adds provenance dataclass/enums and initial XML wrapping — dependency, not duplicate.
   - OOMPAH-288 (Done): adds SAFETY_INSTRUCTION to wrap_untrusted() and adversarial tests — covers rendering layer only; OOMPAH-289 covers the focus triage/model decision layer.
   - OOMPAH-290 (Open): covers server-side authority boundaries — distinct scope (server-side action authorization, not model decision hardening).
   - OOMPAH-291 (Open): end-to-end regression suite — distinct scope (integration/observability).
   - No archived or merged task covers OOMPAH-289's scope.
   - Key design doc: plans/agentic-focus-triage.md describes the LLM-based focus triage path (focus.py: _build_triage_prompt, _select_focus_llm, select_focus). This is the primary path that OOMPAH-289 must harden.

3. Remaining work / risks:
   - Audit all model-only decision paths per threat model (plans/prompt-injection-protection.md §4, §6): focus triage (_build_triage_prompt in focus.py), any other LLM calls where untrusted content influences output decisions.
   - Ensure untrusted title/body/comment text is passed through wrap_untrusted() (OOMPAH-288's SAFETY_INSTRUCTION and XML delimiters) in _build_triage_prompt and any other model-only prompt builders.
   - Add structured output validation: parse and validate model responses for focus triage against the configured foci set — reject any output not naming a known focus; fallback to deterministic score_focus.
   - Verify injections cannot: select arbitrary foci (LLM output must be validated against active foci list), alter priority (server-side only), bypass approval (server-side gating), create follow-up work (server-side only).
   - Write tests: mock model calls with injected content and malicious model output; assert invalid outputs are rejected, deterministic fallback is used, no unauthorized side effect occurs.
   - Key file: oompah/focus.py (select_focus, _build_triage_prompt, _select_focus_llm); tests/test_focus_triage.py (may need to be created).
   - Risk: OOMPAH-288's wrap_untrusted() may already be in some triage prompt paths — auditor should check what is already wrapped vs. what needs to be added.

4. Recommended next focus: security (harden focus.py model decision paths, add structured output validation, write adversarial tests as specified in OOMPAH-289 description).
---
author: oompah
created: 2026-07-21 22:32
---
Agent completed successfully in 123s (5654 tokens)
---
author: oompah
created: 2026-07-21 22:32
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 51, Tool calls: 40
- Tokens: 25 in / 5.6K out [5.7K total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 3s
- Log: OOMPAH-289__20260721T223022Z.jsonl
---
author: oompah
created: 2026-07-21 22:32
---
Focus handoff from `duplicate_detector` is complete. Queued a fresh agent run for the next applicable focus. The next agent should begin with the preceding Focus handoff comment.
---
author: oompah
created: 2026-07-21 22:32
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-21 22:32
---
Focus: Test Engineer
---
author: oompah
created: 2026-07-21 22:38
---
Agent completed successfully in 351s (956404 tokens)
---
author: oompah
created: 2026-07-21 22:38
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/default]
- Turns: 1, Tool calls: 16
- Tokens: 949.2K in / 7.2K out [956.4K total]
- Cost: $0.0000
- Exit: normal, Duration: 5m 51s
- Log: OOMPAH-289__20260721T223232Z.jsonl
---
author: oompah
created: 2026-07-21 22:38
---
Agent completed without closing this issue (351s (956404 tokens)). Escalating from 'default' to 'standard'. Retrying in 10s (1/3).
---
author: oompah
created: 2026-07-21 22:38
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-21 22:38
---
Focus: Test Engineer
---
author: oompah
created: 2026-07-21 22:48
---
Understanding: Continuing from previous Test Engineer session. The prior agent made three files of changes but did not commit them:

1. oompah/focus.py — Hardened _build_triage_prompt() to wrap title, labels, and description each in their own <oompah:untrusted> provenance block (not just description). Hardened _parse_triage_response() to strictly require a single non-empty 'name: reasoning' line (reject multi-line, single-word, quoted, or prefixed responses). Removed the 'default' LLM escape path so only the deterministic scorer can return DEFAULT_FOCUS.

2. tests/test_focus_triage.py — New tests: test_rejects_output_outside_single_line_schema (parametrized), test_llm_cannot_select_default_focus, test_injected_issue_and_malicious_model_output_cannot_select_focus, test_llm_pick_with_score_zero_falls_back, test_llm_pick_with_score_positive_is_trusted, new cache and timeout tests. All 24 tests pass.

3. tests/test_provenance.py — Updated TestTriageProvenanceIntegration to assert 3 untrusted blocks (title + labels + description), not 1. New test_title_and_labels_are_wrapped_independently covers the multi-block wrapping. All 477 relevant tests pass.

Plan: Check for remaining test gaps, add any missing coverage, run the full suite, commit and close.
---
<!-- COMMENTS:END -->
