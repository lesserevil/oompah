---
id: TASK-430
title: Allow unauthenticated API providers through dispatch preflight
status: Done
assignee:
  - oompah
created_date: '2026-06-03 06:00'
updated_date: '2026-06-03 06:03'
labels: []
dependencies: []
priority: high
ordinal: 66000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
BUG: The Providers page test succeeds for Godspeed because provider_health sends a real chat-completions probe and omits the Authorization header when no API key is configured. The scheduler's candidate preflight currently rejects every non-ACP provider with an empty api_key as missing_credentials before attempting dispatch. This incorrectly blocks API-mode providers backed by local/internal OpenAI-compatible gateways that do not require auth.\n\nWHAT TO DO\n- Update orchestrator candidate preflight so API-mode providers with no api_key are not automatically rejected as missing_credentials when they are configured as subscription/no-auth providers.\n- Update the API agent HTTP request path to match provider_health: only include the Authorization header when an api_key is configured.\n- Keep secret safety: never log api_key values and do not include auth headers in agent JSONL logs.\n- Add regression tests covering API-mode subscription/no-auth providers and Authorization header omission.\n\nHOW TO VERIFY\n- Focused pytest for candidate preflight and API agent header behavior passes.\n- make test passes.\n- After restart, Godspeed no longer logs preflight missing_credentials solely because api_key is empty.
<!-- SECTION:DESCRIPTION:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Fixed dispatch preflight so subscription/no-auth API providers are not rejected solely for an empty api_key, and aligned ApiAgentSession with provider health checks by omitting Authorization when no key is configured. Added regression coverage for preflight and HTTP headers. Verified focused pytest and make test.
<!-- SECTION:FINAL_SUMMARY:END -->
