---
id: TASK-407.3
title: Add provider health check service and manual test endpoint
status: Done
assignee: []
created_date: '2026-06-01 21:43'
updated_date: '2026-06-03 02:17'
labels:
  - feature
dependencies: []
modified_files:
  - oompah/server.py
  - oompah/orchestrator.py
  - tests/test_providers_role_matrix.py
parent_task_id: TASK-407
priority: high
ordinal: 33000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Add backend support for manually testing a configured provider from the Providers page and reuse the same error classification concepts for automatic fallback.

Current state to inspect first:
- Providers are stored in ProviderStore and represented by ModelProvider.
- API workers already know how to call provider-backed models.
- ACP providers may be SDK-managed and may not require a normal model value.
- The existing system reports provider failures in several places, including missing credentials, rate limits, and overloads.

Required behavior:
- Add POST /api/v1/providers/{provider_id}/test or an equivalent REST-style endpoint.
- The endpoint sends a tiny prompt such as: What is 2 + 2? Answer with only the number.
- The endpoint must not create an oompah task, update role round-robin usage, claim backlog work, or mutate provider config.
- Return success or failure with provider id, provider name, model used, latency, short response text, and a normalized error reason.
- Use short timeouts so the UI test does not hang the operator.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 POSTing to the provider test endpoint for a valid mocked provider returns success, the model used, latency, and response text.
- [ ] #2 A provider with missing credentials returns failure with normalized reason missing_credentials or auth_failed.
- [ ] #3 A timeout returns failure with normalized reason timeout.
- [ ] #4 A rate limit or overload error returns a normalized retryable reason.
- [ ] #5 The endpoint does not create or modify any Backlog task.
- [ ] #6 The endpoint does not update role selection usage state.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Locate the existing API-agent and ACP-agent call paths and identify the smallest reusable method for sending one prompt to one provider/model.
2. Add a provider test helper that chooses provider.default_model first, then the first configured model, while respecting ACP empty-model behavior.
3. Add a normalized error reason enum or helper for at least missing_credentials, auth_failed, rate_limited, budget_blocked, timeout, overloaded, invalid_model, provider_unavailable, and unknown_error.
4. Add the HTTP endpoint in oompah/server.py.
5. Ensure the endpoint catches exceptions and returns structured JSON instead of crashing the server.
6. Add tests with mocked provider calls for success, missing credentials, invalid model, timeout, and rate limit.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Understanding [oompah]: Adding POST /api/v1/providers/{provider_id}/test endpoint. Plan: 1) Create a provider_health.py module with normalize_error_reason() and test_provider() helpers. 2) test_provider() picks the model (default_model or first in models list), builds minimal OpenAI chat completions request, sends it with short timeout (10s), returns ProviderTestResult. 3) ACP providers (mode=acp) return provider_unavailable for now. 4) Add HTTP endpoint in server.py. 5) Catch all exceptions, map to normalized error reasons. 6) Tests in tests/test_provider_health.py.

Discovery [oompah]: Key finding: _http_post() in api_agent.py already had RateLimitError/TransientServerError but was too coupled to full agent sessions to reuse directly. Created standalone provider_health.py using urllib.request directly (same as api_agent.py uses) with a 10s timeout. The function test_provider() was renamed run_health_check() to avoid pytest collection collision (pytest collects functions starting with test_). Implementation: oompah/provider_health.py (new) - ProviderTestResult dataclass, ERROR_REASONS constant, _normalize_http_error/_normalize_url_error helpers, _pick_model, run_health_check(). oompah/server.py - added POST /api/v1/providers/{provider_id}/test endpoint. tests/test_provider_health.py (new) - 46 tests covering AC1-AC6.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Merge conflict resolved. Feature code was already in main; rebased 3 backlog-status commits onto origin/main, resolved conflict by dropping duplicate patch. Force-pushed cleanly. All 46 provider health tests pass.
<!-- SECTION:FINAL_SUMMARY:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Backend tests cover successful and failed provider tests without making real network calls.
- [ ] #2 The provider test helper can be reused by role failover work.
<!-- DOD:END -->

## Comments
<!-- COMMENTS:BEGIN -->
<!-- COMMENT:BEGIN -->
index: 1
author: oompah
created: 2026-06-03 02:04

Agent dispatched (profile: default)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 2
author: oompah
created: 2026-06-03 02:04

Focus: Feature Developer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 3
author: oompah
created: 2026-06-03 02:04

Agent failed: OpenAIError: Missing credentials. Please pass an `api_key`, `workload_identity`, `admin_api_key`, or set the `OPENAI_API_KEY` or `OPENAI_ADMIN_KEY` environment variable.. Retrying in 10s (attempt #1)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 4
author: oompah
created: 2026-06-03 02:04

Run #1 [attempt=1, profile=default, role=fast -> Codex/default]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 9s
- Log: TASK-407.3__20260603T020419Z.jsonl
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 5
author: oompah
created: 2026-06-03 02:04

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 6
author: oompah
created: 2026-06-03 02:04

Focus: Feature Developer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 7
author: oompah
created: 2026-06-03 02:04

Agent failed: OpenAIError: Missing credentials. Please pass an `api_key`, `workload_identity`, `admin_api_key`, or set the `OPENAI_API_KEY` or `OPENAI_ADMIN_KEY` environment variable.. Retrying in 20s (attempt #2)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 8
author: oompah
created: 2026-06-03 02:04

Run #2 [attempt=2, profile=standard, role=standard -> Codex/default]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 7s
- Log: TASK-407.3__20260603T020449Z.jsonl
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 9
author: oompah
created: 2026-06-03 02:05

Retrying (attempt #2, agent: standard)
<!-- COMMENT:END -->
<!-- COMMENTS:END -->
