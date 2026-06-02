---
id: TASK-407.8
title: Add provider Test button to Providers page blocks
status: In Progress
assignee: []
created_date: 2026-06-01 21:45
updated_date: 2026-06-02 15:57
labels:
- feature
dependencies:
- TASK-407.3
modified_files:
- oompah/templates/providers.html
- tests/test_providers_role_matrix.py
parent_task_id: TASK-407
priority: medium
ordinal: 38000
oompah.task_costs:
  total_input_tokens: 49
  total_output_tokens: 11271
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 49
      output_tokens: 11271
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 49
    output_tokens: 11271
    cost_usd: 0.0
    recorded_at: '2026-06-02T15:41:52.359445+00:00'
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

## Comments
<!-- COMMENTS:BEGIN -->
<!-- COMMENT:BEGIN -->
index: 1
author: oompah
created: 2026-06-02 15:30

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 2
author: oompah
created: 2026-06-02 15:30

Focus: Frontend Developer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 3
author: oompah
created: 2026-06-02 15:35

Agent dispatched (profile: default)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 4
author: oompah
created: 2026-06-02 15:36

Focus: Duplicate Investigator
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 5
author: oompah
created: 2026-06-02 15:41

Agent completed successfully in 359s (11320 tokens)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 6
author: oompah
created: 2026-06-02 15:41

Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 85, Tool calls: 56
- Tokens: 49 in / 11.3K out [11.3K total]
- Cost: $0.0000
- Exit: normal, Duration: 5m 59s
- Log: TASK-407.8__20260602T153601Z.jsonl
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 7
author: oompah
created: 2026-06-02 15:57

Agent dispatched (profile: default)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 8
author: oompah
created: 2026-06-02 16:00

DUPLICATE INVESTIGATION: No duplicate found. TASK-407.3 adds the backend POST /api/v1/providers/{id}/test endpoint; TASK-407.8 adds the frontend Test button that calls it. These are complementary tasks, not duplicates. The previous agent run (commit 31a0f77) already implemented and committed all required changes: Test button in each provider card, inline result rendering, loading state, and 14 template smoke tests.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 9
author: oompah
created: 2026-06-02 16:00

COMPLETION: Feature fully implemented. Changes in commit 31a0f77: (1) Test button added to each provider card in renderProviders() in providers.html; (2) Per-provider inline result div (hidden by default); (3) testProvider() async JS function that POSTs to /api/v1/providers/{id}/test, shows loading state, renders success (model, latency, response text) or failure (normalized reason + detail) inline; (4) CSS classes .provider-test-result/.test-result-ok/.test-result-fail; (5) 14 template smoke tests in TestProviderTestButton class.
<!-- COMMENT:END -->
<!-- COMMENTS:END -->
