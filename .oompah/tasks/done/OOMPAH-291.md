---
id: OOMPAH-291
type: task
status: Done
priority: 1
title: Add prompt-injection regression suite, observability, and operator guidance
parent: OOMPAH-285
children: []
blocked_by:
- OOMPAH-288
- OOMPAH-289
- OOMPAH-290
labels:
- focus-complete:duplicate_detector
assignee: null
created_at: '2026-07-21T14:51:57.738049Z'
updated_at: '2026-07-21T23:58:59.870992Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: f6823415-1206-4425-8f45-08bf1104c28d
oompah.task_costs:
  total_input_tokens: 413079
  total_output_tokens: 9416
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 413079
      output_tokens: 9416
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 24
    output_tokens: 6361
    cost_usd: 0.0
    recorded_at: '2026-07-21T23:24:18.185984+00:00'
  - profile: default
    model: unknown
    input_tokens: 413055
    output_tokens: 3055
    cost_usd: 0.0
    recorded_at: '2026-07-21T23:25:50.517743+00:00'
---
## Summary

Build end-to-end adversarial fixtures that flow GitHub issue bodies/comments and other inventoried sources through import, approval, prompt rendering, focus selection, agent dispatch, and protected-action checks. Add structured audit events for untrusted-content rendering and denied actions without logging secrets. Document the security model, safe intake configuration, and incident response.

Dependencies: Render untrusted content in explicit prompt data boundaries; Harden focus triage and other model-only decisions against external instructions; Enforce server-side authority boundaries for agent actions influenced by external intake.

Tests: end-to-end suite plus documentation tests; run make test.

