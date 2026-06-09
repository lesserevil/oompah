---
id: TASK-458.1
title: Implement GitHub auth and API client layer
status: Done
assignee: []
created_date: '2026-06-08 17:56'
updated_date: '2026-06-09 05:34'
labels:
  - task
  - github-issues
  - tracker-migration
dependencies:
  - TASK-457.1
references:
  - plans/github-issues-tracker-migration.md
modified_files:
  - oompah/github_tracker.py
  - oompah/config.py
  - tests
parent_task_id: TASK-458
priority: high
ordinal: 115000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Add GitHub App installation-token support as the preferred production auth path, with PAT and gh-auth fallback for development. Centralize request retries, timeout handling, pagination, rate-limit logging, ETag/cache hooks, and response redaction.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 GitHub App, PAT, and missing-auth paths are covered by tests.
- [ ] #2 Rate-limit and auth errors become actionable TrackerError messages.
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-09 04:39
---
Agent dispatched (profile: default)
---

author: oompah
created: 2026-06-09 04:40
---
Focus: Duplicate Investigator
---

author: oompah
created: 2026-06-09 04:51
---
Agent completed successfully in 706s (29596 tokens)
---

author: oompah
created: 2026-06-09 04:51
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 103, Tool calls: 73
- Tokens: 62 in / 29.5K out [29.6K total]
- Cost: $0.0000
- Exit: normal, Duration: 11m 46s
- Log: TASK-458.1__20260609T044007Z.jsonl
---

author: oompah
created: 2026-06-09 04:51
---
Agent completed without closing this issue (706s (29596 tokens)). Escalating from 'default' to 'standard'. Retrying in 10s (1/3).
---

author: oompah
created: 2026-06-09 04:53
---
Agent dispatched (profile: standard)
---

author: oompah
created: 2026-06-09 04:55
---
Understanding the task: Implement GitHub auth and API client layer with GitHub App installation-token support as preferred production auth, PAT and gh-auth fallback for development. Centralize request retries, timeout handling, pagination, rate-limit logging, ETag/cache hooks, and response redaction.
---

author: oompah
created: 2026-06-09 05:34
---
Implementation complete. All acceptance criteria met:

1. ✅ GitHub App, PAT, and missing-auth paths are covered by tests (69 tests in test_github_tracker.py)
2. ✅ Rate-limit and auth errors become actionable TrackerError messages (tests verify 401, 403, 429 handling)

Implementation summary:
- GitHubAuth class with three auth paths: GitHub App (preferred production), PAT (dev/CI), gh CLI fallback (local dev)
- GitHubClient with centralized request retries (exponential backoff), timeout handling, pagination (Link header), rate-limit logging (DEBUG), rate-limit block handling (429 with Retry-After/X-RateLimit-Reset wait and retry), ETag/conditional GET cache hooks, response body redaction
- GitHubIssueTracker implementing TrackerProtocol with skeleton methods (NotImplementedError for mutations to be implemented in TASK-458.2-458.7)
- ADAPTER_REGISTRY integration with github_issues factory
- All 69 tests pass, plus existing server/orchestrator/config tests pass
---
<!-- COMMENTS:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Implemented GitHub auth and API client layer with:

1. **GitHubAuth** — Three-tier auth priority:
   - GitHub App installation tokens (preferred production path) with auto-refresh before expiry
   - PAT via OOMPAH_GITHUB_TOKEN / GH_TOKEN / GITHUB_TOKEN env vars
   - gh CLI fallback (gh auth token) for local development
   - Missing auth returns None gracefully (no exception)

2. **GitHubClient** — Centralized HTTP client with:
   - Exponential backoff retries for transient failures (5xx, network, timeout)
   - Configurable per-request timeout (OOMPAH_GITHUB_API_TIMEOUT)
   - Automatic Link-header pagination (request_paginated)
   - Rate-limit logging at DEBUG (remaining quota, reset time)
   - Rate-limit block handling (HTTP 429) with Retry-After/X-RateLimit-Reset wait and retry
   - ETag/conditional GET cache hooks (If-None-Match, 304 returns cached value)
   - Response redaction (Bearer tokens scrubbed from logs)

3. **GitHubIssueTracker** — TrackerProtocol adapter with:
   - Full protocol conformance (27 methods)
   - Read operations return empty collections (skeleton for TASK-458.2+)
   - Mutation operations raise NotImplementedError (to be implemented in TASK-458.3-458.7)
   - In-memory ETag cache with invalidation

4. **ADAPTER_REGISTRY integration** — github_issues factory registered, validates required env vars (OOMPAH_GITHUB_TRACKER_OWNER, OOMPAH_GITHUB_TRACKER_REPO)

All 69 unit tests pass covering both acceptance criteria:
- #1: GitHub App, PAT, and missing-auth paths tested
- #2: Rate-limit (429) and auth errors (401, 403) produce actionable TrackerError messages

Existing server, orchestrator, and config tests also pass (no regressions).
<!-- SECTION:FINAL_SUMMARY:END -->
