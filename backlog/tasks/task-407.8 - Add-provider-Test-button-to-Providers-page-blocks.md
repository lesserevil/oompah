---
id: TASK-407.8
title: Add provider Test button to Providers page blocks
status: Backlog
assignee: []
created_date: 2026-06-01 21:45
labels:
- feature
- needs:frontend
- needs:test
dependencies:
- TASK-407.3
modified_files:
- oompah/templates/providers.html
- tests/test_providers_role_matrix.py
parent_task_id: TASK-407
priority: medium
ordinal: 38000
---
## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Add a manual Test button to each provider block on the Providers page so an operator can verify a provider without creating a task.

Current state to inspect first:
- Providers page already renders provider blocks/cards with configuration fields.
- TASK-407.3 adds a backend provider test endpoint and structured success/failure response.

Required behavior:
- Each provider block has a Test button near the provider actions.
- Clicking Test calls the provider test endpoint for that provider.
- The button shows a loading state while the request is active and prevents duplicate clicks for that provider.
- The result is shown inline inside the provider block, not only as a toast.
- The result includes success/failure, model used, latency, short response text, and normalized error reason when present.
- The test must not change provider config, role config, task state, or round-robin selector state.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Every rendered provider block has a Test button.
- [ ] #2 Clicking Test sends exactly one provider test request while the button is loading.
- [ ] #3 A successful response renders model used, latency, and response text inline.
- [ ] #4 A failed response renders normalized reason and message inline.
- [ ] #5 Testing one provider does not alter unsaved edits on another provider or role matrix state.
- [ ] #6 The button and result layout do not overlap provider form controls on normal desktop width.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Find the provider block rendering code in oompah/templates/providers.html.
2. Add a Test button with a clear accessible label and compact styling consistent with existing actions.
3. Add frontend state keyed by provider id for testing/loading/result.
4. Implement a click handler that POSTs to the endpoint from TASK-407.3.
5. Render success and failure states inline in the provider block.
6. Ensure failures from the HTTP layer and failures returned by the endpoint both show useful messages.
7. Add tests or template assertions for button presence and result rendering where current test structure allows.
<!-- SECTION:PLAN:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Frontend/template tests cover the Test button and result states where practical.
- [ ] #2 Manual browser check confirms the button works against a mocked or harmless configured provider.
<!-- DOD:END -->
