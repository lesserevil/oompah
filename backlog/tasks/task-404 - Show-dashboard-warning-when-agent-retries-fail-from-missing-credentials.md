---
id: TASK-404
title: Show dashboard warning when agent retries fail from missing credentials
status: Merged
assignee: []
created_date: '2026-06-01 20:25'
updated_date: '2026-06-03 04:47'
labels:
  - bug
  - 'needs:frontend'
  - 'needs:backend'
  - 'needs:test'
dependencies: []
priority: high
ordinal: 26000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Context
While monitoring the resumed oompah service on port 8090, the API reported retrying tasks failing with:

```text
OpenAIError: Missing credentials. Please pass an `api_key`, `workload_identity`, `admin_ap`...
```

Examples observed from `/api/v1/state`:
- `TASK-389` retrying with the missing credentials error
- `TASK-397` briefly retrying with the same missing credentials error before running

The dashboard/main page did not surface this as an operator-visible warning. That makes the service look idle or healthy even though workers cannot start because credentials are missing.

## Expected behavior
When oompah detects an agent/task retry caused by missing provider credentials, the main dashboard should show a clear warning banner or alert. The warning should identify the affected task/project/profile when available and explain that provider credentials are missing or unavailable.

## Actual behavior
The retry state is visible through the API, but the main page does not show an obvious warning. Operators have to inspect API state or logs to understand why tasks are retrying.

## Implementation notes
- Detect credential-related failures from retrying agent/task state, provider validation state, or the existing agent error path.
- Surface the condition through the same dashboard alert mechanism used for other operator warnings if possible.
- Do not display raw secrets, tokens, request headers, or full provider config.
- The alert should clear automatically once the credential problem is no longer present.
- Keep the API shape stable unless a small explicit alert field is needed.

## Acceptance criteria
- Given an agent/task retry with an error like `OpenAIError: Missing credentials`, the dashboard main page renders an operator-visible warning.
- The warning includes enough context to identify the affected task/project/profile when available.
- The warning does not leak credential values or sensitive provider configuration.
- The warning disappears when there are no current credential-related retry failures.
- Automated tests cover the backend state/alert behavior and the dashboard rendering behavior.
<!-- SECTION:DESCRIPTION:END -->

## Comments
<!-- COMMENTS:BEGIN -->
<!-- COMMENT:BEGIN -->
index: 208f0cb1-ec0d-4f29-bac6-d27dd191cb13
author: oompah
created: 2026-06-02T01:03:15Z

Understanding: This bug requires surfacing credential-related retry failures on the dashboard. When a task retries with an error like 'OpenAIError: Missing credentials', the dashboard shows nothing to the operator. Plan: (1) Backend - add _is_credential_error() helper + dynamically compute cred_error alerts from retry_attempts in get_snapshot(), so they auto-clear when retries resolve; (2) Frontend - add a prominent credential warning banner in dashboard.html that appears above the board with proper ARIA attributes, rendering alerts with source 'cred_error'; (3) Tests - backend unit tests for get_snapshot() credential error detection, and static-analysis tests for the dashboard HTML/JS.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: a52b2b9c-bb05-4ad9-9faa-83c0d7122c91
author: oompah
created: 2026-06-02T01:10:49Z

Discovery: The orchestrator's get_snapshot() builds an alerts list from self._alerts, which the dashboard renders inline in the agent-bar. The retry_attempts dict already carries the error string per issue. The fix: (1) add _is_credential_error() module-level function with specific phrases (missing credentials, authenticationerror, invalid api key, etc.); (2) add _credential_error_alerts() method that scans retry_attempts dynamically and returns transient alert dicts with source='cred_error:<identifier>'; (3) inject these into the snapshot alerts list in get_snapshot(); (4) add a red warning banner div in dashboard.html between agent-bar and main-area, and update handleStateUpdate() to show/hide it based on cred_error: source-prefixed alerts. This ensures the alerts auto-clear when retries resolve.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 9ca46b9a-5fe4-4ab2-ad5d-66b8695e97a1
author: oompah
created: 2026-06-02T01:11:18Z

Implementation: Added _is_credential_error() helper + _credential_error_alerts() to orchestrator.py; injected dynamic cred_error alerts in get_snapshot() that auto-clear when retries resolve. Added .cred-error-banner CSS + HTML element with role=alert/aria-live between agent-bar and main-area in dashboard.html. Updated handleStateUpdate() to separate cred_error: alerts into the new banner vs other alerts into the existing agent-bar warning span. Uses esc() for XSS safety. No credentials are echoed in alert messages.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 8c2e5d96-1cda-4491-94f8-100855885680
author: oompah
created: 2026-06-02T01:11:18Z

Verification: make test passed: 3614 passed, 4 skipped. New tests: 30 in test_credential_error_alert.py (backend), 18 in test_dashboard_credential_warning.py (frontend). All acceptance criteria met: warning shown for credential retry errors, identifies affected task, no credential values leaked, clears automatically when retry resolves.
<!-- COMMENT:END -->
<!-- COMMENTS:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Implemented credential-error warning banner on dashboard. Backend: added _is_credential_error() helper and _credential_error_alerts() in orchestrator.py that dynamically injects cred_error alerts into get_snapshot() from retry_attempts - auto-clears when resolved. Frontend: added red warning banner div in dashboard.html between agent-bar and main-area with proper ARIA attributes; handleStateUpdate() separates cred_error: alerts into the banner while other alerts stay in the agent-bar. 48 new tests (30 backend + 18 frontend). All 3614 tests pass.
<!-- SECTION:FINAL_SUMMARY:END -->
