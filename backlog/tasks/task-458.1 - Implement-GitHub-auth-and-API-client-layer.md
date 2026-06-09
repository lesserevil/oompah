---
id: TASK-458.1
title: Implement GitHub auth and API client layer
status: In Progress
assignee: []
created_date: '2026-06-08 17:56'
updated_date: '2026-06-09 04:50'
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
created: 2026-06-09 04:41
---
Understanding: No duplicate found. Searched for 'GitHub auth', 'GitHub installation token', 'PAT token github app', 'rate limit retry pagination' — TASK-458.1 is the only task covering GitHub App installation-token auth + PAT/gh-auth fallback + centralized API client. TASK-457.1 (Done) delivered TrackerProtocol and ADAPTER_REGISTRY; TASK-458.1 builds the concrete GitHub client layer on top of that. Plan: (1) check existing code structure and config; (2) implement oompah/github_tracker.py with GitHubClient class covering App auth, PAT fallback, gh-auth fallback; (3) add retry/timeout/pagination/rate-limit/ETag/redaction logic; (4) register GitHubIssueTracker in ADAPTER_REGISTRY; (5) cover all auth paths in tests; (6) verify tests pass.
---

author: oompah
created: 2026-06-09 04:42
---
Discovery: No duplicate. TASK-458.1 is unique. Key findings: (1) oompah/tracker.py has TrackerProtocol, TrackerFactory, ADAPTER_REGISTRY (from TASK-457.1); (2) oompah/scm.py has GitHubProvider for PRs and _resolve_gh_token() pattern I can reuse; (3) PyJWT + cryptography are available in the venv for GitHub App JWT generation; (4) httpx is the HTTP library in use; (5) oompah/models.py Issue already has tracker_kind, owner, repo, issue_number, display_identifier fields; (6) TrackerError and TrackerTimeoutError are the exception types. Implementation plan: create oompah/github_tracker.py with GitHubClient (App auth → JWT → installation token, PAT fallback, gh-auth fallback, retry, timeout, pagination, rate-limit logging, ETag cache, response redaction) + GitHubIssueTracker stub (full TrackerProtocol); register 'github_issues' in ADAPTER_REGISTRY; tests in tests/test_github_tracker.py covering all 3 auth paths + rate-limit/auth error handling.
---

author: oompah
created: 2026-06-09 04:50
---
Implementation: Created oompah/github_tracker.py with: (1) GitHubAuth class — resolves tokens in priority order: GitHub App (JWT → installation token via PyJWT+cryptography, auto-refreshed 2 min before expiry), PAT (OOMPAH_GITHUB_TOKEN/GH_TOKEN/GITHUB_TOKEN), gh CLI fallback; (2) GitHubClient class — centralised HTTP with _MAX_RETRIES=3 exponential backoff, per-request timeout (OOMPAH_GITHUB_API_TIMEOUT), automatic link-header pagination (request_paginated), rate-limit logging (DEBUG) + 429 retry with Retry-After/X-RateLimit-Reset, ETag/conditional-GET cache support, response redaction; (3) GitHubIssueTracker — full TrackerProtocol skeleton (all 27 methods), auth wired in; (4) _github_issues_factory — reads OOMPAH_GITHUB_TRACKER_OWNER/REPO env vars. Updated oompah/tracker.py: registered 'github_issues' in ADAPTER_REGISTRY via lazy-import wrapper. Updated tests/test_tracker_protocol.py: removed 'github_issues' from unknown-kinds list; added test_github_issues_is_valid(). Created tests/test_github_tracker.py with 69 tests covering all 3 auth paths, rate-limit/auth error handling, retry logic, ETag cache, pagination.
---
<!-- COMMENTS:END -->
