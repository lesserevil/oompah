---
id: OOMPAH-291
type: task
status: In Progress
priority: 1
title: Add prompt-injection regression suite, observability, and operator guidance
parent: OOMPAH-285
children: []
blocked_by:
- OOMPAH-288
- OOMPAH-289
- OOMPAH-290
labels: []
assignee: null
created_at: '2026-07-21T14:51:57.738049Z'
updated_at: '2026-07-21T23:23:53.728408Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 3601dcf2-d175-4148-bf1f-f0b9493a0c7e
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
<!-- COMMENTS:END -->