Acceptance criteria: a malicious GitHub issue cannot override agent instructions or cause protected side effects, and operators can investigate attempted injection.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-21 23:21
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-21 23:21
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-21 23:22
---
Understanding: Investigating whether OOMPAH-291 (prompt-injection regression suite, observability, operator guidance) is a duplicate of any existing task. Will search for similar tasks covering adversarial fixtures, prompt-injection testing, security audit events, and security model documentation.
---
author: oompah
created: 2026-07-21 23:23
---
Discovery: No duplicate found. Searched .oompah/tasks, docs/, and plans/ for tasks covering prompt-injection regression suites, adversarial fixtures, audit events, and operator guidance. Closest related work: OOMPAH-286 (created plans/prompt-injection-protection.md threat model doc + documentation/contract tests in tests/test_prompt_injection_protection.py), OOMPAH-285 (parent epic). OOMPAH-291 is distinct: it adds E2E adversarial fixtures flowing through the full pipeline, structured audit events for observability, and operator-facing security guidance—none of which exist yet. The existing test file contains only documentation contract tests (validating the plan doc's presence and structure), not adversarial E2E tests or audit event instrumentation. Not a duplicate.
---
author: oompah
created: 2026-07-21 23:24
---
Focus handoff: duplicate_detector

1. Outcome: No duplicate confirmed. OOMPAH-291 is a new, distinct task within the OOMPAH-285 prompt-injection protection epic.

2. Relevant files and evidence:
   - plans/prompt-injection-protection.md — OOMPAH-286's threat model doc. Sections 1-10 define trust levels, attack scenarios, inventory, provenance contract, and non-goals. This is the design document OOMPAH-291 must implement against.
   - tests/test_prompt_injection_protection.py — Existing documentation/contract tests (OOMPAH-286). These validate that the plan doc exists and contains required sections. They are NOT the E2E adversarial test suite that OOMPAH-291 requires.
   - Blockers OOMPAH-288/289/290 are not yet committed as .oompah/tasks/ files on this branch; they are in-flight tasks implementing: delimiters (288), triage hardening (289), server-side authority enforcement (290).

3. Remaining work:
   - E2E adversarial fixtures: craft malicious GitHub issue/comment fixtures and run them through the full pipeline (import → approval → prompt rendering → focus selection → agent dispatch → protected-action checks), asserting each layer resists injection.
   - Structured audit events: add structured logging for untrusted-content rendering events and denied actions (no secrets in logs).
   - Operator guidance docs: security model summary, safe intake configuration guide, incident response playbook — in docs/ (user-facing).
   - Tests must pass via make test.

4. Recommended next focus: feature (implement E2E tests, audit events, and docs). This task should remain blocked on OOMPAH-288/289/290 until those are merged, unless the implementor can stub the controls.
---
author: oompah
created: 2026-07-21 23:24
---
Agent completed successfully in 142s (6385 tokens)
---
author: oompah
created: 2026-07-21 23:24
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 52, Tool calls: 38
- Tokens: 24 in / 6.4K out [6.4K total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 22s
- Log: OOMPAH-291__20260721T232158Z.jsonl
---
author: oompah
created: 2026-07-21 23:24
---
Focus handoff from `duplicate_detector` is complete. Queued a fresh agent run for the next applicable focus. The next agent should begin with the preceding Focus handoff comment.
---
author: oompah
created: 2026-07-21 23:24
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-21 23:24
---
Focus: Security Auditor
---
author: oompah
created: 2026-07-21 23:25
---
Agent completed successfully in 79s (416110 tokens)
---
author: oompah
created: 2026-07-21 23:25
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/default]
- Turns: 1, Tool calls: 7
- Tokens: 413.1K in / 3.1K out [416.1K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 19s
- Log: OOMPAH-291__20260721T232433Z.jsonl
---
author: oompah
created: 2026-07-21 23:25
---
Agent completed without closing this issue (79s (416110 tokens)). Escalating from 'default' to 'standard'. Retrying in 10s (1/3).
---
author: oompah
created: 2026-07-21 23:26
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-21 23:26
---
Focus: Security Auditor
---
author: oompah
created: 2026-07-21 23:39
---
Understanding: As Security Auditor, implementing the three remaining deliverables for OOMPAH-291:

1. **Structured audit events** — Add UNTRUSTED_RENDER: log events to wrap_untrusted() in provenance.py (mirroring AUTHORITY_DENY: pattern already in authority_boundary.py). Logs component, source, issue_identifier, and content length — no content/secrets.

2. **E2E adversarial test suite** — tests/test_prompt_injection_e2e.py flowing malicious payloads through the full pipeline (intake bridge → prompt rendering → focus triage → authority boundary → protected-action checks).

3. **Operator guidance docs** — docs/prompt-injection-security.md: security model summary, safe intake configuration, monitoring (audit log filters), and incident response playbook.

Blocking tasks OOMPAH-288/289/290 are already merged into this branch. All 10858 tests pass.
---
author: oompah
created: 2026-07-21 23:58
---
Implementation complete. Three deliverables shipped on branch epic-OOMPAH-285:

**1. Structured audit events (oompah/provenance.py)**
Added UNTRUSTED_RENDER: INFO log events to wrap_untrusted() — emits component, source, trust level, issue identifier, and content byte length. Content itself is never logged (no secret exposure). Mirrors AUTHORITY_DENY: pattern from authority_boundary.py.

**2. E2E adversarial regression suite (tests/test_prompt_injection_e2e.py)**
186 tests across 7 test classes, parametrized over 12 adversarial payload categories:
- TestIntakeBridgeAdversarialFixtures: intake bridge handles malicious GitHub issue bodies/comments
- TestPromptRendererAdversarialFixtures: render_prompt() wraps all adversarial content in delimiters with SAFETY_INSTRUCTION
- TestFocusTriageAdversarialFixtures: _build_triage_prompt() wraps issue data, closing-delimiter escape is blocked
- TestCommentDeliveryAdversarialFixtures: _deliver_github_comment_to_agent() wraps mid-turn comments
- TestAuthorityBoundaryAdversarialFixtures: external tasks denied all 7 ProtectedActions regardless of context
- TestAuditEventEmission: UNTRUSTED_RENDER: and AUTHORITY_DENY: events verified; content not in logs
- TestFullPipelineIntegration: complete adversarial flow from intake through all pipeline stages

**3. Operator guidance docs (docs/prompt-injection-security.md)**
- Trust model summary with Mermaid pipeline diagram
- Safe intake configuration (opt-in, auto-promote=false, budget cap, protected-action grants)
- Monitoring guide: UNTRUSTED_RENDER: and AUTHORITY_DENY: log filters, alert thresholds
- Incident response playbook: pause → identify → review → assess blast radius → remediate
- Operator security checklist

**Verification**: All 11,044 tests pass (make test).
---
author: oompah
created: 2026-07-21 23:58
---
Delivered: E2E adversarial regression suite (186 tests in tests/test_prompt_injection_e2e.py covering all 5 pipeline stages + audit event emission), structured UNTRUSTED_RENDER: audit log events in oompah/provenance.py, and operator security guide in docs/prompt-injection-security.md. All 11,044 tests pass.
---
<!-- COMMENTS:END -->
