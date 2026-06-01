---
id: TASK-404
title: Show dashboard warning when agent retries fail from missing credentials
status: Backlog
assignee: []
created_date: 2026-06-01 20:25
updated_date: 2026-06-01 20:25
labels:
- bug
- needs:frontend
- needs:backend
- needs:test
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
